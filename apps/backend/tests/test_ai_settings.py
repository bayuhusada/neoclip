import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import ai as ai_service
from app.services import ai_config


@pytest.fixture()
def client(tmp_path, monkeypatch):
    config_file = tmp_path / "ai_config.json"
    monkeypatch.setattr(ai_config, "CONFIG_FILE", config_file)
    # .env values must not leak into assertions about the stored file.
    monkeypatch.setattr(ai_config.settings, "ai_base_url", "http://127.0.0.1:20128/v1")
    monkeypatch.setattr(ai_config.settings, "ai_api_key", "")
    monkeypatch.setattr(ai_config.settings, "ai_model", "")
    return TestClient(app)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("http://127.0.0.1:20128", "http://127.0.0.1:20128/v1"),
        ("http://127.0.0.1:20128/", "http://127.0.0.1:20128/v1"),
        ("http://127.0.0.1:20128/v1", "http://127.0.0.1:20128/v1"),
        ("https://api.example.com/v1/", "https://api.example.com/v1"),
    ],
)
def test_normalize_base_url(raw, expected):
    assert ai_service.normalize_base_url(raw) == expected


def test_normalize_base_url_rejects_missing_scheme():
    with pytest.raises(ValueError):
        ai_service.normalize_base_url("127.0.0.1:20128")


