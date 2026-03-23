"""
saas/schemas/ab_test.py
A/B testing schemas.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from saas.schemas.video import VideoResponse


class ABTestCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    topic: str = Field(min_length=1, max_length=500)
    template_a: str = Field(default="finance")
    template_b: str = Field(default="energetic")


class ABTestResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    topic: str
    template_a: str
    template_b: str
    status: str
    video_a_id: uuid.UUID | None
    video_b_id: uuid.UUID | None
    winner: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ABTestDetail(ABTestResponse):
    video_a: VideoResponse | None = None
    video_b: VideoResponse | None = None
    analytics_a: dict | None = None
    analytics_b: dict | None = None
