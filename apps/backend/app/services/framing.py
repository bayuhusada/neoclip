"""Smart framing: turn face tracks into smooth 9:16 crop keyframes.

Two responsibilities:

1. `generate_framing_keyframes` — decide where to crop over the clip window,
   using clustered face tracks. All coordinates are in SOURCE video pixels.
2. `build_framing_filter` — compile those keyframes into an FFmpeg filter
   string. FFmpeg's `crop` filter evaluates `x`/`y` per frame, so keyframes are
   compiled into a piecewise-linear `if(lt(t,...))` expression. This is cheap
   (no zoompan, no per-frame Python) and produces continuous motion.

Limitation: this cannot know who is actually speaking. It follows the most
prominent face (confidence x area x duration). Manual override is available via
the API by storing keyframes directly on the clip.
"""

import json
import logging
import math
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

OUTPUT_W = 1080
OUTPUT_H = 1920
ASPECT = OUTPUT_W / OUTPUT_H  # 0.5625

# Keep the compiled expression small; more keyframes than this adds nothing.
MAX_EXPR_KEYFRAMES = 80


# --------------------------------------------------------------------------- #
# geometry
# --------------------------------------------------------------------------- #
def crop_size(video_w: int, video_h: int) -> tuple[int, int]:
    """Largest 9:16 rect that fits inside the source frame (even dimensions)."""
    if video_w <= 0 or video_h <= 0:
        return (OUTPUT_W, OUTPUT_H)

    src_ar = video_w / video_h
    if src_ar >= ASPECT:  # wider than 9:16 -> crop width
        ch = video_h
        cw = int(round(ch * ASPECT))
    else:  # taller -> crop height
        cw = video_w
        ch = int(round(cw / ASPECT))

    cw = max(2, min(cw, video_w)) // 2 * 2
    ch = max(2, min(ch, video_h)) // 2 * 2
    return (cw, ch)


def _clamp(v: float, lo: float, hi: float) -> float:
    if hi < lo:
        lo, hi = hi, lo
    return max(lo, min(v, hi))


def _center_keyframes(video_w: int, video_h: int, clip_start: float, clip_end: float) -> list[dict[str, float]]:
    cw, ch = crop_size(video_w, video_h)
    x = (video_w - cw) / 2.0
    y = (video_h - ch) / 2.0
    end = max(0.0, clip_end - clip_start)
    return [
        {"t": 0.0, "x": x, "y": y, "zoom": 1.0},
        {"t": end, "x": x, "y": y, "zoom": 1.0},
    ]


def _smooth(points: list[dict[str, float]], alpha: float = 0.35, max_speed_ratio: float = 0.35) -> list[dict[str, float]]:
    """EMA smoothing plus a speed cap measured in crop-widths per second."""
    if len(points) < 2:
        return points

    out = [dict(points[0])]
    for i in range(1, len(points)):
        prev = out[-1]
        cur = points[i]
        dt = max(1e-3, cur["t"] - prev["t"])
        sx = prev["x"] + (cur["x"] - prev["x"]) * alpha
        sy = prev["y"] + (cur["y"] - prev["y"]) * alpha

        max_step = max_speed_ratio * OUTPUT_W * dt
        dx, dy = sx - prev["x"], sy - prev["y"]
        dist = math.hypot(dx, dy)
        if dist > max_step and dist > 0:
            sx = prev["x"] + dx * (max_step / dist)
            sy = prev["y"] + dy * (max_step / dist)

        out.append({"t": cur["t"], "x": sx, "y": sy, "zoom": cur.get("zoom", 1.0)})
    return out


def _box_area(box: tuple[float, float, float, float]) -> float:
    return max(0.0, box[2]) * max(0.0, box[3])


