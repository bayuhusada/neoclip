import subprocess
from pathlib import Path

from app.core.config import settings

AUDIO_TIMEOUT_SECONDS = 300


class AudioExtractionError(RuntimeError):
    """Raised when audio extraction fails or ffprobe/ffmpeg errors out."""


def extract_audio_wav(video_path: Path, output_wav_path: Path) -> Path:
    """Extract 16 kHz mono WAV audio from a video file.

    Never uses shell=True. Re-encodes audio to PCM 16-bit mono at 16000 Hz,
    which is the ideal input format for Whisper.
    """
    output_wav_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        settings.ffmpeg_path,
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(output_wav_path),
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, timeout=AUDIO_TIMEOUT_SECONDS, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AudioExtractionError(f"ffmpeg could not run: {exc}") from exc

    if completed.returncode != 0:
        stderr = completed.stderr.decode(errors="replace").strip()
        raise AudioExtractionError(f"Audio extraction failed: {stderr[:500]}")

    if not output_wav_path.exists() or output_wav_path.stat().st_size == 0:
        raise AudioExtractionError("Audio extraction produced an empty or missing file")

    return output_wav_path