def test_save_masks_api_key(client):
    saved = client.post(
        "/api/settings/ai",
        json={
            "base_url": "http://127.0.0.1:20128",
            "api_key": "sk-test-abcd1234",
            "model": "mycombo",
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["base_url"] == "http://127.0.0.1:20128/v1"
    assert body["api_key"] == "****1234"
    assert body["configured"] is True
    assert "sk-test-abcd1234" not in saved.text

    again = client.get("/api/settings/ai").json()
    assert again["api_key"] == "****1234"
    assert again["model"] == "mycombo"


def test_save_keeps_existing_key_when_omitted(client):
    client.post(
        "/api/settings/ai",
        json={"base_url": "http://127.0.0.1:20128/v1", "api_key": "sk-keep-9999"},
    )
    client.post(
        "/api/settings/ai",
        json={"base_url": "http://127.0.0.1:20128/v1", "model": "mycombo"},
    )
    assert ai_config.get_effective_config()["api_key"] == "sk-keep-9999"


def test_saved_values_beat_env(client, monkeypatch):
    monkeypatch.setattr(ai_config.settings, "ai_api_key", "sk-from-env-0000")
    monkeypatch.setattr(ai_config.settings, "ai_model", "env-model")
    assert ai_config.get_effective_config()["api_key"] == "sk-from-env-0000"

    client.post(
        "/api/settings/ai",
        json={"base_url": "http://127.0.0.1:9999", "api_key": "sk-from-ui-1111", "model": "ui-model"},
    )
    effective = ai_config.get_effective_config()
    assert effective["api_key"] == "sk-from-ui-1111"
    assert effective["model"] == "ui-model"
    assert effective["base_url"] == "http://127.0.0.1:9999/v1"


def test_env_used_when_file_missing(client, monkeypatch):
    monkeypatch.setattr(ai_config.settings, "ai_model", "env-only-model")
    assert ai_config.get_effective_config()["model"] == "env-only-model"


def test_save_rejects_bad_base_url(client):
    response = client.post("/api/settings/ai", json={"base_url": "nope"})
    assert response.status_code == 400


def test_test_endpoint_without_key(client):
    response = client.post("/api/settings/ai/test", json={})
    assert response.status_code == 200
    assert response.json()["ok"] is False


def test_test_endpoint_ok(client, monkeypatch):
    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"data": [{"id": "mycombo"}, {"id": "gemini/gemini-3.6-flash"}]}

    def fake_get(url, headers=None, timeout=None):
        assert url == "http://127.0.0.1:20128/v1/models"
        assert headers["Authorization"] == "Bearer sk-test"
        return FakeResponse()

    monkeypatch.setattr(ai_service.httpx, "get", fake_get)
    result = ai_service.test_ai_connection("http://127.0.0.1:20128", "sk-test")
    assert result["ok"] is True
    assert result["models"] == ["mycombo", "gemini/gemini-3.6-flash"]
    assert isinstance(result["latency_ms"], int)


def test_test_endpoint_failure(client, monkeypatch):
    class FakeResponse:
        status_code = 401
        text = "unauthorized"

        @staticmethod
        def json():
            return {"error": {"message": "Invalid API key"}}

    monkeypatch.setattr(ai_service.httpx, "get", lambda *a, **k: FakeResponse())
    result = ai_service.test_ai_connection("http://127.0.0.1:20128", "bad")
    assert result["ok"] is False
    assert result["status_code"] == 401
    assert "Invalid API key" in result["error"]


def test_chat_probe_requires_model():
    result = ai_service.test_ai_chat("http://127.0.0.1:20128", "sk-test", "")
    assert result["ok"] is False
    assert "Model kosong" in result["error"]


def test_chat_probe_ok(monkeypatch):
    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": "ok"}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        assert url == "http://127.0.0.1:20128/v1/chat/completions"
        assert headers["Authorization"] == "Bearer sk-test"
        assert json["max_tokens"] == 8
        return FakeResponse()

    monkeypatch.setattr(ai_service.httpx, "post", fake_post)
    result = ai_service.test_ai_chat("http://127.0.0.1:20128", "sk-test", "mycombo")
    assert result["ok"] is True
    assert result["reply"] == "ok"
    assert result["model"] == "mycombo"
    assert isinstance(result["latency_ms"], int)


def test_chat_probe_timeout_names_exception(monkeypatch):
    import httpx

    def fake_post(*args, **kwargs):
        raise httpx.ReadTimeout("")

    monkeypatch.setattr(ai_service.httpx, "post", fake_post)
    result = ai_service.test_ai_chat("http://127.0.0.1:20128", "sk-test", "mycombo", timeout=30)
    assert result["ok"] is False
    assert "Timeout 30s" in result["error"]
    assert "ReadTimeout" in result["error"]


def test_test_endpoint_deep_includes_chat(client, monkeypatch):
    from app.api import ai_settings as ai_settings_api

    monkeypatch.setattr(
        ai_settings_api,
        "test_ai_connection",
        lambda *a, **k: {"ok": True, "models": ["mycombo"], "latency_ms": 5},
    )
    monkeypatch.setattr(
        ai_settings_api,
        "test_ai_chat",
        lambda *a, **k: {"ok": True, "model": "mycombo", "latency_ms": 9, "reply": "ok"},
    )

    client.post(
        "/api/settings/ai",
        json={"base_url": "http://127.0.0.1:20128", "api_key": "sk-x", "model": "mycombo"},
    )
    body = client.post("/api/settings/ai/test", json={"deep": True}).json()
    assert body["ok"] is True
    assert body["chat"]["reply"] == "ok"


def test_test_endpoint_without_deep_has_no_chat_key(client):
    client.post(
        "/api/settings/ai",
        json={"base_url": "http://127.0.0.1:20128", "api_key": "sk-x", "model": "mycombo"},
    )
    body = client.post("/api/settings/ai/test", json={}).json()
    assert "chat" not in body


def test_quota_unavailable_when_endpoints_missing(client, monkeypatch):
    monkeypatch.setattr(ai_service, "_fetch_json", lambda *a, **k: None)
    result = ai_service.fetch_ai_quota("http://127.0.0.1:20128", "sk-test")
    assert result["available"] is False


def test_quota_computes_remaining(client, monkeypatch):
    subscription = {"hard_limit_usd": 20.0, "plan": {"title": "pay-as-you-go"}}
    usage = {"total_usage": 550}

    def fake_fetch(url, headers, timeout):
        return subscription if "subscription" in url else usage

    monkeypatch.setattr(ai_service, "_fetch_json", fake_fetch)
    result = ai_service.fetch_ai_quota("http://127.0.0.1:20128", "sk-test")
    assert result["available"] is True
    assert result["total"] == 20.0
    assert result["used"] == pytest.approx(5.5)
    assert result["remaining"] == pytest.approx(14.5)
    assert result["reset_at"].endswith("Z")
    assert result["reset_at"][8:10] == "01"  # billing resets on the 1st (UTC)


def test_config_file_written_as_json(client, tmp_path):
    client.post(
        "/api/settings/ai",
        json={"base_url": "http://127.0.0.1:20128", "api_key": "sk-x", "model": "m"},
    )
    stored = json.loads(ai_config.CONFIG_FILE.read_text(encoding="utf-8"))
    assert stored == {
        "base_url": "http://127.0.0.1:20128/v1",
        "api_key": "sk-x",
        "model": "m",
    }
