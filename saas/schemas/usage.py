"""
saas/schemas/usage.py
Response model for usage endpoint.
"""
from pydantic import BaseModel


class UsageResponse(BaseModel):
    month: str
    videos_generated: int
    videos_published: int
    api_cost_usd: float
    plan_limit: int
