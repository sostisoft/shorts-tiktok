"""
saas/api/trends.py
Trend intelligence endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException

from saas.auth.api_key import get_current_tenant
from saas.models.tenant import Tenant
from saas.schemas.common import APIEnvelope
from saas.schemas.trend import TrendRequest, TrendSuggestion
from saas.services.trend_service import TrendService

router = APIRouter(prefix="/api/trends", tags=["trends"])


@router.post("/suggest")
async def suggest_topics(
    body: TrendRequest,
    _tenant: Tenant = Depends(get_current_tenant),
):
    try:
        suggestions = await TrendService.suggest_topics(body.niche, body.count)
        return APIEnvelope(data=[TrendSuggestion(**s) for s in suggestions])
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
