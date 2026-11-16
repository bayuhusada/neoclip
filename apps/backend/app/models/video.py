from sqlalchemy import BigInteger, CheckConstraint, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin

VIDEO_STATUSES = ("uploaded", "probing", "ready", "failed")


class Video(TimestampMixin, Base):
    __tablename__ = "videos"
    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded','probing','ready','failed')", name="ck_videos_status"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )

    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    # Path relative to settings.storage_dir, e.g. "uploads/3f2a.mp4"
    stored_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    mime_type: Mapped[str | None] = mapped_column(String(120))

    duration_sec: Mapped[float | None] = mapped_column(Float())
    width: Mapped[int | None] = mapped_column(Integer())
    height: Mapped[int | None] = mapped_column(Integer())
    fps: Mapped[float | None] = mapped_column(Float())
    video_codec: Mapped[str | None] = mapped_column(String(50))
    audio_codec: Mapped[str | None] = mapped_column(String(50))

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="uploaded")
    error: Mapped[str | None] = mapped_column(Text())

    project: Mapped["Project"] = relationship(back_populates="videos")
    transcripts: Mapped[list["Transcript"]] = relationship(
        back_populates="video", cascade="all, delete-orphan", passive_deletes=True
    )
    clips: Mapped[list["Clip"]] = relationship(
        back_populates="video", cascade="all, delete-orphan", passive_deletes=True
    )
    jobs: Mapped[list["Job"]] = relationship(back_populates="video", passive_deletes=True)
