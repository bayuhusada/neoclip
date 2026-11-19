import pytest

from app.services.youtube_transcript import (
    extract_video_id,
    merge_youtube_with_whisper,
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("not a url", None),
        (None, None),
    ],
)
def test_extract_video_id(url, expected):
    assert extract_video_id(url) == expected


def test_merge_keeps_whisper_timings():
    whisper = [
        {"start": 0.0, "duration": 1.0, "text": "hello world"},
        {"start": 1.5, "duration": 1.0, "text": "goodbye world"},
    ]
    yt = [
        {"start": 0.0, "duration": 1.0, "text": "Hello World!"},
        {"start": 1.5, "duration": 1.0, "text": "Goodbye World!"},
    ]
    merged = merge_youtube_with_whisper(whisper, yt)
    assert [s["text"] for s in merged] == ["Hello World!", "Goodbye World!"]
    assert merged[0]["start"] == 0.0
    assert merged[0]["duration"] == 1.0


def test_merge_ignores_no_match():
    whisper = [{"start": 0.0, "duration": 1.0, "text": "completely unrelated"}]
    yt = [{"start": 0.0, "duration": 1.0, "text": "something else"}]
    merged = merge_youtube_with_whisper(whisper, yt)
    assert len(merged) == 1
    assert merged[0]["text"] == "completely unrelated"
