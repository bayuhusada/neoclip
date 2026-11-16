import json
from pathlib import Path
from typing import Any

from app.core.config import settings

CONFIG_FILE = Path(settings.storage_dir) / "ai_config.json"


def _defaults() -> dict[str, str]:
    return {
        "base_url": settings.ai_base_url,
        "api_key": "",
        "model": "",
    }


def _read_file() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_file(data: dict[str, Any]) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_effective_config() -> dict[str, Any]:
    """Values from `storage/ai_config.json` win; `.env` only fills empty fields.

    The UI is the normal way to set credentials, so an explicit save must not be
    silently overridden by leftovers in `.env`. `.env` stays as the bootstrap
    default (and as the fallback when the JSON file is missing).
    """
    merged = _defaults()
    for key in ("base_url", "api_key", "model"):
        value = _read_file().get(key)
        if isinstance(value, str) and value.strip():
            merged[key] = value.strip()
    for key in ("base_url", "api_key", "model"):
        if merged[key]:
            continue
        env_value = getattr(settings, f"ai_{key}")
        if env_value:
            merged[key] = env_value
    return merged


def get_config_for_ui() -> dict[str, Any]:
    """Config safe to return to frontend (key masked, never sent in clear)."""
    cfg = get_effective_config()
    masked = cfg.copy()
    raw = masked.get("api_key") or ""
    if raw:
        masked["api_key"] = "****" + raw[-4:] if len(raw) > 4 else "****"
    masked["configured"] = bool(cfg.get("api_key") and cfg.get("model"))
    return masked


def save_config(base_url: str, api_key: str | None, model: str | None) -> dict[str, Any]:
    """Persist user-provided values to JSON file. None keeps the existing value."""
    current = _read_file()
    current["base_url"] = base_url.strip()
    if api_key is not None:
        current["api_key"] = api_key.strip()
    if model is not None:
        current["model"] = model.strip()
    _write_file(current)
    return get_config_for_ui()
