import json
import subprocess
from pathlib import Path

from app.core.config import settings

PROBE_TIMEOUT_SECONDS = 120


class ProbeError(RuntimeError):
    """Raised when ffprobe is missing, times out, or the file is not valid media."""


def _parse_frame_rate(rate: str | None) -> float | None:
    if not rate:
        return None
    if rate in {"0/0", "0"}:
        return None
    try:
        numerator, _, denominator = rate.partition("/")
        denominator = denominator or "1"
        value = float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError):
        return None
    return value if value > 0 else None


def probe_media(path: Path) -> dict:
    """Return {duration_sec, width, height, fps, video_codec, audio_codec}.

    Raises ProbeError on failure. Never uses a shell; arguments are passed as a list.
    """
    command = [
        settings.ffprobe_path,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, timeout=PROBE_TIMEOUT_SECONDS, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProbeError(f"ffprobe could not run: {exc}") from exc

    if completed.returncode != 0:
        stderr = completed.stderr.decode(errors="replace").strip()
        raise ProbeError(f"ffprobe failed: {stderr[:500]}")

    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError(f"ffprobe returned invalid JSON: {exc}") from exc

    streams = data.get("streams") or []
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video_stream is None:
        raise ProbeError("No video stream found in file")

    duration_raw = (data.get("format") or {}).get("duration") or video_stream.get("duration")
    try:
        duration_sec = float(duration_raw) if duration_raw is not None else None
    except (TypeError, ValueError):
        duration_sec = None

    return {
        "duration_sec": duration_sec,
        "width": int(video_stream["width"]) if video_stream.get("width") else None,
        "height": int(video_stream["height"]) if video_stream.get("height") else None,
        "fps": _parse_frame_rate(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")),
        "video_codec": video_stream.get("codec_name"),
        "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
    }
