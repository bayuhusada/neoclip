"""Smart framing API: inspect and edit crop keyframes for a clip.

Auto keyframes are produced at render time from detected faces. This router
lets the UI preview them, override them manually, or ask for a fresh detection
pass. All work stays local; nothing is uploaded anywhere.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import CAMERA_MODES, Clip, Video
from app.services.face_tracking import (
    cluster_tracks,
    detect_faces_video,
    load_face_cache,
    save_face_cache,
)
from app.services.framing import (
    generate_framing_keyframes,
    generate_split_keyframes,
    load_framing_cache,
    resolve_clip_mode,
    save_framing_cache,
)

router = APIRouter(tags=["framing"])


class Keyframe(BaseModel):
    t: float = Field(ge=0)
    x: float
    y: float
    zoom: float = 1.0


class FramingUpdate(BaseModel):
    camera_mode: str | None = None
    keyframes: list[Keyframe] | None = None


class FramingRead(BaseModel):
    clip_id: int
    camera_mode: str
    resolved_mode: str
    video_width: int | None
    video_height: int | None
    keyframes: list[Keyframe]
    split: list[list[Keyframe]] | None = None
    source: str  # "manual" | "cache" | "auto" | "none"


def _get_clip(clip_id: int, db: Session) -> Clip:
    clip = db.get(Clip, clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail=f"Clip {clip_id} not found")
    return clip


def _get_video(clip: Clip, db: Session) -> Video:
    video = db.get(Video, clip.video_id)
    if video is None:
        raise HTTPException(status_code=404, detail=f"Video {clip.video_id} not found")
    return video


def _load_tracks(clip: Clip, video: Video, refresh: bool = False) -> list[dict]:
    video_path = Path(settings.storage_dir) / video.stored_path
    if not refresh:
        tracks = load_face_cache(video_path)
        if tracks:
            return tracks
    detections = detect_faces_video(video_path)
    tracks = cluster_tracks(detections)
    if tracks:
        try:
            save_face_cache(video_path, tracks)
        except OSError:
            pass
    return tracks


def _build(
    clip: Clip, video: Video, tracks: list[dict], requested: str
) -> tuple[str, list[dict], list[list[dict]] | None]:
    """Resolve the effective mode and compute (keyframes, split)."""
    video_w = video.width or 1920
    video_h = video.height or 1080
    if not tracks:
        return "original", [], None

    resolved = resolve_clip_mode(
        tracks, video_w, video_h, clip.start_sec, clip.end_sec, requested
    )
    if resolved in ("split", "split_stacked"):
        left, right = generate_split_keyframes(
            tracks,
            clip.start_sec,
            clip.end_sec,
            video_w,
            video_h,
            stacked=resolved == "split_stacked",
        )
        if left and right:
            return resolved, left, [left, right]
        resolved = "single"
    keyframes = generate_framing_keyframes(
        tracks, video_w, video_h, clip.start_sec, clip.end_sec, resolved
    )
    return resolved, keyframes, None


@router.get("/clips/{clip_id}/framing", response_model=FramingRead)
def get_framing(clip_id: int, db: Session = Depends(get_db)):
    clip = _get_clip(clip_id, db)
    video = _get_video(clip, db)
    requested = clip.camera_mode or "original"

    if clip.framing:
        # Manual override stored on the clip.
        keyframes = clip.framing
        resolved = clip.framing_mode or requested
        return FramingRead(
            clip_id=clip.id,
            camera_mode=requested,
            resolved_mode=resolved,
            video_width=video.width,
            video_height=video.height,
            keyframes=keyframes,
            split=None,
            source="manual",
        )

    tracks = _load_tracks(clip, video)
    resolved, keyframes, split = _build(clip, video, tracks, requested)
    source = "auto" if tracks else "none"
    return FramingRead(
        clip_id=clip.id,
        camera_mode=requested,
        resolved_mode=resolved,
        video_width=video.width,
        video_height=video.height,
        keyframes=keyframes or [],
        split=split,
        source=source,
    )


@router.put("/clips/{clip_id}/framing", response_model=FramingRead)
def update_framing(clip_id: int, payload: FramingUpdate, db: Session = Depends(get_db)):
    clip = _get_clip(clip_id, db)
    video = _get_video(clip, db)

    if payload.camera_mode is not None:
        if payload.camera_mode not in CAMERA_MODES:
            raise HTTPException(
                status_code=400,
                detail=f"Camera mode '{payload.camera_mode}' tidak dikenal.",
            )
        clip.camera_mode = payload.camera_mode
        clip.framing_mode = None

    if payload.keyframes is not None:
        keyframes = [k.model_dump() for k in payload.keyframes]
        clip.framing = keyframes or None
        if keyframes:
            save_framing_cache(clip.id, keyframes)

    db.commit()
    db.refresh(clip)

    tracks = _load_tracks(clip, video)
    resolved, keyframes, split = _build(clip, video, tracks, clip.camera_mode or "original")
    if clip.framing:
        return FramingRead(
            clip_id=clip.id,
            camera_mode=clip.camera_mode or "original",
            resolved_mode=clip.framing_mode or resolved,
            video_width=video.width,
            video_height=video.height,
            keyframes=clip.framing,
            split=None,
            source="manual",
        )
    return FramingRead(
        clip_id=clip.id,
        camera_mode=clip.camera_mode or "original",
        resolved_mode=resolved,
        video_width=video.width,
        video_height=video.height,
        keyframes=keyframes or [],
        split=split,
        source="auto" if tracks else "none",
    )


@router.post("/clips/{clip_id}/framing/regenerate", response_model=FramingRead)
def regenerate_framing(clip_id: int, db: Session = Depends(get_db)):
    """Recompute auto keyframes from a fresh face-detection pass."""
    clip = _get_clip(clip_id, db)
    video = _get_video(clip, db)

    tracks = _load_tracks(clip, video, refresh=True)
    resolved, keyframes, split = _build(
        clip, video, tracks, clip.camera_mode or "original"
    )

    # Fresh detection overrides any previous manual keyframe override.
    clip.framing = None
    if keyframes:
        save_framing_cache(clip.id, keyframes)
    db.commit()
    db.refresh(clip)

    return FramingRead(
        clip_id=clip.id,
        camera_mode=clip.camera_mode or "original",
        resolved_mode=resolved,
        video_width=video.width,
        video_height=video.height,
        keyframes=keyframes or [],
        split=split,
        source="auto" if tracks else "none",
    )
