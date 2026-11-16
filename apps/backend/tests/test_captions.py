"""Caption ASS generation: readable defaults, size scaling, line wrapping."""

from app.services import captions

SEGMENTS = [
    {
        "start": 1.0,
        "end": 5.0,
        "text": "satu dua tiga empat lima enam",
        "words": [
            {"start": 1.0, "end": 1.4, "text": "satu"},
            {"start": 1.4, "end": 1.8, "text": "dua"},
            {"start": 1.8, "end": 2.4, "text": "tiga"},
            {"start": 2.4, "end": 3.0, "text": "empat"},
            {"start": 3.0, "end": 3.8, "text": "lima"},
            {"start": 3.8, "end": 4.8, "text": "enam"},
        ],
    }
]


def _style_line(ass: str) -> str:
    return next(line for line in ass.splitlines() if line.startswith("Style:"))


def test_presets_are_readable():
    # ASS sizes relative to a 1920px-tall canvas; anything under 50 is unreadable.
    for name, preset in captions.PRESETS.items():
        assert preset["size"] >= 50, name


def test_size_scale_multiplies_font_size_and_outline():
    small, _, _ = captions.build_ass(SEGMENTS, 0, 10, "modern_bold", size_scale=1.0)
    big, _, _ = captions.build_ass(SEGMENTS, 0, 10, "modern_bold", size_scale=1.5)

    base_size = captions.PRESETS["modern_bold"]["size"]
    assert f",{base_size}," in _style_line(small)
    assert f",{round(base_size * 1.5)}," in _style_line(big)


def test_size_scale_clamps_out_of_range_values():
    assert captions.clamp_size_scale(2.5) == captions.MAX_SIZE_SCALE
    assert captions.clamp_size_scale(0.1) == captions.MIN_SIZE_SCALE
    assert captions.clamp_size_scale(None) == 1.0
    assert captions.clamp_size_scale("bogus") == 1.0


def test_long_lines_are_wrapped_with_hard_breaks():
    long_segments = [
        {
            "start": 0.0,
            "end": 5.0,
            "text": "kalimat ini sengaja dibuat sangat panjang supaya pasti harus dibungkus",
            "words": [
                {"start": float(i), "end": float(i) + 0.7, "text": w}
                for i, w in enumerate(
                    "kalimat ini sengaja dibuat sangat panjang supaya pasti harus dibungkus".split()
                )
            ],
        }
    ]
    ass, cue_count, has_estimated = captions.build_ass(long_segments, 0, 5, "modern_bold")
    assert not has_estimated
    assert cue_count > 0
    assert "\\N" in ass


def test_karaoke_preset_emits_cumulative_sweeps():
    ass, cue_count, _ = captions.build_ass(SEGMENTS, 0, 10, "karaoke")
    assert cue_count > 0
    assert "\\kf" in ass


def test_unknown_preset_falls_back_to_modern_bold():
    ass, _, _ = captions.build_ass(SEGMENTS, 0, 10, "does_not_exist")
    assert _style_line(ass).split(",")[1] == captions.PRESETS["modern_bold"]["font"]
