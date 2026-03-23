"""
saas/schemas/analytics.py
Analytics schemas.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel


class VideoAnalyticsResponse(BaseModel):
    video_id: uuid.UUID
    views: int
    likes: int
    comments: int
    shares: int
    impressions: int | None
    click_through_rate: float | None
    avg_view_duration_seconds: float | None
    avg_view_percentage: float | None
    fetched_at: datetime

    model_config = {"from_attributes": True}


class AnalyticsSummary(BaseModel):
    total_views: int
    total_likes: int
    total_comments: int
    avg_ctr: float | None
    avg_retention: float | None
    best_video_id: uuid.UUID | None
    best_video_title: str | None
    best_video_views: int