def _track_keyframes(
    frames: list[dict[str, Any]],
    video_w: int,
    video_h: int,
    clip_start: float,
) -> list[dict[str, float]]:
    cw, ch = crop_size(video_w, video_h)
    max_x = video_w - cw
    max_y = video_h - ch

    points: list[dict[str, float]] = []
    for f in frames:
        rel_t = float(f["t"]) - clip_start
        if rel_t < 0:
            continue
        bx, by, bw, bh = f["box"]
        cx = bx + bw / 2.0
        cy = by + bh / 2.0
        # Put the face slightly above center: headroom looks more natural.
        target_cy = cy - bh * 0.15
        x = _clamp(cx - cw / 2.0, 0.0, max_x)
        y = _clamp(target_cy - ch / 2.0, 0.0, max_y)
        points.append({"t": rel_t, "x": x, "y": y, "zoom": 1.0})

    if not points:
        return []
    return _smooth(points)


def resolve_clip_mode(
    tracks: list[dict[str, Any]],
    video_w: int,
    video_h: int,
    clip_start: float,
    clip_end: float,
    requested: str = "smart_auto",
) -> str:
    """Turn a requested camera mode into the effective one for this window.

    `smart_auto` inspects face counts over time:
      - two people talking the whole time  -> `split`
      - one person talking the whole time  -> `single`
      - many faces / group laughter        -> `group`
    Any other requested mode is returned unchanged (manual override).
    """
    if requested != "smart_auto":
        return requested
    return _resolve_mode(tracks, clip_start, clip_end, video_w, video_h)


def generate_framing_keyframes(
    tracks: list[dict[str, Any]],
    video_w: int,
    video_h: int,
    clip_start: float,
    clip_end: float,
    mode: str = "auto_speaker",
) -> list[dict[str, float]]:
    """Produce crop keyframes (source pixel coords) for one clip window."""
    if mode == "original" or not tracks:
        return _center_keyframes(video_w, video_h, clip_start, clip_end)

    if mode == "smart_auto":
        mode = _resolve_mode(tracks, clip_start, clip_end, video_w, video_h)
        if mode == "original":
            return _center_keyframes(video_w, video_h, clip_start, clip_end)

    if mode in ("split", "split_stacked"):
        # Split screen needs a two-crop graph; a single-crop caller still gets
        # valid keyframes by following the primary face (see build_split_filter
        # for the actual side-by-side or stacked render).
        scored = []
        for track in tracks:
            frames = [f for f in track.get("frames", []) if clip_start <= float(f["t"]) <= clip_end]
            if not frames:
                continue
            avg_conf = sum(float(f["conf"]) for f in frames) / len(frames)
            avg_area = sum(_box_area(f["box"]) for f in frames) / len(frames)
            span = float(frames[-1]["t"]) - float(frames[0]["t"])
            scored.append({"frames": frames, "score": avg_conf * avg_area * max(1.0, span)})
        if len(scored) >= 2:
            primary = max(scored, key=lambda item: item["score"])
            keyframes = _track_keyframes(primary["frames"], video_w, video_h, clip_start)
            return keyframes or _center_keyframes(video_w, video_h, clip_start, clip_end)
        return _center_keyframes(video_w, video_h, clip_start, clip_end)

    if mode == "group":
        return _union_keyframes(tracks, clip_start, clip_end, video_w, video_h)

    # "single" and "auto_speaker": follow the dominant face.
    scored = []
    for track in tracks:
        frames = [f for f in track.get("frames", []) if clip_start <= float(f["t"]) <= clip_end]
        if not frames:
            continue
        avg_conf = sum(float(f["conf"]) for f in frames) / len(frames)
        avg_area = sum(_box_area(f["box"]) for f in frames) / len(frames)
        span = float(frames[-1]["t"]) - float(frames[0]["t"])
        scored.append(
            {
                "frames": frames,
                "score": avg_conf * avg_area * max(1.0, span),
            }
        )

    if not scored:
        return _center_keyframes(video_w, video_h, clip_start, clip_end)

    primary = max(scored, key=lambda item: item["score"])
    keyframes = _track_keyframes(primary["frames"], video_w, video_h, clip_start)
    if not keyframes:
        return _center_keyframes(video_w, video_h, clip_start, clip_end)
    return keyframes


def _strip_size(video_w: int, video_h: int) -> tuple[int, int]:
    """Portrait strip size for one half of a side-by-side split screen."""
    half_w = OUTPUT_W // 2  # 540
    strip_w = max(2, int(round(video_h * (half_w / OUTPUT_H))))
    return (strip_w, max(2, int(round(video_h))))


