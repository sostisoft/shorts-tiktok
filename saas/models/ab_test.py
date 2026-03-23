"""
saas/models/ab_test.py
ABTest model — A/B test comparing two video variants.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from saas.models.base import Base, UUIDPrimaryKeyMixin


class ABTest(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ab_tests"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    template_a: Mapped[str] = mapped_column(String(50), nullable=False, default="finance")
    template_b: Mapped[str] = mapped_column(String(50), nullable=False, default="energetic")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    video_a_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("saas_videos.id", ondelete="SET NULL"), nullable=True,
    )
    video_b_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("saas_videos.id", ondelete="SET NULL"), nullable=True,
    )
    winner: Mapped[str | None] = mapped_column(String(1), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    # Relationships
    tenant = relationship("Tenant")
    video_a = relationship("Video", foreign_keys=[video_a_id])
    video_b = relationship("Video", foreign_keys=[video_b_id])

    def __repr__(self) -> str:
        return f"<ABTest '{self.name}' [{self.status}]>"
