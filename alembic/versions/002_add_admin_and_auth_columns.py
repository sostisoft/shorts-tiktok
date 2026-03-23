"""Add admin, auth, and billing columns to tenants.

Revision ID: 002
Revises: 001
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("is_admin", sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("tenants", sa.Column("password_hash", sa.String(200), nullable=True))
    op.add_column("tenants", sa.Column("email_verified", sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("tenants", sa.Column("stripe_customer_id", sa.String(100), nullable=True, unique=True))
    op.add_column("tenants", sa.Column("stripe_subscription_id", sa.String(100), nullable=True))
    op.add_column("tenants", sa.Column("subscription_status", sa.String(30), nullable=True))
    op.add_column("tenants", sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "current_period_end")
    op.drop_column("tenants", "subscription_status")
    op.drop_column("tenants", "stripe_subscription_id")
    op.drop_column("tenants", "stripe_customer_id")
    op.drop_column("tenants", "email_verified")
    op.drop_column("tenants", "password_hash")
    op.drop_column("tenants", "is_admin")
