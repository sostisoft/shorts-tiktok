"""
saas/models/schedule.py
Schedule model — cron-based video generation schedules per tenant.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from saas.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Schedule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "schedules"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False,
    )
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="UTC")
    topic_pool: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    style: Mapped[str] = mapped_column(String(50), nullable=False, default="finance")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="schedules")
    channel = relationship("Channel")

    def __repr__(self) -> str:
        return f"<Schedule {self.cron_expression} [{self.timezone}]>"
