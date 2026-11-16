from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models.video import Video
from app.models.project import Project
from app.schemas import VideoRead
from app.services.files import (
    FileRejected,
    delete_video_files,
    unique_stored_name,
    validate_upload,
    write_upload_to_disk,
)
from app.services.probe import ProbeError, probe_media

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post("", response_model=VideoRead, status_code=201)
def upload_video(
    project_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # Validate cheap rules before touching the database or disk.
    try:
        suffix = validate_upload(file.filename or "", file.content_type)
    except FileRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    stored_name = unique_stored_name(file.filename or "", suffix)
    stored_path = settings.uploads_dir / stored_name

    try:
        size_bytes = write_upload_to_disk(file, stored_path)
    except FileRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    finally:
        file.file.close()

    video = Video(
        project_id=project.id,
        original_filename=file.filename or stored_name,
        stored_path=f"uploads/{stored_name}",
        size_bytes=size_bytes,
        mime_type=file.content_type,
        status="probing",
    )
    db.add(video)
    db.commit()

    absolute_path = Path(settings.storage_dir) / video.stored_path
    try:
        metadata = probe_media(absolute_path)
    except ProbeError as exc:
        video.status = "failed"
        video.error = str(exc)[:1000]
    else:
        duration = metadata["duration_sec"]
        if settings.max_duration_sec and duration and duration > settings.max_duration_sec:
            # Reject after probing so the user gets the real duration in the message.
            absolute_path.unlink(missing_ok=True)
            db.delete(video)
            db.commit()
            limit_min = settings.max_duration_sec / 60
            actual_min = duration / 60
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Durasi video {actual_min:.1f} menit melebihi batas "
                    f"{limit_min:.0f} menit. Potong dulu atau naikkan MAX_DURATION_SEC."
                ),
            )
        video.status = "ready"
        video.duration_sec = metadata["duration_sec"]
        video.width = metadata["width"]
        video.height = metadata["height"]
        video.fps = metadata["fps"]
        video.video_codec = metadata["video_codec"]
        video.audio_codec = metadata["audio_codec"]
        video.error = None

    db.commit()
    db.refresh(video)
    return video


@router.get("", response_model=list[VideoRead])
def list_videos(project_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Video).order_by(Video.created_at.desc())
    if project_id is not None:
        query = query.filter(Video.project_id == project_id)
    return query.all()


@router.get("/{video_id}", response_model=VideoRead)
def get_video(video_id: int, db: Session = Depends(get_db)):
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
    return video


@router.delete("/{video_id}", status_code=204)
def delete_video(video_id: int, db: Session = Depends(get_db)):
    """Delete a video plus its files. Transcript and clips cascade in the DB."""
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    delete_video_files(video)
    db.delete(video)
    db.commit()
    return Response(status_code=204)