# Stacked split: two full-width bands, each half of the 9:16 frame (1080x960).
STACK_BAND_W = OUTPUT_W
STACK_BAND_H = OUTPUT_H // 2
STACK_ASPECT = STACK_BAND_W / STACK_BAND_H  # 1.125


def stacked_crop_size(video_w: int, video_h: int) -> tuple[int, int]:
    """Largest 1080:960 rect that fits inside the source frame (even dims)."""
    if video_w <= 0 or video_h <= 0:
        return (STACK_BAND_W, STACK_BAND_H)
    if video_w / video_h >= STACK_ASPECT:  # wider than the band -> crop width
        ch = video_h
        cw = int(round(ch * STACK_ASPECT))
    else:  # taller -> crop height
        cw = video_w
        ch = int(round(cw / STACK_ASPECT))
    cw = max(2, min(cw, video_w)) // 2 * 2
    ch = max(2, min(ch, video_h)) // 2 * 2
    return (cw, ch)


def _union_keyframes(
    tracks: list[dict[str, Any]],
    clip_start: float,
    clip_end: float,
    video_w: int,
    video_h: int,
) -> list[dict[str, float]]:
    """Crop keyframes that follow the union of all active faces.

    Used by the smart/auto modes: one face → tight follow; many faces → widen
    to cover the group (laughter / group conversation), then tighten again.
    """
    cw, ch = crop_size(video_w, video_h)
    events: list[tuple[float, float, float, float]] = []  # (t, minX, maxX, minY+maxY mid)
    for track in tracks:
        frames = [f for f in track.get("frames", []) if clip_start <= float(f["t"]) <= clip_end]
        for f in frames:
            rel_t = float(f["t"]) - clip_start
            bx, by, bw, bh = f["box"]
            events.append((rel_t, bx, bx + bw, by + bh / 2.0))

    if not events:
        return _center_keyframes(video_w, video_h, clip_start, clip_end)

    events.sort(key=lambda e: e[0])
    points: list[dict[str, float]] = []
    for i, (t, x0, x1, y) in enumerate(events):
        if i > 0 and abs(t - events[i - 1][0]) < 1e-6:
            continue
        cx = (x0 + x1) / 2.0
        x = _clamp(cx - cw / 2.0, 0.0, max(0.0, video_w - cw))
        y = _clamp(y - ch / 2.0, 0.0, max(0.0, video_h - ch))
        if not points or points[-1]["t"] != t:
            points.append({"t": t, "x": x, "y": y, "zoom": 1.0})

    if not points:
        return _center_keyframes(video_w, video_h, clip_start, clip_end)
    return _smooth(points)


def generate_split_keyframes(
    tracks: list[dict[str, Any]],
    clip_start: float,
    clip_end: float,
    video_w: int,
    video_h: int,
    stacked: bool = False,
) -> tuple[list[dict[str, float]], list[dict[str, float]]]:
    """Pick the two highest-scored distinct faces and build strip keyframes.

    `stacked=False` -> side-by-side strips (each 540x1920), y stays at 0.
    `stacked=True`  -> top/bottom bands (each 1080x960), x and y follow the face.
    """
    scored = []
    for track in tracks:
        frames = [f for f in track.get("frames", []) if clip_start <= float(f["t"]) <= clip_end]
        if not frames:
            continue
        avg_conf = sum(float(f["conf"]) for f in frames) / len(frames)
        avg_area = sum(_box_area(f["box"]) for f in frames) / len(frames)
        span = float(frames[-1]["t"]) - float(frames[0]["t"])
        scored.append((track, avg_conf * avg_area * max(1.0, span)))
    scored.sort(key=lambda item: item[1], reverse=True)

    if len(scored) < 2:
        return [], []

    if stacked:
        crop_w, crop_h = stacked_crop_size(video_w, video_h)
    else:
        crop_w, crop_h = _strip_size(video_w, video_h)

    max_x = max(0.0, video_w - crop_w)
    max_y = max(0.0, video_h - crop_h)

    result: list[list[dict[str, float]]] = [[], []]
    for idx, (track, _) in enumerate(scored[:2]):
        points: list[dict[str, float]] = []
        for f in track.get("frames", []):
            rel_t = float(f["t"]) - clip_start
            if rel_t < 0:
                continue
            bx, by, bw, bh = f["box"]
            cx = bx + bw / 2.0
            cy = by + bh / 2.0
            x = _clamp(cx - crop_w / 2.0, 0.0, max_x)
            if stacked:
                # Put the face slightly above the band center: headroom looks natural.
                y = _clamp(cy - bh * 0.15 - crop_h / 2.0, 0.0, max_y)
            else:
                y = 0.0
            points.append({"t": rel_t, "x": x, "y": y, "zoom": 1.0})
        result[idx] = _smooth(points) if points else _center_keyframes(video_w, video_h, clip_start, clip_end)

    return result[0], result[1]


