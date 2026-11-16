"""Split-screen geometry: side-by-side and stacked variants."""

from app.services import framing


def test_stacked_crop_size_is_band_aspect():
    # 1920x1080 source -> 1080x960 band aspect (1.125) -> ~1214x1080 (even dims)
    assert framing.stacked_crop_size(1920, 1080) == (1214, 1080)


def test_side_by_side_split_uses_hstack():
    graph = framing.build_split_filter([], [], 1920, 1080)
    assert "hstack=inputs=2" in graph
    assert "vstack" not in graph
    # Each half is 540 wide, full 1920 tall.
    assert "scale=540:1920" in graph


def test_stacked_split_uses_vstack_and_band_height():
    graph = framing.build_split_filter([], [], 1920, 1080, stacked=True)
    assert "vstack=inputs=2" in graph
    assert "hstack" not in graph
    assert "scale=1080:960" in graph
    assert "crop=1214:1080" in graph


def test_stacked_keyframes_follow_face_vertically():
    tracks = [
        {
            "frames": [
                {"t": 0.0, "box": [100, 100, 200, 400], "conf": 0.9},
                {"t": 0.5, "box": [100, 100, 200, 400], "conf": 0.9},
            ]
        },
        {
            "frames": [
                {"t": 0.0, "box": [400, 1200, 200, 400], "conf": 0.8},
                {"t": 0.5, "box": [400, 1200, 200, 400], "conf": 0.8},
            ]
        },
    ]
    # Use vertical source 1080x1920 so vertical crop headroom exists
    left, right = framing.generate_split_keyframes(
        tracks, 0.0, 1.0, 1080, 1920, stacked=True
    )
    assert left and right
    assert all(k["y"] >= 0 for k in left + right)
    assert any(k["y"] > 0 for k in left + right)


def test_side_by_side_keyframes_keep_y_at_zero():
    tracks = [
        {"frames": [{"t": 0.0, "box": [100, 100, 200, 200], "conf": 0.9}]},
        {"frames": [{"t": 0.0, "box": [1400, 700, 200, 200], "conf": 0.8}]},
    ]
    left, right = framing.generate_split_keyframes(tracks, 0.0, 1.0, 1920, 1080)
    assert left and right
    assert all(k["y"] == 0.0 for k in left + right)
