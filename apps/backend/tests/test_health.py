from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_returns_running():
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["docs"] == "/docs"


def test_health_reports_services():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["services"]) == {"ffmpeg", "ffprobe", "storage"}
    assert body["services"]["storage"] is True


def test_health_without_api_prefix_is_404():
    assert client.get("/health").status_code == 404