def _resolve_mode(
    tracks: list[dict[str, Any]],
    clip_start: float,
    clip_end: float,
    video_w: int,
    video_h: int,
) -> str:
    """Decide the effective framing mode for a clip window from face tracks."""
    duration = max(0.0, clip_end - clip_start)
    if not tracks or duration <= 0:
        return "original"

    bucket_sec = 1.0
    n_buckets = max(1, int(duration / bucket_sec) + 1)
    counts = [0] * n_buckets
    for track in tracks:
        frames = [f for f in track.get("frames", []) if clip_start <= float(f["t"]) <= clip_end]
        if not frames:
            continue
        for f in frames:
            rel = float(f["t"]) - clip_start
            idx = min(n_buckets - 1, int(rel / bucket_sec))
            counts[idx] += 1

    if not any(counts):
        return "original"

    max_count = max(counts)
    two_ratio = sum(1 for c in counts if c >= 2) / len(counts)
    three_ratio = sum(1 for c in counts if c >= 3) / len(counts)
    one_ratio = sum(1 for c in counts if c == 1) / len(counts)

    if max_count >= 2 and two_ratio >= 0.55 and three_ratio <= 0.25:
        return "split"
    if three_ratio >= 0.2 or (max_count >= 2 and two_ratio >= 0.25):
        # Multiple faces present -> show the group (covers laughter / group chat).
        # One face keeps cropping tight (handled by single/group keyframe logic).
        return "group"
    if one_ratio >= 0.5:
        return "single"
    return "group"


# --------------------------------------------------------------------------- #
# FFmpeg compilation
# --------------------------------------------------------------------------- #
def _piecewise(points: list[tuple[float, float]], fallback: float) -> str:
    """Nested if() expression giving linear interpolation over time t."""
    if not points:
        return f"{fallback:.2f}"
    if len(points) == 1:
        return f"{points[0][1]:.2f}"

    expr = f"{points[-1][1]:.2f}"
    for i in range(len(points) - 2, -1, -1):
        t0, v0 = points[i]
        t1, v1 = points[i + 1]
        dt = max(1e-3, t1 - t0)
        slope = (v1 - v0) / dt
        seg = f"({v0:.2f}+{slope:.4f}*(t-{t0:.3f}))"
        expr = f"if(lt(t,{t1:.3f}),{seg},{expr})"
    first_t, first_v = points[0]
    return f"if(lt(t,{first_t:.3f}),{first_v:.2f},{expr})"


def _downsample(points: list[dict[str, float]], limit: int = MAX_EXPR_KEYFRAMES) -> list[dict[str, float]]:
    if len(points) <= limit:
        return points
    step = len(points) / float(limit)
    out = [points[int(i * step)] for i in range(limit)]
    if out[-1] is not points[-1]:
        out[-1] = points[-1]
    return out


def build_framing_filter(
    keyframes: list[dict[str, float]],
    video_w: int,
    video_h: int,
) -> str:
    """Return `crop+scale` filter segment (no leading comma)."""
    cw, ch = crop_size(video_w, video_h)

    if not keyframes:
        return (
            f"crop={cw}:{ch},scale={OUTPUT_W}:{OUTPUT_H}:flags=lanczos,setsar=1"
        )

    pts = _downsample(sorted(keyframes, key=lambda k: float(k["t"])))
    xs = [(float(k["t"]), float(k["x"])) for k in pts]
    ys = [(float(k["t"]), float(k["y"])) for k in pts]
    center_x = (video_w - cw) / 2.0
    center_y = (video_h - ch) / 2.0

    x_expr = _piecewise(xs, center_x)
    y_expr = _piecewise(ys, center_y)

    return (
        f"crop={cw}:{ch}:x='{x_expr}':y='{y_expr}',"
        f"scale={OUTPUT_W}:{OUTPUT_H}:flags=lanczos,setsar=1"
    )


