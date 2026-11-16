from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin

CLIP_STATUSES = ("candidate", "approved", "rendered", "failed")
CAPTION_PRESETS = (
    "modern_bold",
    "karaoke",
    "minimal",
    "podcast",
    "hormozi",
    "classic",
    "anton",
    "pill",
    "oneword",
)
CAMERA_MODES = (
    "original",
    "smart_auto",
    "single",
    "split",
    "split_stacked",
    "group",
    "auto_speaker",
    "dynamic_zoom",
)


class Clip(TimestampMixin, Base):
    __tablename__ = "clips"
    __table_args__ = (
        CheckConstraint(
            "status IN ('candidate','approved','rendered','failed')", name="ck_clips_status"
        ),
        CheckConstraint("end_sec > start_sec", name="ck_clips_range"),
        CheckConstraint("start_sec >= 0", name="ck_clips_start_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    hook: Mapped[str | None] = mapped_column(Text())
    rationale: Mapped[str | None] = mapped_column(Text())
    start_sec: Mapped[float] = mapped_column(Float(), nullable=False)
    end_sec: Mapped[float] = mapped_column(Float(), nullable=False)
    score: Mapped[float | None] = mapped_column(Float())

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="candidate")
    # Render style preset; see app.services.render.TEMPLATES
    template: Mapped[str] = mapped_column(String(30), nullable=False, default="clean")
    # Animated captions (Phase 1): preset key + where timings came from
    caption_preset: Mapped[str] = mapped_column(String(30), nullable=False, default="modern_bold")
    # Per-clip font size multiplier (0.6-1.8); 1.0 = preset default
    caption_size: Mapped[float] = mapped_column(
        Float(), nullable=False, default=1.0, server_default="1.0"
    )
    caption_source: Mapped[str] = mapped_column(String(20), nullable=False, default="estimated")
    # Hook overlay: FFmpeg drawtext based, disabled by default, duration in seconds
    hook_enabled: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    hook_duration: Mapped[float] = mapped_column(Float(), nullable=False, default=3.0)
    # Smart framing (Phase 2): camera mode + manual/auto keyframes (source px)
    camera_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="smart_auto")
    # Resolved mode after smart_auto is evaluated at render time (split/single/group)
    framing_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    framing: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Paths relative to settings.storage_dir
    output_path: Mapped[str | None] = mapped_column(String(1000))
    subtitle_path: Mapped[str | None] = mapped_column(String(1000))
    error: Mapped[str | None] = mapped_column(Text())

    video: Mapped["Video"] = relationship(back_populates="clips")
