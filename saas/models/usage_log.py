"""
saas/models/usage_log.py
UsageLog model — monthly usage tracking per tenant.
"""
import uuid

from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from saas.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UsageLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "usage_logs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "month", name="uq_usage_tenant_month"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    month: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    videos_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    videos_published: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    api_cost_usd: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=0)

    # Relationships
    tenant = relationship("Tenant", back_populates="usage_logs")

    def __repr__(self) -> str:
        return f"<UsageLog {self.month} gen={self.videos_generated} pub={self.videos_published}>"
