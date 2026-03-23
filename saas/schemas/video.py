"""
saas/schemas/video.py
Request/response models for video endpoints.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class VideoCreate(BaseModel):
    topic: str | None = Field(default=None, description="Topic for script generation")
    style: str = Field(default="finance", description="Video style/template")
    channel_id: uuid.UUID | None = Field(default=None, description="Target channel for auto-publish")
    auto_publish: bool = Field(default=False, description="Publish automatically when ready")


class VideoResponse(BaseModel):
    id: uuid.UUID
    job_id: str
    title: str | None
    description: str | None
    status: str
    video_url: str | None = Field(description="Presigned download URL")
    preview_url: str | None = Field(description="Presigned preview URL")
    cost_usd: float | None
    youtube_id: str | None = None
    tiktok_id: str | None = None
    instagram_id: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None

    model_config = {"from_attributes": True}


class VideoPublish(BaseModel):
    channel_id: uuid.UUID
