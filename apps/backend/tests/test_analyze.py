import asyncio
import json
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
from app.models import Clip, Job, Project, Transcript, Video
from app.services import analyzer as analyzer_module
from app.services import worker as worker_module
from app.services.analyzer import parse_ai_response

VALID_AI_JSON = {
    "clips": [
        {
            "title": "Momen paling gila",
            "hook": "Tunggu sampai akhir.",
            "start_sec": 12.0,
            "end_sec": 42.0,
            "score": 0.91,
            "rationale": "Ada twist di tengah.",
        },
        {
            "title": "Insight singkat",
            "hook": "Ini yang jarang dibahas.",
            "start_sec": 60.0,
            "end_sec": 95.0,
            "score": 0.74,
            "rationale": "Padat dan jelas.",
        },
    ]
}


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
    with mock.patch("app.api.clips.start_worker"):
        yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def _make_video(db, tmp_storage: Path, duration: float = 120.0) -> Video:
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
        duration_sec=duration,
        audio_codec="aac",
    )
    db.add(video)
    db.commit()
    return video


def _add_transcript(db, video: Video, text: str = "Halo semuanya, ini podcast.") -> Transcript:
    transcript = Transcript(
        video_id=video.id,
        model_name="small",
        language="id",
        duration_sec=video.duration_sec,
        text=text,
        segments=[{"start": 0.0, "end": 2.0, "text": text}],
    )
    db.add(transcript)
    db.commit()
    return transcript


# ---------------------------------------------------------------- parser tests


def test_parse_wrapped_object():
    clips = parse_ai_response(json.dumps(VALID_AI_JSON))
    assert len(clips) == 2
    assert clips[0]["score"] == pytest.approx(0.91)
    assert clips[0]["title"] == "Momen paling gila"


def test_parse_bare_array_and_markdown_fence():
    bare = json.dumps(VALID_AI_JSON["clips"])
    assert len(parse_ai_response(bare)) == 2

    fenced = "Berikut hasilnya:\n```json\n" + bare + "\n```\n"
    assert len(parse_ai_response(fenced)) == 2


def test_parse_drops_invalid_entries():
    raw = json.dumps(
        {
            "clips": [
                {"title": "no range", "score": 0.5},
                {"title": "backwards", "start_sec": 30, "end_sec": 10},
                {"title": "too short", "start_sec": 0, "end_sec": 2},
                {"title": "negative", "start_sec": -5, "end_sec": 20},
                {"title": "ok", "start_sec": 5, "end_sec": 40, "score": 2.5},
            ]
        }
    )
    clips = parse_ai_response(raw)
    assert [c["title"] for c in clips] == ["ok"]
    assert clips[0]["score"] == 1.0  # clamped


def test_parse_sorts_by_score_desc_and_caps():
    items = [
        {"title": f"clip {i}", "start_sec": i * 20, "end_sec": i * 20 + 30, "score": i / 100}
        for i in range(12)
    ]
    clips = parse_ai_response(json.dumps({"clips": items}))
    assert len(clips) == 8
    assert clips[0]["score"] > clips[-1]["score"]


def test_parse_garbage_returns_empty():
    assert parse_ai_response("bukan json") == []
    assert parse_ai_response("{}") == []
    assert parse_ai_response('{"clips": "nope"}') == []


# ----------------------------------------------- AI timeout / payload behaviour


def test_build_timeout_uses_ai_timeout_sec(monkeypatch):
    from app.services import ai as ai_service

    monkeypatch.setattr(analyzer_module.settings, "ai_timeout_sec", 300)
    timeout = analyzer_module.build_timeout()
    assert timeout.connect <= timeout.read
    assert timeout.read >= 300 - 1e-6
    assert ai_service.normalize_base_url("http://127.0.0.1:20128") == "http://127.0.0.1:20128/v1"


def test_analysis_payload_caps_transcript_and_tokens(monkeypatch):
    monkeypatch.setattr(analyzer_module, "get_effective_config", lambda: {"model": "mycombo"})
    payload = analyzer_module.build_analysis_payload("A" * 50000, 120.0)
    assert payload["max_tokens"] == 1200
    user_content = payload["messages"][1]["content"]
    assert "A" * 8000 in user_content
    assert "A" * 8001 not in user_content
    assert payload["model"] == "mycombo"


