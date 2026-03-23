"""
saas/api/webhooks.py
Webhook management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from saas.auth.api_key import get_current_tenant
from saas.database.session import get_db
from saas.models.tenant import Tenant
from saas.schemas.common import APIEnvelope
from saas.schemas.webhook import WebhookCreate, WebhookResponse
from saas.services.webhook_service import WebhookService

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("")
async def register_webhook(
    body: WebhookCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Register a webhook endpoint for event notifications."""
    try:
        endpoint = await WebhookService.register(
            db=db,
            tenant=tenant,
            url=str(body.url),
            events=body.events,
        )
        return APIEnvelope(data=WebhookResponse.model_validate(endpoint))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
async def list_webhooks(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List registered webhook endpoints."""
    endpoints = await WebhookService.list_webhooks(db, tenant)
    return APIEnvelope(data=[WebhookResponse.model_validate(e) for e in endpoints])
