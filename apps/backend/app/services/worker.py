import asyncio
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select

from app.core.config import settings
from app.db import SessionLocal
from app.models import Clip, Job, Transcript, Video
from app.services.analyzer import analyze_transcript
from app.services.audio import extract_audio_wav
from app.services.face_tracking import cluster_tracks, detect_faces_video, load_face_cache, save_face_cache
from app.services.framing import generate_framing_keyframes, save_framing_cache
from app.services.render import normalize_template, render_clip
from app.services.subtitles import segments_to_srt
from app.services.transcriber import transcribe_audio_file

_worker_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()

# Progress checkpoints so the UI can show something meaningful.
PROGRESS_EXTRACT = 25
PROGRESS_TRANSCRIBE = 50
PROGRESS_SAVE = 85
PROGRESS_DONE = 100

# Analyze checkpoints
PROGRESS_ANALYZE_SEND = 10
PROGRESS_ANALYZE_PARSE = 50


class VideoHasNoAudio(RuntimeError):
    """Raised when the probed video has no audio stream to transcribe."""


def _error_text(exc: Exception) -> str:
    """Include the exception class; httpx timeouts stringify to "" so a bare
    `str(exc)` produced "Cannot reach AI endpoint:" with nothing after it."""
    detail = str(exc).strip()
    name = type(exc).__name__
    return f"{name}: {detail}" if detail else name


def _mark_failed(db, job: Job, message: str) -> None:
    db.rollback()
    job.status = "failed"
    job.progress = 0
    job.error = message[:1000]
    job.finished_at = datetime.now(timezone.utc)
    db.commit()


def _process_transcribe_job(db, job: Job) -> bool:
    """Process one transcribe job.

    Marks the job `failed` itself when anything goes wrong, so callers only need
    to log. Returns True on success, False on failure.
    """
    try:
        video_id = job.payload.get("video_id")
        if not video_id:
            raise ValueError("Job payload missing video_id")

        video = db.get(Video, video_id)
        if video is None:
            raise ValueError(f"Video {video_id} not found")

        # Fail fast: ffprobe already told us whether an audio stream exists.
        if not video.audio_codec:
            raise VideoHasNoAudio("Video has no audio stream; transcription skipped")

        job.status = "running"
        job.progress = PROGRESS_EXTRACT
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        video_path = Path(settings.storage_dir) / video.stored_path
        audio_dir = settings.audio_dir
        audio_dir.mkdir(parents=True, exist_ok=True)
        wav_path = audio_dir / f"{video_id}.wav"

        extract_audio_wav(video_path, wav_path)

        job.progress = PROGRESS_TRANSCRIBE
        db.commit()

        text, language, segments = transcribe_audio_file(wav_path)

        job.progress = PROGRESS_SAVE
        db.commit()

        transcript = db.scalar(select(Transcript).where(Transcript.video_id == video_id))
        if transcript is None:
            transcript = Transcript(
                video_id=video_id,
                model_name=settings.whisper_model,
                language=language,
                duration_sec=video.duration_sec,
                text=text,
                segments=segments,
            )
            db.add(transcript)
        else:
            transcript.text = text
            transcript.language = language
            transcript.segments = segments
            transcript.model_name = settings.whisper_model
            transcript.duration_sec = video.duration_sec

        # The WAV is regenerable; keep only the DB row to save disk.
        try:
            wav_path.unlink(missing_ok=True)
        except OSError:
            pass

        job.progress = PROGRESS_DONE
        job.status = "succeeded"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        return True
    except Exception as exc:  # noqa: BLE001 - job boundary, must not kill the worker
        _mark_failed(db, job, _error_text(exc))
        return False