def test_analyze_timeout_error_names_the_exception(monkeypatch):
    import httpx
    from app.core.config import settings as config_settings

    monkeypatch.setattr(config_settings, "ai_timeout_sec", 300)
    monkeypatch.setattr(analyzer_module, "get_effective_config", lambda: {"api_key": "k", "model": "m", "base_url": "http://127.0.0.1:20128/v1"})

    class BoomClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            raise httpx.ReadTimeout("")

    monkeypatch.setattr(httpx, "AsyncClient", BoomClient)

    with pytest.raises(RuntimeError) as excinfo:
        asyncio.run(analyzer_module.analyze_transcript("teks", 60.0))

    message = str(excinfo.value)
    assert "Timeout AI" in message
    assert "300" in message


def test_analyze_retries_without_response_format_on_400(monkeypatch):
    import httpx
    from app.core.config import settings as config_settings

    monkeypatch.setattr(config_settings, "ai_timeout_sec", 300)
    calls: list[dict] = []

    class Resp:
        def __init__(self, status_code, body):
            self.status_code = status_code
            self._body = body

        def json(self):
            return self._body

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, json=None):
            calls.append(json)
            if json and "response_format" in json:
                return Resp(400, {"error": {"message": "response_format unsupported"}})
            return Resp(200, {"choices": [{"message": {"content": '{"clips": []}'}}]})

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(analyzer_module, "get_effective_config", lambda: {"api_key": "k", "model": "m", "base_url": "http://127.0.0.1:20128/v1"})

    assert asyncio.run(analyzer_module.analyze_transcript("teks", 60.0)) == []
    assert len(calls) == 2
    assert "response_format" in calls[0]
    assert "response_format" not in calls[1]


def test_extract_content_prefers_content_then_reasoning():
    extract = analyzer_module._extract_content_from_message
    assert extract({"content": "hello"}) == "hello"
    assert extract({"content": "", "reasoning_content": "think"}) == "think"
    assert extract({"content": None, "reasoning": "r"}) == "r"
    assert extract({"content": "", "tool_calls": [{"function": {"arguments": '{"clips": []}'}}]}) == '{"clips": []}'
    assert extract({"content": ""}) == ""
    assert extract(None) == ""


def _fake_client(responses, calls=None):
    import httpx

    class Resp:
        def __init__(self, body):
            self.status_code = 200
            self._body = body
            self.text = ""

        def json(self):
            return self._body

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, json=None):
            if calls is not None:
                calls.append(json)
            return Resp(responses.pop(0))

    return httpx, FakeClient


