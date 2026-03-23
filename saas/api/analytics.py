"""
saas/api/analytics.py
Video analytics endpoints.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from saas.auth.api_key import get_current_tenant
from saas.database.session import get_db
from saas.models.tenant import Tenant
from saas.schemas.analytics import AnalyticsSummary, VideoAnalyticsResponse
from saas.schemas.common import APIEnvelope
from saas.services.analytics_service import AnalyticsService

router = APIRouter(tags=["analytics"])


@router.get("/api/videos/{video_id}/analytics")
async def get_video_analytics(
    video_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    analytics = await AnalyticsService.get_video_analytics(db, tenant, video_id)
    if not analytics:
        return APIEnvelope(data=None)
    return APIEnvelope(data=VideoAnalyticsResponse.model_validate(analytics))


@router.get("/api/analytics/summary")
async def get_analytics_summary(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    summary = await AnalyticsService.get_tenant_summary(db, tenant)
    return APIEnvelope(data=AnalyticsSummary(**summary))
