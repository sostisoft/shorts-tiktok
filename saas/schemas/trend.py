"""
saas/schemas/trend.py
Trend intelligence schemas.
"""
from pydantic import BaseModel, Field


class TrendRequest(BaseModel):
    niche: str = Field(default="finanzas personales", description="Topic niche")
    count: int = Field(default=10, ge=1, le=20)


class TrendSuggestion(BaseModel):
    topic: str
    reasoning: str
    estimated_interest: str  # "high", "medium", "low"
