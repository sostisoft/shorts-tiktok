"""
saas/models/webhook_endpoint.py
WebhookEndpoint model — webhook URLs for event notifications per tenant.
"""
import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from saas.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WebhookEndpoint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "webhook_endpoints"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    events: Mapped[list] = mapped_column(JSON, nullable=False)  # list of event strings
    secret: Mapped[str] = mapped_column(String(64), nullable=False)  # HMAC signing key
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="webhook_endpoints")

    def __repr__(self) -> str:
        return f"<WebhookEndpoint {self.url[:40]}>"