def build_split_filter(
    left_keyframes: list[dict[str, float]],
    right_keyframes: list[dict[str, float]],
    video_w: int,
    video_h: int,
    stacked: bool = False,
) -> str:
    """9:16 split screen from two face crops.

    `stacked=False` -> side-by-side: two portrait strips (540x1920) hstacked.
    `stacked=True`  -> top/bottom: two wide bands (1080x960) vstacked.

    Returns a filter graph producing an unlabeled final stream (caller appends
    subtitle filters then `[v]`). Coordinates are source pixels, y is top.
    """
    if stacked:
        crop_w, crop_h = stacked_crop_size(video_w, video_h)
    else:
        crop_w, crop_h = _strip_size(video_w, video_h)

    max_x = max(0.0, video_w - crop_w)
    max_y = max(0.0, video_h - crop_h) if stacked else 0.0

    def _expr(
        keyframes: list[dict[str, float]], axis: str, limit: float, fallback: float
    ) -> str:
        if not keyframes:
            return f"{fallback:.2f}"
        pts = _downsample(sorted(keyframes, key=lambda k: float(k["t"])))
        vals = [
            (float(k["t"]), _clamp(float(k.get(axis, 0.0)), 0.0, limit)) for k in pts
        ]
        return _piecewise(vals, fallback)

    left_x = _expr(left_keyframes, "x", max_x, (video_w - crop_w) / 2.0)
    right_x = _expr(right_keyframes, "x", max_x, (video_w - crop_w) / 2.0)

    if stacked:
        band_w = STACK_BAND_W
        band_h = STACK_BAND_H
        left_y = _expr(left_keyframes, "y", max_y, (video_h - crop_h) / 2.0)
        right_y = _expr(right_keyframes, "y", max_y, (video_h - crop_h) / 2.0)
        top_chain = (
            f"[0:v]crop={crop_w}:{crop_h}:x='{left_x}':y='{left_y}',"
            f"scale={band_w}:{band_h}:flags=lanczos,setsar=1[spt]"
        )
        bottom_chain = (
            f"[0:v]crop={crop_w}:{crop_h}:x='{right_x}':y='{right_y}',"
            f"scale={band_w}:{band_h}:flags=lanczos,setsar=1[spb]"
        )
        return f"{top_chain};{bottom_chain};[spt][spb]vstack=inputs=2"

    half_w = OUTPUT_W // 2
    left_chain = (
        f"[0:v]crop={crop_w}:{crop_h}:x='{left_x}':y=0,"
        f"scale={half_w}:{OUTPUT_H}:flags=lanczos,setsar=1[spl]"
    )
    right_chain = (
        f"[0:v]crop={crop_w}:{crop_h}:x='{right_x}':y=0,"
        f"scale={half_w}:{OUTPUT_H}:flags=lanczos,setsar=1[spr]"
    )
    return f"{left_chain};{right_chain};[spl][spr]hstack=inputs=2"


# --------------------------------------------------------------------------- #
# cache helpers (used by the framing API)
# --------------------------------------------------------------------------- #
def _cache_file(clip_id: int) -> Path:
    cache_dir = Path(settings.storage_dir) / "framing_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"clip_{clip_id}_framing.json"


def save_framing_cache(clip_id: int, keyframes: list[dict[str, float]]) -> Path:
    path = _cache_file(clip_id)
    payload = [
        {
            "t": float(k["t"]),
            "x": float(k["x"]),
            "y": float(k["y"]),
            "zoom": float(k.get("zoom", 1.0)),
        }
        for k in keyframes
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def load_framing_cache(clip_id: int) -> list[dict[str, float]] | None:
    path = _cache_file(clip_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, list):
        return None
    return data
