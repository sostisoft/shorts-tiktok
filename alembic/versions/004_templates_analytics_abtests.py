"""Add template column, video_analytics table, ab_tests table.

Revision ID: 004
Revises: 003
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Video template column ---
    op.add_column("saas_videos", sa.Column("template", sa.String(50), nullable=True))

    # --- Video analytics table ---
    op.create_table(
        "video_analytics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", UUID(as_uuid=True), sa.ForeignKey("saas_videos.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("views", sa.Integer, nullable=False, server_default="0"),
        sa.Column("likes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("comments", sa.Integer, nullable=False, server_default="0"),
        sa.Column("shares", sa.Integer, nullable=False, server_default="0"),
        sa.Column("impressions", sa.Integer, nullable=True),
        sa.Column("click_through_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("avg_view_duration_seconds", sa.Numeric(8, 2), nullable=True),
        sa.Column("avg_view_percentage", sa.Numeric(5, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_video_analytics_fetched_at", "video_analytics", ["fetched_at"])

    # --- A/B tests table ---
    op.create_table(
        "ab_tests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("topic", sa.String(500), nullable=False),
        sa.Column("template_a", sa.String(50), nullable=False, server_default="finance"),
        sa.Column("template_b", sa.String(50), nullable=False, server_default="energetic"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("video_a_id", UUID(as_uuid=True), sa.ForeignKey("saas_videos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("video_b_id", UUID(as_uuid=True), sa.ForeignKey("saas_videos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("winner", sa.String(1), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- Link videos to A/B tests ---
    op.add_column("saas_videos", sa.Column("ab_test_id", UUID(as_uuid=True), sa.ForeignKey("ab_tests.id", ondelete="SET NULL"), nullable=True))


def downgrade() -> None:
    op.drop_column("saas_videos", "ab_test_id")
    op.drop_table("ab_tests")
    op.drop_index("ix_video_analytics_fetched_at", table_name="video_analytics")
    op.drop_table("video_analytics")
    op.drop_column("saas_videos", "template")
