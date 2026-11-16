from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Job, Transcript, Video
from app.schemas import TranscriptRead
from app.services.worker import start_worker

router = APIRouter(prefix="/videos", tags=["transcribe"])

PENDING_STATUSES = ("queued", "running")


@router.post("/{video_id}/transcribe")
def start_transcription(
    video_id: int,
    response: Response,
    force: bool = False,
    db: Session = Depends(get_db),
):
    """Enqueue a transcription job for the given video.

    202 = job baru dibuat, 200 = sudah ada transcript atau job masih berjalan.
    `force=true` re-runs the worker even when a transcript exists (used by the
    "Transkripsi ulang" button to regenerate word-level timestamps).
    Status per cabang di-set eksplisit; `status_code` di dekorator akan menimpa
    semua cabang dan itu yang dulu membuat respons idempoten salah kode.
    """
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    existing = db.scalar(select(Transcript).where(Transcript.video_id == video_id))
    if existing is not None and not force:
        response.status_code = 200
        return {
            "message": "Transcript already exists",
            "video_id": video_id,
            "transcript_id": existing.id,
        }

    pending = db.scalar(
        select(Job).where(
            Job.video_id == video_id,
            Job.kind == "transcribe",
            Job.status.in_(PENDING_STATUSES),
        )
    )
    if pending is not None:
        response.status_code = 200
        return {
            "message": "Transcription already queued or running",
            "job_id": pending.id,
            "video_id": video_id,
            "status": pending.status,
        }

    job = Job(
        video_id=video_id,
        kind="transcribe",
        status="queued",
        payload={"video_id": video_id},
    )
    db.add(job)
    db.commit()

    start_worker()

    response.status_code = 202
    return {"message": "Transcription queued", "job_id": job.id, "video_id": video_id}


@router.get("/{video_id}/transcript", response_model=TranscriptRead)
def get_transcript(video_id: int, db: Session = Depends(get_db)):
    """Get the transcript for a video (if exists)."""
    transcript = db.scalar(select(Transcript).where(Transcript.video_id == video_id))
    if transcript is None:
        raise HTTPException(status_code=404, detail=f"No transcript for video {video_id}")
    return transcript


@router.get("/{video_id}/jobs")
def list_video_jobs(video_id: int, db: Session = Depends(get_db)):
    """List all jobs for a video (useful for polling)."""
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
    jobs = db.scalars(
        select(Job).where(Job.video_id == video_id).order_by(Job.created_at.desc())
    ).all()
    return [
        {
            "id": job.id,
            "kind": job.kind,
            "status": job.status,
            "progress": job.progress,
            "error": job.error,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
        }
        for job in jobs
    ]
