"""
saas/schemas/channel.py
Request/response models for channel endpoints.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ChannelCreate(BaseModel):
    platform: str = Field(description="youtube, tiktok, or instagram")
    display_name: str = Field(description="Human-readable channel name")
    credentials: dict = Field(description="OAuth token data (encrypted at rest)")


class ChannelResponse(BaseModel):
    id: uuid.UUID
    platform: str
    display_name: str
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
