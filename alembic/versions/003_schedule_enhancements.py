"""Add style and last_run_at to schedules.

Revision ID: 003
Revises: 002
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("schedules", sa.Column("style", sa.String(50), nullable=False, server_default="finance"))
    op.add_column("schedules", sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("schedules", "last_run_at")
    op.drop_column("schedules", "style")
