from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registers tables)
from app.db import Base, get_db
from app.main import app
from app.models import Job, Project, Transcript, Video
from app.services import worker as worker_module
from app.services.audio import AudioExtractionError

MOCK_TRANSCRIBE_RESULT = (
    "Hello world. This is a test.",
    "en",
    [
        {"start": 0.0, "end": 2.0, "text": "Hello world."},
        {"start": 2.0, "end": 4.0, "text": "This is a test."},
    ],
)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        yield db
    engine.dispose()


@pytest.fixture()
def tmp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.storage_dir", tmp_path)
    return tmp_path


@pytest.fixture()
def client(session, tmp_storage):
    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with mock.patch("app.api.transcribe.start_worker"):
        yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def _make_video(db, tmp_storage: Path) -> Video:
    project = Project(name="Podcast")
    db.add(project)
    db.commit()

    stored = tmp_storage / "uploads" / "talk.mp4"
    stored.parent.mkdir(parents=True, exist_ok=True)
    stored.write_bytes(b"\x00fake")

    video = Video(
        project_id=project.id,
        original_filename="talk.mp4",
        stored_path="uploads/talk.mp4",
        size_bytes=4,
        status="ready",
        duration_sec=90.0,
        audio_codec="aac",
    )
    db.add(video)
    db.commit()
    return video


def test_enqueue_transcription(client, session, tmp_storage):
    video = _make_video(session, tmp_storage)

    response = client.post(f"/api/videos/{video.id}/transcribe")
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["video_id"] == video.id

    job = session.get(Job, body["job_id"])
    assert job is not None
    assert job.kind == "transcribe"
    assert job.status == "queued"


def test_enqueue_twice_is_rejected(client, session, tmp_storage):
    video = _make_video(session, tmp_storage)
    assert client.post(f"/api/videos/{video.id}/transcribe").status_code == 202

    second = client.post(f"/api/videos/{video.id}/transcribe")
    assert second.status_code == 200
    assert second.json()["message"] == "Transcription already queued or running"
    assert second.json()["status"] == "queued"
    assert session.query(Job).count() == 1


def test_transcript_404_and_jobs_list(client, session, tmp_storage):
    video = _make_video(session, tmp_storage)
    assert client.get(f"/api/videos/{video.id}/transcript").status_code == 404
    jobs = client.get(f"/api/videos/{video.id}/jobs")
    assert jobs.status_code == 200
    assert jobs.json() == []


def test_transcript_after_success(client, session, tmp_storage):
    video = _make_video(session, tmp_storage)
    session.add(
        Transcript(
            video_id=video.id,
            model_name="small",
            language="en",
            duration_sec=90.0,
            text="Done",
            segments=[{"start": 0.0, "end": 1.0, "text": "Done"}],
        )
    )
    session.commit()

    # Re-enqueueing must report the existing transcript instead of creating a job
    response = client.post(f"/api/videos/{video.id}/transcribe")
    assert response.status_code == 200
    assert response.json()["message"] == "Transcript already exists"
    assert session.query(Job).count() == 0

    transcript = client.get(f"/api/videos/{video.id}/transcript")
    assert transcript.status_code == 200
    assert transcript.json()["text"] == "Done"


@mock.patch.object(worker_module, "transcribe_audio_file", return_value=MOCK_TRANSCRIBE_RESULT)
@mock.patch.object(worker_module, "extract_audio_wav", return_value=Path("audio/1.wav"))
def test_worker_processes_job(mock_extract, mock_transcribe, session, tmp_storage):
    video = _make_video(session, tmp_storage)
    job = Job(video_id=video.id, kind="transcribe", status="queued", payload={"video_id": video.id})
    session.add(job)
    session.commit()
    job_id = job.id

    assert worker_module._process_transcribe_job(session, job) is True

    job = session.get(Job, job_id)
    assert job.status == "succeeded"
    assert job.progress == 100
    assert job.finished_at is not None

    transcript = session.scalar(select(Transcript).where(Transcript.video_id == video.id))
    assert transcript is not None
    assert transcript.text == MOCK_TRANSCRIBE_RESULT[0]
    assert transcript.language == "en"
    assert transcript.segments[0]["start"] == 0.0
    assert transcript.model_name == "small"


@mock.patch.object(
    worker_module, "extract_audio_wav", side_effect=AudioExtractionError("ffmpeg blew up")
)
def test_worker_marks_job_failed(mock_extract, session, tmp_storage):
    video = _make_video(session, tmp_storage)
    job = Job(video_id=video.id, kind="transcribe", status="queued", payload={"video_id": video.id})
    session.add(job)
    session.commit()
    job_id = job.id

    assert worker_module._process_transcribe_job(session, job) is False

    job = session.get(Job, job_id)
    assert job.status == "failed"
    assert job.progress == 0
    assert "ffmpeg blew up" in job.error
    assert job.finished_at is not None
    assert session.scalar(select(Transcript).where(Transcript.video_id == video.id)) is None


@mock.patch.object(worker_module, "extract_audio_wav")
def test_worker_fails_fast_without_audio_stream(mock_extract, session, tmp_storage):
    project = Project(name="Podcast")
    session.add(project)
    session.commit()

    stored = tmp_storage / "uploads" / "silent.mp4"
    stored.parent.mkdir(parents=True, exist_ok=True)
    stored.write_bytes(b"\x00fake")

    video = Video(
        project_id=project.id,
        original_filename="silent.mp4",
        stored_path="uploads/silent.mp4",
        size_bytes=4,
        status="ready",
        duration_sec=30.0,
        audio_codec=None,  # ffprobe found no audio stream
    )
    session.add(video)
    session.commit()

    job = Job(video_id=video.id, kind="transcribe", status="queued", payload={"video_id": video.id})
    session.add(job)
    session.commit()
    job_id = job.id

    assert worker_module._process_transcribe_job(session, job) is False

    mock_extract.assert_not_called()
    job = session.get(Job, job_id)
    assert job.status == "failed"
    assert "no audio stream" in job.error