def _process_analyze_job(db, job: Job) -> bool:
    """Process one analyze job: call AI with transcript and create candidate Clips."""
    try:
        video_id = job.payload.get("video_id")
        if not video_id:
            raise ValueError("Job payload missing video_id")

        video = db.get(Video, video_id)
        if video is None:
            raise ValueError(f"Video {video_id} not found")

        transcript = db.scalar(select(Transcript).where(Transcript.video_id == video_id))
        if transcript is None:
            raise ValueError("Belum ada transkrip; jalankan transkripsi dulu.")

        job.progress = PROGRESS_ANALYZE_SEND
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        # Call AI analyzer; this is an async call wrapped in asyncio.run()
        clips_data = asyncio.run(
            analyze_transcript(transcript.text, transcript.duration_sec or video.duration_sec or 0.0)
        )

        job.progress = PROGRESS_ANALYZE_PARSE
        db.commit()

        # Replace any previous candidate clips for this video
        for existing in db.scalars(
            select(Clip).where(Clip.video_id == video_id, Clip.status == "candidate")
        ).all():
            db.delete(existing)

        # Insert new candidate clips, clamped to the real video duration.
        max_duration = transcript.duration_sec or video.duration_sec
        for data in clips_data:
            start = float(data["start_sec"])
            end = float(data["end_sec"])
            if max_duration:
                start = min(start, max(max_duration - 1.0, 0.0))
                end = min(end, max_duration)
            if end <= start:
                continue
            db.add(
                Clip(
                    video_id=video_id,
                    status="candidate",
                    title=data["title"],
                    hook=data.get("hook"),
                    start_sec=start,
                    end_sec=end,
                    score=float(data.get("score") or 0.5),
                    rationale=data.get("rationale"),
                )
            )

        job.progress = PROGRESS_DONE
        job.status = "succeeded"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        return True
    except Exception as exc:  # noqa: BLE001 - job boundary, must not kill the worker
        _mark_failed(db, job, _error_text(exc))
        return False


def _process_render_job(db, job: Job) -> bool:
    """Render one approved clip to 9:16 with burned-in subtitles."""
    try:
        clip_id = job.payload.get("clip_id")
        if not clip_id:
            raise ValueError("Job payload missing clip_id")

        clip = db.get(Clip, clip_id)
        if clip is None:
            raise ValueError(f"Clip {clip_id} not found")

        video = db.get(Video, clip.video_id)
        if video is None:
            raise ValueError(f"Video {clip.video_id} not found")

        job.status = "running"
        job.progress = 10
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        template = normalize_template(clip.template)

        # Subtitles are derived data: rebuild every render so manual start/end
        # edits are always reflected in the burned-in text.
        # Prefer ASS (animated word-level captions) when segments have `words`,
        # fall back to SRT otherwise.
        subtitle_rel = None
        ass_rel = None
        caption_source = "estimated"
        transcript = db.scalar(select(Transcript).where(Transcript.video_id == video.id))
        if transcript is not None:
            from app.services.captions import build_ass

            caption_preset = getattr(clip, "caption_preset", "modern_bold") or "modern_bold"
            caption_size = getattr(clip, "caption_size", 1.0)
            try:
                ass_text, cue_count, has_estimated = build_ass(
                    transcript.segments,
                    clip.start_sec,
                    clip.end_sec,
                    caption_preset,
                    size_scale=caption_size,
                )
            except Exception:
                ass_text, cue_count, has_estimated = "", 0, True

            if cue_count > 0:
                caption_source = "estimated" if has_estimated else "words"
                settings.subtitles_dir.mkdir(parents=True, exist_ok=True)
                ass_path = settings.subtitles_dir / f"{clip.id}.ass"
                ass_path.write_text(ass_text, encoding="utf-8")
                ass_rel = f"subtitles/{clip.id}.ass"
            else:
                srt_text, cue_count = segments_to_srt(
                    transcript.segments, clip.start_sec, clip.end_sec
                )
                if cue_count:
                    caption_source = "estimated"
                    settings.subtitles_dir.mkdir(parents=True, exist_ok=True)
                    srt_path = settings.subtitles_dir / f"{clip.id}.srt"
                    srt_path.write_text(srt_text, encoding="utf-8")
                    subtitle_rel = f"subtitles/{clip.id}.srt"

        # Phase 2: Smart framing (face detection + crop keyframes).
        # Load existing face cache or detect from video (sample low fps).
        video_path = Path(settings.storage_dir) / video.stored_path
        tracks = cluster_tracks([])
        cache = None
        try:
            cache = load_face_cache(video_path)
            if cache:
                tracks = cache
        except Exception:
            pass

        if not tracks and clip.camera_mode != "original":
            # Detect faces at low sample rate (video might be long).
            detections = detect_faces_video(video_path, sample_fps=2.0, max_width=1280)
            tracks = cluster_tracks(detections)
            if tracks:
                # Cache so later renders/settings reuse the detection.
                try:
                    save_face_cache(video_path, tracks)
                except Exception:
                    pass

        keyframes = []
        framing_split = None
        split_stacked = False
        resolved_mode = clip.camera_mode or "original"
        video_w = video.width if video.width is not None else 1920
        video_h = video.height if video.height is not None else 1080
        if tracks and resolved_mode != "original":
            from app.services.framing import (
                generate_split_keyframes,
                resolve_clip_mode,
            )

            # Turn "smart_auto" into a concrete mode for this window.
            resolved_mode = resolve_clip_mode(
                tracks, video_w, video_h, clip.start_sec, clip.end_sec, resolved_mode
            )
            if resolved_mode in ("split", "split_stacked"):
                split_stacked = resolved_mode == "split_stacked"
                left, right = generate_split_keyframes(
                    tracks,
                    clip.start_sec,
                    clip.end_sec,
                    video_w,
                    video_h,
                    stacked=split_stacked,
                )
                if left and right:
                    framing_split = (left, right)
                    keyframes = left  # store left as the single-keyframe fallback
                else:
                    resolved_mode = "single"
                    split_stacked = False
                    keyframes = generate_framing_keyframes(
                        tracks, video_w, video_h, clip.start_sec, clip.end_sec, "single"
                    )
            else:
                keyframes = generate_framing_keyframes(
                    tracks, video_w, video_h, clip.start_sec, clip.end_sec, resolved_mode
                )
            # Save framing cache for later re-use.
            save_framing_cache(clip.id, keyframes)

        job.progress = 40
        db.commit()

        # OpenShorts-style hook: burn the AI title line for the first seconds.
        # A hook failure must never fail the render.
        hook_rel = None
        hook_duration = 3.0
        if getattr(clip, "hook_enabled", False) and clip.hook:
            from app.services.hooks import write_hook_text

            try:
                hook_rel = write_hook_text(clip.id, clip.hook)
                hook_duration = float(getattr(clip, "hook_duration", 3.0) or 3.0)
            except Exception:  # noqa: BLE001 - optional overlay
                hook_rel = None

        output_name = f"{clip.id}.mp4"
        output_path = settings.clips_dir / output_name
        render_clip(
            video_path=Path(settings.storage_dir) / video.stored_path,
            output_path=output_path,
            start_sec=clip.start_sec,
            end_sec=clip.end_sec,
            subtitle_rel=subtitle_rel,
            ass_rel=ass_rel,
            template=template,
            framing=keyframes,
            video_w=video_w,
            video_h=video_h,
            framing_split=framing_split,
            split_stacked=split_stacked,
            hook_rel=hook_rel,
            hook_duration=hook_duration,
        )

        clip.output_path = f"clips/{output_name}"
        clip.subtitle_path = ass_rel or subtitle_rel
        clip.caption_source = caption_source
        clip.template = template
        clip.status = "rendered"
        clip.error = None
        clip.framing_mode = resolved_mode if resolved_mode != "original" else None
        clip.framing = keyframes if keyframes else None

        job.progress = PROGRESS_DONE
        job.status = "succeeded"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        return True
    except Exception as exc:  # noqa: BLE001 - job boundary, must not kill the worker
        _mark_failed(db, job, _error_text(exc))
        clip_id = job.payload.get("clip_id")
        if clip_id:
            clip = db.get(Clip, clip_id)
            if clip is not None:
                clip.status = "failed"
                clip.error = _error_text(exc)[:1000]
                db.commit()
        return False


