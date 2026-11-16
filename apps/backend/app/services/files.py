import uuid
from pathlib import Path

from app.core.config import settings

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv"}
ALLOWED_MIME_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-matroska",
    "video/mpeg",
    "application/octet-stream",  # some browsers/clients omit the real video MIME
}


class FileRejected(Exception):
    """Raised when an upload violates extension, MIME, or size rules."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def validate_upload(original_filename: str, content_type: str | None) -> str:
    """Validate extension and MIME type. Returns the normalized extension."""
    suffix = Path(original_filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise FileRejected(f"Extension '{suffix or '(none)'}' is not allowed. Use MP4/MOV/MKV.")

    if content_type and content_type not in ALLOWED_MIME_TYPES:
        raise FileRejected(f"MIME type '{content_type}' is not accepted as video.")

    return suffix


def unique_stored_name(original_filename: str, suffix: str) -> str:
    """Return a flat, collision-safe filename inside uploads/, never trusting the original name."""
    return f"{uuid.uuid4().hex[:12]}{suffix}"


def max_upload_bytes() -> int:
    return settings.max_upload_mb * 1024 * 1024


def upload_limits() -> dict:
    """Limits the UI shows before a file is picked."""
    return {
        "max_upload_mb": settings.max_upload_mb,
        "max_duration_sec": settings.max_duration_sec,
        "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
    }


def _unlink_quiet(path: Path) -> None:
    """Remove a file if it exists; never fail the DB delete on a missing file."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _safe_storage_path(relative_path: str) -> Path | None:
    """Resolve a DB path and refuse anything outside storage_dir."""
    base = Path(settings.storage_dir).resolve()
    target = (base / relative_path).resolve()
    if not target.is_relative_to(base):
        return None
    return target


def delete_video_files(video) -> None:
    """Remove every file that belongs to a video: upload, cached WAV, clip outputs.

    Paths stored in the DB are relative to ``settings.storage_dir``.
    Never touches ``storage/models`` (shared Whisper weights).
    """
    stored = _safe_storage_path(video.stored_path)
    if stored is not None:
        _unlink_quiet(stored)

    _unlink_quiet(settings.audio_dir / f"{video.id}.wav")

    for clip in getattr(video, "clips", []):
        if clip.output_path:
            output = _safe_storage_path(clip.output_path)
            if output is not None:
                _unlink_quiet(output)
        if clip.subtitle_path:
            subtitle = _safe_storage_path(clip.subtitle_path)
            if subtitle is not None:
                _unlink_quiet(subtitle)


def write_upload_to_disk(upload_file, destination: Path) -> int:
    """Stream an UploadFile to disk in chunks. Returns bytes written.

    Raises FileRejected if the upload exceeds settings.max_upload_mb.
    """
    limit = max_upload_bytes()
    total = 0
    with destination.open("wb") as out:
        while True:
            chunk = upload_file.file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                out.close()
                destination.unlink(missing_ok=True)
                raise FileRejected(
                    f"File exceeds the {settings.max_upload_mb} MB limit.", status_code=413
                )
            out.write(chunk)
    return total
