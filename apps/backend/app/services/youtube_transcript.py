"""YouTube Transcript fetch and merge helper.

Fetches automatic captions from YouTube and merges with Whisper segments.
Only the text content is borrowed from YouTube, preserving all timestamps
and word timings from the local Whisper model.
"""

from __future__ import annotations

import re
from typing import Any

# Direct import avoids runtime dependency when not used
# youtube_transcript_api must be installed for this feature.


def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats.
    
    Supports:
    - youtube.com/watch?v=ID
    - youtube.com/embed/ID
    - youtube.com/shorts/ID
    - youtu.be/ID
    - m.youtube.com/watch?v=ID
    """
    if not url:
        return None

    url = url.strip()

    # youtu.be/ID
    if "youtu.be" in url:
        match = re.search(r"youtu\.be/([^/?&]+)", url)
        if match:
            return match.group(1)

    # youtube.com/watch?v=ID, youtube.com/v/ID, youtube.com/embed/ID
    patterns = [
        r"/watch\?v=([^&]+)",
        r"/v/([^/?&]+)",
        r"/embed/([^/?&]+)",
        r"/shorts/([^/?&]+)",
        r"/live/([^/?&]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


def fetch_segments(video_id: str, langs: list[str] | None = None) -> list[dict[str, Any]]:
    """Fetch transcript segments from YouTube.

    Returns list of dicts with 'text', 'start', 'duration' keys.
    Empty list means no caption available or fetch failed.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        if langs:
            return YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
        return YouTubeTranscriptApi.get_transcript(video_id)
    except Exception:
        return []


def merge_youtube_with_whisper(
    whisper_segments: list[dict[str, Any]],
    youtube_segments: list[dict[str, Any]],
    confidence_threshold: float = 0.6,
) -> list[dict[str, Any]]:
    """Merge YouTube text into Whisper segments while keeping Whisper timing.

    Strategy:
    1. For each Whisper segment, find YouTube segments that overlap temporally.
    2. Use YouTube text when semantic overlap is high (case-insensitive substring).
    3. Keep Whisper timestamp, confidence, and word-level info.

    This improves transcription quality without losing word-level timing.
    """
    if not youtube_segments:
        return whisper_segments

    result = []
    yt_idx = 0

    # Sort YouTube segments by start time
    yt_sorted = sorted(youtube_segments, key=lambda s: s.get("start", 0))

    for ws in whisper_segments:
        seg = dict(ws)
        w_start = ws.get("start", 0)
        w_end = w_start + ws.get("duration", 0)

        # Find YouTube segment temporally closest
        best_match = None
        best_score = 0.0

        for yt in yt_sorted:
            yt_start = yt.get("start", 0)
            yt_end = yt_start + yt.get("duration", 0)

            # Temporal overlap check
            overlap = max(0, min(w_end, yt_end) - max(w_start, yt_start))
            if overlap <= 0:
                continue

            # Semantic similarity
            w_text = ws.get("text", "").lower()
            yt_text = yt.get("text", "").lower()

            if w_text in yt_text or yt_text in w_text:
                score = 0.9
            elif len(w_text) > 2 and w_text in yt_text:
                score = 0.8
            else:
                continue

            if score > best_score:
                best_score = score
                best_match = yt

        # Apply YouTube text if confidence is high enough
        if best_match and best_score >= confidence_threshold:
            seg["text"] = best_match["text"]

        result.append(seg)

    return result


def get_youtube_transcript_info(url: str) -> dict[str, Any] | None:
    """Get metadata about YouTube captions (availability, language options).

    Returns:
        dict with 'available': bool, 'languages': list, 'video_id': str
        None if URL invalid or fetch failed.
    """
    video_id = extract_video_id(url)
    if not video_id:
        return None

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api.formatters import HTMLFormatter

        # Find available languages
        available = YouTubeTranscriptApi.list_transcripts(video_id)
        langs = []
        for t in available:
            langs.append(t.language_code)

        return {"video_id": video_id, "available": True, "languages": langs}
    except Exception:
        return None