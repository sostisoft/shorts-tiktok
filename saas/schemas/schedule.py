"""
saas/schemas/schedule.py
Schedule CRUD schemas.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ScheduleCreate(BaseModel):
    channel_id: uuid.UUID
    cron_expression: str = Field(description="Cron expression (e.g., '0 9 * * 1-5')")
    timezone: str = Field(default="UTC")
    topic_pool: list[str] | None = Field(default=None, description="Pool of topics to rotate through")
    style: str = Field(default="finance")


class ScheduleUpdate(BaseModel):
    cron_expression: str | None = None
    timezone: str | None = None
    topic_pool: list[str] | None = None
    style: str | None = None
    active: bool | None = None


class ScheduleResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    channel_id: uuid.UUID
    cron_expression: str
    timezone: str
    topic_pool: list[str] | None
    style: str
    active: bool
    last_run_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
