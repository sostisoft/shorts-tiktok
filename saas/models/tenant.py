"""
saas/models/tenant.py
Tenant model — each customer is a tenant.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from saas.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(20), nullable=False, default="starter")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Auth
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    password_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Stripe billing
    stripe_customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subscription_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    channels = relationship("Channel", back_populates="tenant", lazy="selectin")
    videos = relationship("Video", back_populates="tenant", lazy="selectin")
    schedules = relationship("Schedule", back_populates="tenant", lazy="selectin")
    usage_logs = relationship("UsageLog", back_populates="tenant", lazy="selectin")
    webhook_endpoints = relationship("WebhookEndpoint", back_populates="tenant", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Tenant {self.name} [{self.plan}]>"
