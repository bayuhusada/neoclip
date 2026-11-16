from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.ai import (
    fetch_ai_quota,
    normalize_base_url,
    test_ai_chat,
    test_ai_connection,
)
from app.services.ai_config import get_config_for_ui, get_effective_config, save_config

router = APIRouter(prefix="/settings/ai", tags=["settings"])


class AiSettingsIn(BaseModel):
    base_url: str = Field(default="", max_length=300)
    api_key: str | None = Field(default=None, max_length=400)
    model: str | None = Field(default=None, max_length=200)
    # Only used by /test: also exercise /chat/completions, not just /models.
    deep: bool = False


def _resolve(payload: AiSettingsIn | None) -> tuple[str, str]:
    """Return (base_url, api_key). Explicit request values win over stored ones."""
    stored = get_effective_config()
    base_url = (payload.base_url if payload and payload.base_url else stored["base_url"]).strip()
    api_key = (payload.api_key if payload and payload.api_key else stored.get("api_key") or "").strip()
    return base_url, api_key


@router.get("")
def read_ai_settings() -> dict[str, Any]:
    return get_config_for_ui()


@router.post("")
def update_ai_settings(payload: AiSettingsIn) -> dict[str, Any]:
    try:
        normalized = normalize_base_url(payload.base_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return save_config(normalized, payload.api_key, payload.model)


@router.post("/test")
def run_connection_test(payload: AiSettingsIn | None = None) -> dict[str, Any]:
    base_url, api_key = _resolve(payload)
    if not api_key:
        return {"ok": False, "error": "API key kosong — isi dulu lalu simpan.", "models": []}

    result = test_ai_connection(base_url, api_key)
    if payload is not None and payload.deep:
        stored = get_effective_config()
        model = (payload.model or stored.get("model") or "").strip()
        result["chat"] = test_ai_chat(base_url, api_key, model)
    return result


@router.post("/quota")
def run_quota_check(payload: AiSettingsIn | None = None) -> dict[str, Any]:
    base_url, api_key = _resolve(payload)
    if not api_key:
        return {"available": False, "error": "API key kosong — isi dulu lalu simpan."}
    return fetch_ai_quota(base_url, api_key)
