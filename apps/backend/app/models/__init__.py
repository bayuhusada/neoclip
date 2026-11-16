"""SQLAlchemy models. Importing this package registers every table on Base.metadata."""

from app.models.clip import CAMERA_MODES, CAPTION_PRESETS, CLIP_STATUSES, Clip
from app.models.job import JOB_KINDS, JOB_STATUSES, Job
from app.models.project import Project
from app.models.transcript import Transcript
from app.models.video import VIDEO_STATUSES, Video

__all__ = [
    "CAMERA_MODES",
    "CAPTION_PRESETS",
    "CLIP_STATUSES",
    "Clip",
    "JOB_KINDS",
    "JOB_STATUSES",
    "Job",
    "Project",
    "Transcript",
    "VIDEO_STATUSES",
    "Video",
]