def _worker_loop():
    """Pick up queued transcribe, analyze, or render jobs and process them one at a time."""
    while not _stop_event.is_set():
        try:
            with SessionLocal() as db:
                job = db.scalar(
                    select(Job)
                    .where(
                        Job.status == "queued",
                        Job.kind.in_(("transcribe", "analyze", "render")),
                    )
                    .order_by(Job.created_at)
                )
                if job is None:
                    time.sleep(1)
                    continue

                kind = job.kind
                if kind == "transcribe":
                    ok = _process_transcribe_job(db, job)
                elif kind == "analyze":
                    ok = _process_analyze_job(db, job)
                elif kind == "render":
                    ok = _process_render_job(db, job)
                else:
                    ok = False

                if not ok:
                    print(f"[worker] Job {job.id} ({kind}) failed: {job.error}")

        except Exception:  # noqa: BLE001 - never let the loop die silently
            traceback.print_exc()
            time.sleep(1)


def start_worker():
    """Start the background worker thread (idempotent)."""
    global _worker_thread
    if _worker_thread is not None and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_worker_loop, name="neoclip-worker", daemon=True)
    _worker_thread.start()
    print("[worker] Started")


def stop_worker(timeout: float = 5.0):
    """Signal the worker to stop and wait for the current job to end."""
    global _worker_thread
    if _worker_thread is None:
        return
    _stop_event.set()
    _worker_thread.join(timeout=timeout)
    _worker_thread = None
    print("[worker] Stopped")