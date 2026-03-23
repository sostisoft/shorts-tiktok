"""
saas/models/channel.py
Channel model — connected YouTube/TikTok/Instagram channels per tenant.
"""
import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from saas.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Channel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "channels"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)  # youtube, tiktok, instagram
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    credentials_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="channels")
    videos = relationship("Video", back_populates="channel", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Channel {self.display_name} [{self.platform}]>"