def test_analyze_uses_reasoning_content(monkeypatch):
    httpx, FakeClient = _fake_client(
        [{"model": "deepseek-r1", "choices": [{"finish_reason": "stop", "message": {"content": "", "reasoning_content": '{"clips": []}'}}]}]
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(analyzer_module, "get_effective_config", lambda: {"api_key": "k", "model": "m", "base_url": "http://127.0.0.1:20128/v1"})

    assert asyncio.run(analyzer_module.analyze_transcript("teks", 60.0)) == []


def test_analyze_retries_when_finish_reason_length(monkeypatch):
    calls: list[dict] = []
    httpx, FakeClient = _fake_client(
        [
            {"model": "m", "choices": [{"finish_reason": "length", "message": {"content": '{"clips": ['}}]},
            {"model": "m", "choices": [{"finish_reason": "stop", "message": {"content": '{"clips": []}'}}]},
        ],
        calls,
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(analyzer_module, "get_effective_config", lambda: {"api_key": "k", "model": "m", "base_url": "http://127.0.0.1:20128/v1"})

    assert asyncio.run(analyzer_module.analyze_transcript("teks", 60.0)) == []
    assert len(calls) == 2
    assert calls[1]["max_tokens"] > calls[0]["max_tokens"]


def test_analyze_empty_content_error_is_actionable(monkeypatch):
    httpx, FakeClient = _fake_client(
        [{"model": "m", "choices": [{"finish_reason": "error", "message": {"content": "", "reasoning": None}}]}]
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(analyzer_module, "get_effective_config", lambda: {"api_key": "k", "model": "m", "base_url": "http://127.0.0.1:20128/v1"})

    with pytest.raises(RuntimeError) as excinfo:
        asyncio.run(analyzer_module.analyze_transcript("teks", 60.0))
    message = str(excinfo.value)
    assert "finish_reason=error" in message
    assert "Check model availability" in message


# ------------------------------------------------- SSE / non-JSON body tolerance


class _FakeResponse:
    def __init__(self, body, status_code=200):
        self._body = body
        self.status_code = status_code

    def json(self):
        if isinstance(self._body, dict):
            return self._body
        raise ValueError("not json")

    @property
    def text(self):
        return self._body


def test_load_body_accepts_normal_json():
    body = analyzer_module._load_body(_FakeResponse({"choices": [{"message": {"content": "{}"}}]}))
    assert body["choices"][0]["message"]["content"] == "{}"


def test_load_body_rebuilds_sse_stream():
    sse = (
        'data: {"model":"m","choices":[{"delta":{"content":"{\\"clips\\": "}}]}\n'
        'data: {"model":"m","choices":[{"delta":{"content":"[]}"}}]}\n'
        'data: [DONE]\n'
    )
    body = analyzer_module._load_body(_FakeResponse(sse))
    content = body["choices"][0]["message"]["content"]
    assert content == '{"clips": []}'


def test_load_body_raises_on_garbage():
    with pytest.raises(RuntimeError) as excinfo:
        analyzer_module._load_body(_FakeResponse("not json at all"))
    assert "non-JSON body" in str(excinfo.value)


def test_analyze_handles_sse_response(monkeypatch):
    import httpx

    sse = (
        'data: {"model":"m","choices":[{"delta":{"content":"{\\"clips\\": ["}}]}\n'
        'data: {"model":"m","choices":[{"delta":{"content":"]}"}}]}\n'
        'data: [DONE]\n'
    )

    class Resp:
        def __init__(self):
            self.status_code = 200
            self.text = sse

        def json(self):
            raise ValueError("SSE body is not JSON")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, json=None):
            return Resp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(analyzer_module, "get_effective_config", lambda: {"api_key": "k", "model": "m", "base_url": "http://127.0.0.1:20128/v1"})

    assert asyncio.run(analyzer_module.analyze_transcript("teks", 60.0)) == []


# ------------------------------------------------------------------ API tests


def test_analyze_requires_transcript(client, session, tmp_storage):
    video = _make_video(session, tmp_storage)
    response = client.post(f"/api/videos/{video.id}/analyze")
    assert response.status_code == 409
    assert "transkrip" in response.json()["detail"].lower()


def test_analyze_unknown_video(client):
    assert client.post("/api/videos/999/analyze").status_code == 404


def test_enqueue_analysis(client, session, tmp_storage):
    video = _make_video(session, tmp_storage)
    _add_transcript(session, video)

    response = client.post(f"/api/videos/{video.id}/analyze")
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["video_id"] == video.id

    job = session.get(Job, body["job_id"])
    assert job.kind == "analyze"
    assert job.status == "queued"


def test_enqueue_analysis_twice(client, session, tmp_storage):
    video = _make_video(session, tmp_storage)
    _add_transcript(session, video)

    assert client.post(f"/api/videos/{video.id}/analyze").status_code == 202
    second = client.post(f"/api/videos/{video.id}/analyze")
    assert second.status_code == 200
    assert second.json()["message"] == "Analysis already queued or running"
    assert session.query(Job).count() == 1


def test_list_and_update_clip(client, session, tmp_storage):
    video = _make_video(session, tmp_storage)
    clip = Clip(
        video_id=video.id,
        title="Awal",
        start_sec=10.0,
        end_sec=40.0,
        score=0.5,
        status="candidate",
    )
    session.add(clip)
    session.commit()

    listed = client.get(f"/api/videos/{video.id}/clips")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["title"] == "Awal"

    patched = client.patch(
        f"/api/clips/{clip.id}",
        json={"title": "Judul baru", "status": "approved", "end_sec": 45.0},
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Judul baru"
    assert patched.json()["status"] == "approved"
    assert patched.json()["end_sec"] == 45.0


def test_patch_rejects_inverted_range(client, session, tmp_storage):
    video = _make_video(session, tmp_storage)
    clip = Clip(video_id=video.id, title="X", start_sec=10.0, end_sec=20.0, status="candidate")
    session.add(clip)
    session.commit()

    response = client.patch(f"/api/clips/{clip.id}", json={"end_sec": 5.0})
    assert response.status_code == 400


def test_patch_rejects_uneditable_status(client, session, tmp_storage):
    video = _make_video(session, tmp_storage)
    clip = Clip(video_id=video.id, title="X", start_sec=10.0, end_sec=20.0, status="rendered")
    session.add(clip)
    session.commit()

    assert client.patch(f"/api/clips/{clip.id}", json={"title": "Y"}).status_code == 409


def test_delete_clip_removes_files(client, session, tmp_storage):
    video = _make_video(session, tmp_storage)
    output = tmp_storage / "clips" / "out.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"\x00clip")

    clip = Clip(
        video_id=video.id,
        title="X",
        start_sec=10.0,
        end_sec=20.0,
        status="rendered",
        output_path="clips/out.mp4",
    )
    session.add(clip)
    session.commit()
    clip_id = clip.id

    response = client.delete(f"/api/clips/{clip_id}")
    assert response.status_code == 200
    assert response.json() == {"deleted": clip_id}
    assert session.get(Clip, clip_id) is None
    assert not output.exists()


# --------------------------------------------------------------- worker tests


def _fake_analyzer(result_json):
    async def _inner(transcript_text, duration_sec):
        return parse_ai_response(json.dumps(result_json))

    return _inner


def test_worker_creates_candidate_clips(session, tmp_storage, monkeypatch):
    video = _make_video(session, tmp_storage)
    _add_transcript(session, video)

    job = Job(video_id=video.id, kind="analyze", status="queued", payload={"video_id": video.id})
    session.add(job)
    session.commit()
    job_id = job.id

    monkeypatch.setattr(
        worker_module, "analyze_transcript", _fake_analyzer(VALID_AI_JSON)
    )

    assert worker_module._process_analyze_job(session, job) is True

    job = session.get(Job, job_id)
    assert job.status == "succeeded"
    assert job.progress == 100
    assert job.finished_at is not None

    clips = session.scalars(select(Clip).where(Clip.video_id == video.id)).all()
    assert len(clips) == 2
    assert {clip.status for clip in clips} == {"candidate"}
    assert clips[0].title == "Momen paling gila"
    assert clips[0].score == pytest.approx(0.91)


def test_worker_replaces_previous_candidates(session, tmp_storage, monkeypatch):
    video = _make_video(session, tmp_storage)
    _add_transcript(session, video)

    session.add(Clip(video_id=video.id, title="Lama", start_sec=1.0, end_sec=20.0, status="candidate"))
    session.add(Clip(video_id=video.id, title="Disetujui", start_sec=1.0, end_sec=20.0, status="approved"))
    session.commit()

    job = Job(video_id=video.id, kind="analyze", status="queued", payload={"video_id": video.id})
    session.add(job)
    session.commit()

    monkeypatch.setattr(worker_module, "analyze_transcript", _fake_analyzer(VALID_AI_JSON))
    assert worker_module._process_analyze_job(session, job) is True

    titles = {clip.title for clip in session.scalars(select(Clip)).all()}
    assert "Lama" not in titles  # old candidate replaced
    assert "Disetujui" in titles  # approved clip never touched
    assert "Momen paling gila" in titles


def test_worker_clamps_end_to_video_duration(session, tmp_storage, monkeypatch):
    video = _make_video(session, tmp_storage, duration=50.0)
    _add_transcript(session, video)

    job = Job(video_id=video.id, kind="analyze", status="queued", payload={"video_id": video.id})
    session.add(job)
    session.commit()

    long_clip = {"clips": [{"title": "Kepanjangan", "start_sec": 10.0, "end_sec": 100.0, "score": 0.8}]}
    monkeypatch.setattr(worker_module, "analyze_transcript", _fake_analyzer(long_clip))
    assert worker_module._process_analyze_job(session, job) is True

    clip = session.scalar(select(Clip))
    assert clip.end_sec == pytest.approx(50.0)


def test_worker_fails_without_transcript(session, tmp_storage, monkeypatch):
    video = _make_video(session, tmp_storage)
    job = Job(video_id=video.id, kind="analyze", status="queued", payload={"video_id": video.id})
    session.add(job)
    session.commit()
    job_id = job.id

    async def boom(*args, **kwargs):  # pragma: no cover - must not be called
        raise AssertionError("analyzer must not run without a transcript")

    monkeypatch.setattr(worker_module, "analyze_transcript", boom)

    assert worker_module._process_analyze_job(session, job) is False
    job = session.get(Job, job_id)
    assert job.status == "failed"
    assert "transkrip" in job.error.lower()
    assert session.scalar(select(Clip)) is None


def test_worker_marks_failed_when_ai_errors(session, tmp_storage, monkeypatch):
    video = _make_video(session, tmp_storage)
    _add_transcript(session, video)
    job = Job(video_id=video.id, kind="analyze", status="queued", payload={"video_id": video.id})
    session.add(job)
    session.commit()
    job_id = job.id

    async def boom(*args, **kwargs):
        raise RuntimeError("AI not configured: missing api_key or model in settings")

    monkeypatch.setattr(worker_module, "analyze_transcript", boom)

    assert worker_module._process_analyze_job(session, job) is False
    job = session.get(Job, job_id)
    assert job.status == "failed"
    assert "not configured" in job.error
