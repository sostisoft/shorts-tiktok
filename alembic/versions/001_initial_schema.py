"""Initial SaaS schema: tenants, channels, videos, schedules, usage_logs, webhook_endpoints.

Revision ID: 001
Revises: -
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- tenants ---
    op.create_table(
        "tenants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("api_key_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("plan", sa.String(20), nullable=False, server_default="starter"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- channels ---
    op.create_table(
        "channels",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("credentials_encrypted", sa.Text, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- saas_videos ---
    op.create_table(
        "saas_videos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("channel_id", UUID(as_uuid=True), sa.ForeignKey("channels.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_id", sa.String(32), nullable=False, unique=True, index=True),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("tags", JSON, nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "queued", "script", "images", "tts", "video", "music",
                "compositing", "ready", "publishing", "published", "error", "cancelled",
                name="videostatus",
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("video_s3_key", sa.String(500), nullable=True),
        sa.Column("preview_s3_key", sa.String(500), nullable=True),
        sa.Column("script_json", JSON, nullable=True),
        sa.Column("youtube_id", sa.String(20), nullable=True),
        sa.Column("tiktok_id", sa.String(40), nullable=True),
        sa.Column("instagram_id", sa.String(40), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 4), nullable=True, server_default="0"),
        sa.Column("auto_publish", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- schedules ---
    op.create_table(
        "schedules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("channel_id", UUID(as_uuid=True), sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cron_expression", sa.String(100), nullable=False),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="UTC"),
        sa.Column("topic_pool", JSON, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- usage_logs ---
    op.create_table(
        "usage_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("month", sa.String(7), nullable=False),
        sa.Column("videos_generated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("videos_published", sa.Integer, nullable=False, server_default="0"),
        sa.Column("api_cost_usd", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "month", name="uq_usage_tenant_month"),
    )

    # --- webhook_endpoints ---
    op.create_table(
        "webhook_endpoints",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("events", JSON, nullable=False),
        sa.Column("secret", sa.String(64), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("webhook_endpoints")
    op.drop_table("usage_logs")
    op.drop_table("schedules")
    op.drop_table("saas_videos")
    op.drop_table("channels")
    op.drop_table("tenants")
    op.execute("DROP TYPE IF EXISTS videostatus")
