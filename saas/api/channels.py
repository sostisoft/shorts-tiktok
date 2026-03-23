"""
saas/api/channels.py
Channel management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from saas.auth.api_key import get_current_tenant
from saas.database.session import get_db
from saas.models.tenant import Tenant
from saas.schemas.channel import ChannelCreate, ChannelResponse
from saas.schemas.common import APIEnvelope
from saas.services.channel_service import ChannelService

router = APIRouter(prefix="/api/channels", tags=["channels"])


@router.post("")
async def connect_channel(
    body: ChannelCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Connect a new YouTube/TikTok/Instagram channel."""
    try:
        channel = await ChannelService.connect_channel(
            db=db,
            tenant=tenant,
            platform=body.platform,
            display_name=body.display_name,
            credentials=body.credentials,
        )
        return APIEnvelope(data=ChannelResponse.model_validate(channel))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
async def list_channels(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List connected channels for the authenticated tenant."""
    channels = await ChannelService.list_channels(db, tenant)
    return APIEnvelope(data=[ChannelResponse.model_validate(c) for c in channels])
