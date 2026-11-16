from pathlib import Path
from typing import Any
from faster_whisper import WhisperModel

from app.core.config import settings

_model_instance: WhisperModel | None = None


def get_whisper_model() -> WhisperModel:
    """Return a singleton instance of WhisperModel, loading it lazily.

    Models are downloaded to settings.whisper_download_root.
    """
    global _model_instance
    if _model_instance is not None:
        return _model_instance

    download_root = Path(settings.whisper_download_root)
    download_root.mkdir(parents=True, exist_ok=True)

    _model_instance = WhisperModel(
        settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
        cpu_threads=settings.whisper_cpu_threads,
        download_root=str(download_root),
    )
    return _model_instance


def transcribe_audio_file(wav_path: Path) -> tuple[str, str | None, list[dict[str, Any]]]:
    """Transcribe a WAV file using faster-whisper.

    Returns:
        (full_text, detected_language, segments_list)
    """
    model = get_whisper_model()
    segments_gen, info = model.transcribe(
        str(wav_path),
        beam_size=settings.whisper_beam_size,
        vad_filter=True,
        word_timestamps=True,
    )

    segments = []
    text_parts = []
    for seg in segments_gen:
        words = []
        if seg.words:
            for w in seg.words:
                words.append({
                    "start": round(float(w.start), 2),
                    "end": round(float(w.end), 2),
                    "text": w.word.strip(),
                })

        segment_data = {
            "start": round(float(seg.start), 2),
            "end": round(float(seg.end), 2),
            "text": seg.text.strip(),
            "words": words,
        }
        segments.append(segment_data)
        text_parts.append(seg.text.strip())

    full_text = " ".join(text_parts)
    language = getattr(info, "language", None)
    return full_text, language, segments
