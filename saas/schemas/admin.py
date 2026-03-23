"""
saas/schemas/admin.py
Admin panel schemas.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel


class TenantListItem(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    plan: str
    active: bool
    is_admin: bool
    videos_generated: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class TenantDetail(TenantListItem):
    channels_count: int = 0
    total_videos: int = 0
    total_cost: float = 0.0
    stripe_customer_id: str | None = None
    subscription_status: str | None = None


class TenantPatch(BaseModel):
    plan: str | None = None
    active: bool | None = None
    is_admin: bool | None = None


class AdminJobResponse(BaseModel):
    id: uuid.UUID
    job_id: str
    tenant_id: uuid.UUID
    tenant_name: str
    title: str | None
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class AdminMetrics(BaseModel):
    total_tenants: int
    active_tenants: int
    total_videos_this_month: int
    total_published_this_month: int
    total_cost_this_month: float
    videos_by_status: dict[str, int]
