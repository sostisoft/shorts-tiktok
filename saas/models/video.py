"""
saas/models/video.py
Video model — multi-tenant video jobs with status tracking.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from saas.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class VideoStatus(str, enum.Enum):
    QUEUED = "queued"
    SCRIPT = "script"
    IMAGES = "images"
    TTS = "tts"
    VIDEO = "video"
    MUSIC = "music"
    COMPOSITING = "compositing"
    READY = "ready"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    ERROR = "error"
    CANCELLED = "cancelled"


class Video(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "saas_videos"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    channel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channels.id", ondelete="SET NULL"), nullable=True,
    )
    job_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[VideoStatus] = mapped_column(
        Enum(VideoStatus, values_callable=lambda e: [m.value for m in e]),
        nullable=False, default=VideoStatus.QUEUED,
    )
    video_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    preview_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    script_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Platform IDs after publishing
    youtube_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tiktok_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    instagram_id: Mapped[str | None] = mapped_column(String(40), nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True, default=0)
    auto_publish: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Template and A/B test
    template: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ab_test_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ab_tests.id", ondelete="SET NULL"), nullable=True,
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="videos")
    channel = relationship("Channel", back_populates="videos")

    def __repr__(self) -> str:
        return f"<Video {self.job_id} [{self.status}]>"
