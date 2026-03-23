"""
saas/schemas/webhook.py
Request/response models for webhook endpoints.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class WebhookCreate(BaseModel):
    url: HttpUrl
    events: list[str] = Field(
        description="Events to subscribe to",
        examples=[["video.completed", "video.error", "video.published"]],
    )


class WebhookResponse(BaseModel):
    id: uuid.UUID
    url: str
    events: list[str]
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
