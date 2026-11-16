"""Face detection and tracking using the YuNet ONNX model (onnxruntime).

The YuNet model exported from opencv_zoo (face_detection_yunet_2023mar) does
NOT return a single [1,N,15] tensor. It returns raw anchor grids per stride:

    input:  [1, 3, 640, 640]  float32, BGR, 0-255 scale, no mean subtraction
    cls_8/16/32:  [1, 6400|1600|400, 1]
    obj_8/16/32:  [1, ... , 1]
    bbox_8/16/32: [1, ... , 4]
    kps_8/16/32:  [1, ... , 10]

Decode follows OpenCV's face_detection_yunet.cpp:
    score = sqrt(cls * obj)
    cx = bbox[0] + c*stride      (prior x)
    cy = bbox[1] + r*stride      (prior y)
    w  = exp(bbox[2]) * stride
    h  = exp(bbox[3]) * stride

Frames are fed with letterbox padding so aspect ratio is preserved; boxes are
mapped back to original pixel coordinates. No video or audio leaves the machine.
"""

import json
import logging
import math
from pathlib import Path
from typing import Any

import av
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

MODEL_INPUT = 640
STRIDES = (8, 16, 32)
NMS_IOU_THRESH = 0.3


def _model_path() -> Path:
    return Path(settings.face_model_path)


def model_available() -> bool:
    return _model_path().is_file()


def _get_session():
    import onnxruntime as ort

    return ort.InferenceSession(str(_model_path()), providers=["CPUExecutionProvider"])


def _letterbox(frame_bgr: np.ndarray) -> tuple[np.ndarray, float, int, int]:
    """Resize preserving aspect ratio, pad to MODEL_INPUT x MODEL_INPUT.

    Returns (padded_float32_chw, scale, pad_x, pad_y).
    """
    h, w = frame_bgr.shape[:2]
    if h == 0 or w == 0:
        raise ValueError("Empty frame")

    scale = min(MODEL_INPUT / w, MODEL_INPUT / h)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))

    # Nearest-neighbour keeps this dependency-free (no OpenCV needed).
    ys = (np.arange(new_h) * (h / new_h)).astype(np.int32)
    xs = (np.arange(new_w) * (w / new_w)).astype(np.int32)
    resized = frame_bgr[ys][:, xs]

    canvas = np.zeros((MODEL_INPUT, MODEL_INPUT, 3), dtype=np.float32)
    canvas[:new_h, :new_w] = resized.astype(np.float32)
    chw = np.transpose(canvas, (2, 0, 1))[None, ...]
    return chw, scale, 0, 0


def _nms(boxes: list[tuple[float, float, float, float]], scores: list[float], thresh: float) -> list[int]:
    """Greedy NMS over (x, y, w, h) boxes. Returns kept indices."""
    order = sorted(range(len(boxes)), key=lambda i: scores[i], reverse=True)
    kept: list[int] = []
    while order:
        i = order.pop(0)
        kept.append(i)
        xi, yi, wi, hi = boxes[i]
        remaining = []
        for j in order:
            xj, yj, wj, hj = boxes[j]
            ix1, iy1 = max(xi, xj), max(yi, yj)
            ix2, iy2 = min(xi + wi, xj + wj), min(yi + hi, yj + hj)
            iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
            inter = iw * ih
            union = wi * hi + wj * hj - inter
            if union <= 0 or inter / union <= thresh:
                remaining.append(j)
        order = remaining
    return kept


def _decode(outputs: list[np.ndarray], scale: float, conf_thresh: float, orig_w: int, orig_h: int) -> list[dict[str, Any]]:
    """Decode raw YuNet anchor grids into boxes in original pixel coordinates."""
    # Output order is cls_8, cls_16, cls_32, obj_8, ..., bbox_8..., kps_8...
    named = {}
    names = [f"cls_{s}" for s in STRIDES] + [f"obj_{s}" for s in STRIDES] + [
        f"bbox_{s}" for s in STRIDES
    ] + [f"kps_{s}" for s in STRIDES]
    for name, arr in zip(names, outputs):
        named[name] = np.asarray(arr)[0]

    boxes: list[tuple[float, float, float, float]] = []
    scores: list[float] = []

    for stride in STRIDES:
        cls = named[f"cls_{stride}"]
        obj = named[f"obj_{stride}"]
        bbox = named[f"bbox_{stride}"]

        cols = MODEL_INPUT // stride
        rows = MODEL_INPUT // stride
        idx = 0
        for r in range(rows):
            for c in range(cols):
                score = math.sqrt(
                    max(0.0, float(cls[idx, 0])) * max(0.0, float(obj[idx, 0]))
                )
                if score < conf_thresh:
                    idx += 1
                    continue

                cx = float(bbox[idx, 0]) + c * stride
                cy = float(bbox[idx, 1]) + r * stride
                # exp() can overflow on garbage rows; clamp before use.
                bw = math.exp(min(20.0, float(bbox[idx, 2]))) * stride
                bh = math.exp(min(20.0, float(bbox[idx, 3]))) * stride

                x = cx - bw / 2.0
                y = cy - bh / 2.0

                # Map letterboxed coords back to original frame pixels.
                boxes.append((x / scale, y / scale, bw / scale, bh / scale))
                scores.append(score)
                idx += 1

    if not boxes:
        return []

    kept = _nms(boxes, scores, NMS_IOU_THRESH)
    results = []
    for i in kept:
        x, y, w, h = boxes[i]
        # Clamp to frame; drop boxes that ended up mostly outside.
        x = max(0.0, min(x, orig_w))
        y = max(0.0, min(y, orig_h))
        w = max(0.0, min(w, orig_w - x))
        h = max(0.0, min(h, orig_h - y))
        if w < 8 or h < 8:
            continue
        results.append({"box": (x, y, w, h), "conf": float(scores[i])})
    return results


