from fastapi.testclient import TestClient

from app.main import app


def test_config_never_exposes_api_key():
    client = TestClient(app)
    response = client.get("/api/config")
    assert response.status_code == 200

    body = response.json()
    assert "ai_api_key" not in body
    assert "ai_configured" in body
    assert body["whisper_model"]
    assert body["max_concurrent_jobs"] == 1


def test_config_exposes_upload_limits():
    client = TestClient(app)
    body = client.get("/api/config").json()

    assert body["max_upload_mb"] > 0
    assert "max_duration_sec" in body
    assert body["max_duration_sec"] >= 0
    assert set(body["allowed_extensions"]) == {".mp4", ".mov", ".mkv"}
    assert "video/mp4" in body["allowed_mime_types"]
