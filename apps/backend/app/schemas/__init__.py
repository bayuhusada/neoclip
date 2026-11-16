from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class ProjectRead(ORMModel):
    id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class VideoRead(ORMModel):
    id: int
    project_id: int
    original_filename: str
    stored_path: str
    size_bytes: int
    mime_type: str | None
    duration_sec: float | None
    width: int | None
    height: int | None
    fps: float | None
    video_codec: str | None
    audio_codec: str | None
    status: str
    error: str | None
    created_at: datetime
    updated_at: datetime


class TranscriptSegment(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    text: str


class TranscriptRead(ORMModel):
    id: int
    video_id: int
    language: str | None
    model_name: str
    duration_sec: float | None
    text: str
    segments: list[TranscriptSegment]
    created_at: datetime


class ClipCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)
    hook: str | None = None
    rationale: str | None = None
    score: float | None = Field(default=None, ge=0, le=100)


class ClipRead(ORMModel):
    id: int
    video_id: int
    title: str
    hook: str | None
    rationale: str | None
    start_sec: float
    end_sec: float
    score: float | None
    status: str
    template: str
    caption_preset: str
    caption_size: float = 1.0
    caption_source: str
    camera_mode: str
    framing_mode: str | None = None
    framing: list | None = None
    hook_enabled: bool = False
    hook_duration: float = 3.0
    output_path: str | None
    subtitle_path: str | None
    error: str | None
    created_at: datetime


class JobRead(ORMModel):
    id: int
    video_id: int | None
    kind: str
    status: str
    progress: int
    payload: dict
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
