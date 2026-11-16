import subprocess

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["system"])


def _probe_version(executable: str) -> bool:
    """Run `<executable> -version` without a shell and report success."""
    try:
        completed = subprocess.run(
            [executable, "-version"],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


@router.get("/health")
def health():
    return {
        "status": "ok",
        "services": {
            "ffmpeg": _probe_version(settings.ffmpeg_path),
            "ffprobe": _probe_version(settings.ffprobe_path),
            "storage": settings.storage_dir.is_dir(),
        },
    }
