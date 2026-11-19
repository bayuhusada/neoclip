from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registers tables)
from app.api import videos as videos_api
from app.core.config import settings
from app.db import Base, get_db
from app.main import app
from app.models.project import Project
from app.models.video import Video
from app.services.files import max_upload_bytes
from app.services.probe import ProbeError

FAKE_PROBE_RESULT = {
    "duration_sec": 360.5,
    "width": 1920,
    "height": 1080,
    "fps": 30.0,
    "video_codec": "h264",
    "audio_codec": "aac",
}


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        yield db
    engine.dispose()


@pytest.fixture()
def temp_storage(tmp_path, monkeypatch):
    """Never write test uploads into the real storage/ directory."""
    monkeypatch.setattr(settings, "storage_dir", tmp_path)
    return tmp_path


@pytest.fixture()
def client(session, temp_storage):
    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def _make_project(db: Session) -> Project:
    project = Project(name="Test Project")
    db.add(project)
    db.commit()
    return project


def test_upload_rejects_wrong_extension(client):
    response = client.post(
        "/api/videos",
        data={"project_id": 1},
        files={"file": ("bad.txt", b"fake", "text/plain")},
    )
    assert response.status_code == 400
    assert "not allowed" in response.json()["detail"]


def test_upload_rejects_bad_mime(client, session):
    project = _make_project(session)
    response = client.post(
        "/api/videos",
        data={"project_id": project.id},
        files={"file": ("movie.mp4", b"fake", "text/plain")},
    )
    assert response.status_code == 400


def test_upload_unknown_project(client):
    response = client.post(
        "/api/videos",
        data={"project_id": 9999},
        files={"file": ("video.mp4", b"fake", "video/mp4")},
    )
    assert response.status_code == 404


@mock.patch.object(videos_api, "probe_media", return_value=FAKE_PROBE_RESULT)
def test_upload_creates_ready_video(_mock_probe, client, session, temp_storage):
    project = _make_project(session)
    response = client.post(
        "/api/videos",
        data={"project_id": project.id},
        files={"file": ("talk.mp4", b"\x00\x01fakevideo", "video/mp4")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["original_filename"] == "talk.mp4"
    assert body["stored_path"].startswith("uploads/")
    assert body["stored_path"].endswith(".mp4")
    assert body["size_bytes"] > 0
    assert body["status"] == "ready"
    assert body["duration_sec"] == 360.5
    assert body["width"] == 1920
    assert body["height"] == 1080
    assert body["fps"] == 30.0
    assert body["video_codec"] == "h264"
    assert body["audio_codec"] == "aac"

    disk_path = Path(body["stored_path"])
    assert (temp_storage / disk_path).exists()

    list_resp = client.get(f"/api/videos?project_id={project.id}")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    detail_resp = client.get(f"/api/videos/{body['id']}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["status"] == "ready"


@mock.patch.object(videos_api, "probe_media", return_value=FAKE_PROBE_RESULT)
def test_upload_rejects_duration_over_limit(_mock_probe, client, session, temp_storage, monkeypatch):
    monkeypatch.setattr(settings, "max_duration_sec", 60)  # FAKE_PROBE_RESULT is 360.5 s
    project = _make_project(session)
    response = client.post(
        "/api/videos",
        data={"project_id": project.id},
        files={"file": ("long.mp4", b"\x00\x01fakevideo", "video/mp4")},
    )
    assert response.status_code == 413
    assert "melebihi batas" in response.json()["detail"]
    assert list((temp_storage / "uploads").glob("*")) == []
    assert client.get(f"/api/videos?project_id={project.id}").json() == []


@mock.patch.object(videos_api, "probe_media", side_effect=ProbeError("corrupt file"))
def test_upload_marks_video_failed(_mock_probe, client, session):
    project = _make_project(session)
    response = client.post(
        "/api/videos",
        data={"project_id": project.id},
        files={"file": ("talk.mov", b"fake", "video/quicktime")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"
    assert body["error"] == "corrupt file"


@mock.patch.object(videos_api, "probe_media", return_value=FAKE_PROBE_RESULT)
def test_delete_video_removes_row_and_file(_mock_probe, client, session, temp_storage):
    project = _make_project(session)
    created = client.post(
        "/api/videos",
        data={"project_id": project.id},
        files={"file": ("talk.mp4", b"\x00\x01fakevideo", "video/mp4")},
    ).json()

    stored = temp_storage / created["stored_path"]
    assert stored.exists()

    response = client.delete(f"/api/videos/{created['id']}")
    assert response.status_code == 204
    assert not stored.exists()
    assert client.get(f"/api/videos/{created['id']}").status_code == 404
    assert client.get(f"/api/videos?project_id={project.id}").json() == []


@mock.patch.object(videos_api, "probe_media", return_value=FAKE_PROBE_RESULT)
def test_delete_project_removes_videos_and_files(_mock_probe, client, session, temp_storage):
    project = _make_project(session)
    created = client.post(
        "/api/videos",
        data={"project_id": project.id},
        files={"file": ("talk.mp4", b"\x00\x01fakevideo", "video/mp4")},
    ).json()
    stored = temp_storage / created["stored_path"]
    assert stored.exists()

    response = client.delete(f"/api/projects/{project.id}")
    assert response.status_code == 204
    assert not stored.exists()
    assert client.get(f"/api/projects/{project.id}").status_code == 404
    assert client.get(f"/api/videos/{created['id']}").status_code == 404


def test_delete_missing_video_and_project_return_404(client):
    assert client.delete("/api/videos/9999").status_code == 404
    assert client.delete("/api/projects/9999").status_code == 404


def test_delete_video_never_unlinks_outside_storage(client, session, temp_storage):
    project = _make_project(session)
    outside = temp_storage.parent / "outside-secret.txt"
    outside.write_text("keep me", encoding="utf-8")

    video = Video(
        project_id=project.id,
        original_filename="evil.mp4",
        stored_path="../outside-secret.txt",
        size_bytes=1,
        status="ready",
    )
    session.add(video)
    session.commit()

    response = client.delete(f"/api/videos/{video.id}")
    assert response.status_code == 204
    assert outside.exists()


def test_max_upload_bytes_reads_settings():
    assert max_upload_bytes() == settings.max_upload_mb * 1024 * 1024


@mock.patch.object(videos_api, "probe_media", return_value=FAKE_PROBE_RESULT)
def test_upload_accepts_youtube_url(_mock_probe, client, session, temp_storage):
    project = _make_project(session)
    response = client.post(
        "/api/videos",
        data={
            "project_id": project.id,
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        },
        files={"file": ("song.mp4", b"\x00\x01fakevideo", "video/mp4")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["youtube_url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@mock.patch.object(videos_api, "probe_media", return_value=FAKE_PROBE_RESULT)
def test_update_video_youtube_url(_mock_probe, client, session, temp_storage):
    project = _make_project(session)
    created = client.post(
        "/api/videos",
        data={
            "project_id": project.id,
            "youtube_url": "https://youtu.be/dQw4w9WgXcQ",
        },
        files={"file": ("song.mp4", b"\x00\x01fakevideo", "video/mp4")},
    ).json()

    response = client.patch(
        f"/api/videos/{created['id']}",
        json={"youtube_url": "https://www.youtube.com/watch?v=7FvHcY0mMqI"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["youtube_url"] == "https://www.youtube.com/watch?v=7FvHcY0mMqI"

    assert (
        client.patch(
            f"/api/videos/{created['id']}",
            json={"youtube_url": "https://not-a-youtube-url"},
        ).status_code
        == 400
    )