def detect_faces_video(
    video_path: Path,
    sample_fps: float | None = None,
    max_width: int | None = None,
    conf_thresh: float | None = None,
) -> list[dict[str, Any]]:
    """Detect faces at `sample_fps` and return per-frame detections.

    Returns: [{"t": float, "detections": [{"box": (x,y,w,h), "conf": float}]}]
    Empty list means no faces found OR the model is missing (logged as warning).
    """
    sample_fps = sample_fps or settings.face_sample_fps
    conf_thresh = conf_thresh if conf_thresh is not None else settings.face_confidence

    if not model_available():
        logger.warning("Face model missing at %s; skipping detection", _model_path())
        return []

    session = _get_session()
    input_name = session.get_inputs()[0].name
    results: list[dict[str, Any]] = []

    container = None
    try:
        container = av.open(str(video_path))
        stream = container.streams.video[0]
        rate = stream.average_rate or stream.guessed_rate
        fps = float(rate) if rate else 30.0
        if fps <= 0:
            fps = 30.0
        frame_interval = max(1, int(round(fps / sample_fps)))

        frame_idx = 0
        for frame in container.decode(video=0):
            if frame_idx % frame_interval == 0:
                rgb = frame.to_ndarray(format="rgb24")
                bgr = rgb[:, :, ::-1]
                chw, scale, pad_x, pad_y = _letterbox(bgr)
                outputs = session.run(None, {input_name: chw})
                dets = _decode(outputs, scale, conf_thresh, bgr.shape[1], bgr.shape[0])
                if dets:
                    results.append({"t": round(frame_idx / fps, 3), "detections": dets})
            frame_idx += 1
    except Exception:
        logger.exception("Face detection failed for %s", video_path.name)
    finally:
        if container is not None:
            try:
                container.close()
            except Exception:
                pass

    return results


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix1, iy1 = max(ax, bx), max(ay, by)
    ix2, iy2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def cluster_tracks(
    frame_detections: list[dict[str, Any]],
    iou_thresh: float = 0.3,
    max_gap_sec: float = 2.0,
    min_track_sec: float = 0.5,
) -> list[dict[str, Any]]:
    """Greedy IoU tracker: group per-frame detections into identity tracks."""
    tracks: list[dict[str, Any]] = []
    next_id = 0

    for frame_data in frame_detections:
        t = float(frame_data["t"])
        for det in frame_data["detections"]:
            best_iou = 0.0
            best: dict[str, Any] | None = None
            for track in tracks:
                if t - track["last_t"] > max_gap_sec:
                    continue
                iou = _iou(det["box"], track["last_box"])
                if iou > best_iou and iou >= iou_thresh:
                    best_iou = iou
                    best = track

            if best is not None:
                best["last_t"] = t
                best["last_box"] = det["box"]
                best["frames"].append({"t": t, "box": det["box"], "conf": det["conf"]})
            else:
                tracks.append(
                    {
                        "id": next_id,
                        "last_t": t,
                        "last_box": det["box"],
                        "frames": [{"t": t, "box": det["box"], "conf": det["conf"]}],
                    }
                )
                next_id += 1

    # Drop tracks that are too short to be a real person.
    kept = []
    for track in tracks:
        span = track["frames"][-1]["t"] - track["frames"][0]["t"]
        if span >= min_track_sec or len(track["frames"]) >= 3:
            kept.append({"id": track["id"], "frames": track["frames"]})
    return kept


def _cache_file(video_path: Path) -> Path:
    cache_dir = Path(settings.storage_dir) / "face_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{video_path.stem}_faces.json"


def save_face_cache(video_path: Path, tracks: list[dict[str, Any]]) -> Path:
    path = _cache_file(video_path)
    serializable = [
        {
            "id": tr["id"],
            "frames": [
                {"t": f["t"], "box": list(f["box"]), "conf": f["conf"]} for f in tr["frames"]
            ],
        }
        for tr in tracks
    ]
    path.write_text(json.dumps(serializable, ensure_ascii=False), encoding="utf-8")
    return path


def load_face_cache(video_path: Path) -> list[dict[str, Any]] | None:
    path = _cache_file(video_path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for track in data:
        for frame in track.get("frames", []):
            frame["box"] = tuple(frame["box"])
    return data
