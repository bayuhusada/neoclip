from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin

JOB_KINDS = ("extract_audio", "transcribe", "analyze", "render")
JOB_STATUSES = ("queued", "running", "succeeded", "failed")


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('extract_audio','transcribe','analyze','render')", name="ck_jobs_kind"
        ),
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed')", name="ck_jobs_status"
        ),
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_jobs_progress"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int | None] = mapped_column(
        ForeignKey("videos.id", ondelete="SET NULL"), index=True
    )

    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(Text())

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    video: Mapped["Video"] = relationship(back_populates="jobs")
