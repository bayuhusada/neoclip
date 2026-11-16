"""Build SRT subtitles for a clip from the stored transcript segments."""

from typing import Any


def _srt_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    millis = int(round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def segments_to_srt(
    segments: list[dict[str, Any]] | None,
    start_sec: float,
    end_sec: float,
) -> tuple[str, int]:
    """Return (srt_text, cue_count) for the part of `segments` inside the clip.

    Timestamps are shifted so the first cue starts at 0 — the clip is rendered
    with `-ss`, so its own timeline starts at zero. Segments that only partially
    overlap are clamped; segments entirely outside the window are skipped.
    """
    if not segments:
        return "", 0

    cues: list[tuple[float, float, str]] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        text = (segment.get("text") or "").strip()
        if not text:
            continue
        try:
            seg_start = float(segment.get("start"))
            seg_end = float(segment.get("end"))
        except (TypeError, ValueError):
            continue

        # Clamp to the clip window.
        clamped_start = max(seg_start, start_sec)
        clamped_end = min(seg_end, end_sec)
        if clamped_end <= clamped_start:
            continue

        cues.append((clamped_start - start_sec, clamped_end - start_sec, text))

    if not cues:
        return "", 0

    cues.sort(key=lambda cue: cue[0])

    blocks = []
    for index, (cue_start, cue_end, text) in enumerate(cues, start=1):
        blocks.append(
            f"{index}\n{_srt_time(cue_start)} --> {_srt_time(cue_end)}\n{text}\n"
        )
    return "\n".join(blocks), len(cues)