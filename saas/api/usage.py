"""
saas/api/usage.py
Usage tracking endpoint.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from saas.auth.api_key import get_current_tenant
from saas.database.session import get_db
from saas.models.tenant import Tenant
from saas.schemas.common import APIEnvelope
from saas.schemas.usage import UsageResponse
from saas.services.usage_service import UsageService

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("")
async def get_usage(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get current month usage metrics."""
    usage = await UsageService.get_usage(db, tenant)
    return APIEnvelope(data=UsageResponse(**usage))
