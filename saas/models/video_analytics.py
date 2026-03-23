"""
saas/models/video_analytics.py
VideoAnalytics model — stores YouTube/TikTok performance metrics.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from saas.models.base import Base, UUIDPrimaryKeyMixin


class VideoAnalytics(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "video_analytics"

    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("saas_videos.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    likes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comments: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shares: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    impressions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    click_through_rate: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    avg_view_duration_seconds: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    avg_view_percentage: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    # Relationships
    video = relationship("Video", backref="analytics_entries")

    def __repr__(self) -> str:
        return f"<VideoAnalytics video={self.video_id} views={self.views}>"
