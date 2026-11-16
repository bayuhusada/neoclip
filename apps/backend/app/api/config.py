from fastapi import APIRouter

from app.core.config import settings
from app.services.files import ALLOWED_EXTENSIONS, ALLOWED_MIME_TYPES

router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
def read_config():
    """Read-only, secret-free view of the active configuration.

    The API key is intentionally never returned; only whether 9Router is
    configured is exposed so the UI can show a safe status badge.
    """
    return {
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "ai_base_url": settings.ai_base_url,
        "ai_model": settings.ai_model,
        "ai_configured": bool(settings.ai_api_key and settings.ai_model),
        "ai_timeout_sec": settings.ai_timeout_sec,
        "whisper_model": settings.whisper_model,
        "whisper_device": settings.whisper_device,
        "whisper_compute_type": settings.whisper_compute_type,
        "whisper_cpu_threads": settings.whisper_cpu_threads,
        "storage_dir": str(settings.storage_dir),
        "max_upload_mb": settings.max_upload_mb,
        "max_duration_sec": settings.max_duration_sec,
        "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
        "allowed_mime_types": sorted(ALLOWED_MIME_TYPES),
        "max_concurrent_jobs": settings.max_concurrent_jobs,
    }
