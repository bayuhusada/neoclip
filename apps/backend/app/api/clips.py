from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import Clip, Job, Transcript, Video
from app.schemas import ClipRead
from app.services.captions import PRESETS as CAPTION_PRESETS
from app.services.files import _safe_storage_path, _unlink_quiet
from app.services.render import TEMPLATES, RenderError, render_thumbnail
from app.services.worker import start_worker

router = APIRouter(tags=["clips"])

PENDING_STATUSES = ("queued", "running")
EDITABLE_STATUSES = ("candidate", "approved")
CAMERA_MODES = ("original", "smart_auto", "auto_speaker", "single", "split", "split_stacked", "group", "dynamic_zoom")


class ClipUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    hook: str | None = Field(default=None, max_length=2000)
    rationale: str | None = Field(default=None, max_length=2000)
    start_sec: float | None = Field(default=None, ge=0)
    end_sec: float | None = Field(default=None, gt=0)
    score: float | None = Field(default=None, ge=0, le=1)
    status: str | None = None
    template: str | None = None
    caption_preset: str | None = None
    caption_size: float | None = Field(default=None, ge=0.6, le=1.8)
    camera_mode: str | None = None
    framing: list | None = None
    hook_enabled: bool | None = None
    hook_duration: float | None = None


@router.post("/videos/{video_id}/analyze")
def start_analysis(video_id: int, response: Response, db: Session = Depends(get_db)):
    """Enqueue an AI analysis job that proposes candidate clips.

    202 = job baru, 200 = job analyze masih jalan, 409 = belum ada transkrip.
    """
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    transcript = db.scalar(select(Transcript).where(Transcript.video_id == video_id))
    if transcript is None:
        raise HTTPException(
            status_code=409,
            detail="Belum ada transkrip. Jalankan transkripsi dulu sebelum analisis AI.",
        )

    pending = db.scalar(
        select(Job).where(
            Job.video_id == video_id,
            Job.kind == "analyze",
            Job.status.in_(PENDING_STATUSES),
        )
    )
    if pending is not None:
        response.status_code = 200
        return {
            "message": "Analysis already queued or running",
            "job_id": pending.id,
            "video_id": video_id,
            "status": pending.status,
        }

    job = Job(
        video_id=video_id,
        kind="analyze",
        status="queued",
        payload={"video_id": video_id},
    )
    db.add(job)
    db.commit()

    start_worker()

    response.status_code = 202
    return {"message": "Analysis queued", "job_id": job.id, "video_id": video_id}


@router.get("/videos/{video_id}/clips", response_model=list[ClipRead])
def list_clips(video_id: int, db: Session = Depends(get_db)):
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
    return db.scalars(
        select(Clip)
        .where(Clip.video_id == video_id)
        .order_by(Clip.score.desc(), Clip.start_sec.asc())
    ).all()


@router.patch("/clips/{clip_id}", response_model=ClipRead)
def update_clip(clip_id: int, payload: ClipUpdate, db: Session = Depends(get_db)):
    clip = db.get(Clip, clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail=f"Clip {clip_id} not found")

    if clip.status not in EDITABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Clip dengan status '{clip.status}' tidak bisa diubah.",
        )

    if payload.status is not None:
        if payload.status not in EDITABLE_STATUSES:
            raise HTTPException(
                status_code=400,
                detail="Status hanya boleh 'candidate' atau 'approved'.",
            )
        clip.status = payload.status

    for field in ("title", "hook", "rationale", "start_sec", "end_sec", "score", "template"):
        value = getattr(payload, field)
        if value is not None:
            if field == "template" and value not in TEMPLATES:
                raise HTTPException(status_code=400, detail=f"Template '{value}' tidak dikenal.")
            setattr(clip, field, value)

    if payload.caption_preset is not None:
        if payload.caption_preset not in CAPTION_PRESETS:
            raise HTTPException(
                status_code=400,
                detail=f"Caption preset '{payload.caption_preset}' tidak dikenal.",
            )
        clip.caption_preset = payload.caption_preset

    if payload.caption_size is not None:
        clip.caption_size = float(payload.caption_size)

    if payload.camera_mode is not None:
        if payload.camera_mode not in CAMERA_MODES:
            raise HTTPException(
                status_code=400,
                detail=f"Camera mode '{payload.camera_mode}' tidak dikenal.",
            )
        clip.camera_mode = payload.camera_mode

    if payload.framing is not None:
        clip.framing = payload.framing or None

    if payload.hook_enabled is not None:
        clip.hook_enabled = bool(payload.hook_enabled)

    if payload.hook_duration is not None:
        clip.hook_duration = min(max(float(payload.hook_duration), 0.5), 10.0)

    if clip.end_sec <= clip.start_sec:
        raise HTTPException(status_code=400, detail="end_sec harus lebih besar dari start_sec.")

    db.commit()
    db.refresh(clip)
    return clip


@router.delete("/clips/{clip_id}")
def delete_clip(clip_id: int, db: Session = Depends(get_db)):
    clip = db.get(Clip, clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail=f"Clip {clip_id} not found")

    for relative in (clip.output_path, clip.subtitle_path):
        if relative:
            target = _safe_storage_path(relative)
            if target is not None:
                _unlink_quiet(target)

    db.delete(clip)
    db.commit()
    return {"deleted": clip_id}


@router.post("/clips/{clip_id}/render")
def start_render(clip_id: int, response: Response, db: Session = Depends(get_db)):
    """Enqueue a high-quality 9:16 render job for the approved clip."""
    clip = db.get(Clip, clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail=f"Clip {clip_id} not found")

    if clip.status not in ("approved", "rendered", "failed"):
        raise HTTPException(
            status_code=409, detail="Hanya klip yang disetujui (Approved) yang bisa dirender."
        )

    pending = db.scalar(
        select(Job).where(
            Job.video_id == clip.video_id,
            Job.kind == "render",
            Job.status.in_(PENDING_STATUSES),
            Job.payload["clip_id"].as_integer() == clip_id,
        )
    )
    if pending is not None:
        response.status_code = 200
        return {"message": "Render already queued", "job_id": pending.id}

    job = Job(
        video_id=clip.video_id,
        kind="render",
        status="queued",
        payload={"clip_id": clip_id},
    )
    db.add(job)
    db.commit()

    start_worker()
    response.status_code = 202
    return {"message": "Render queued", "job_id": job.id}


@router.get("/clips/{clip_id}/video")
def download_clip(clip_id: int, db: Session = Depends(get_db)):
    clip = db.get(Clip, clip_id)
    if clip is None or not clip.output_path:
        raise HTTPException(status_code=404, detail="Klip belum dirender.")

    path = _safe_storage_path(clip.output_path)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="File hasil render tidak ditemukan di disk.")

    return FileResponse(path, media_type="video/mp4", filename=f"{clip.id}.mp4")


@router.get("/clips/{clip_id}/thumbnail")
def get_clip_thumbnail(clip_id: int, db: Session = Depends(get_db)):
    clip = db.get(Clip, clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip not found")

    thumb_name = f"clip_{clip.id}.jpg"
    thumb_path = settings.thumbnails_dir / thumb_name

    if not thumb_path.exists():
        video = db.get(Video, clip.video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video source not found")
        try:
            render_thumbnail(
                video_path=Path(settings.storage_dir) / video.stored_path,
                output_path=thumb_path,
                at_sec=clip.start_sec,
            )
        except RenderError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return FileResponse(thumb_path, media_type="image/jpeg")

