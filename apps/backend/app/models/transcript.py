from typing import Any

from sqlalchemy import Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class Transcript(TimestampMixin, Base):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    language: Mapped[str | None] = mapped_column(String(20))
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_sec: Mapped[float | None] = mapped_column(Float())
    text: Mapped[str] = mapped_column(Text(), nullable=False, default="")
    # [{"start": 0.0, "end": 2.4, "text": "..."}]
    segments: Mapped[list[dict[str, Any]]] = mapped_column(JSON(), nullable=False, default=list)

    video: Mapped["Video"] = relationship(back_populates="transcripts")
