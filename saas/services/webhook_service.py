"""
saas/services/webhook_service.py
Webhook endpoint registration.
"""
import os
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saas.models.tenant import Tenant
from saas.models.webhook_endpoint import WebhookEndpoint

VALID_EVENTS = {"video.completed", "video.error", "video.published", "*"}


class WebhookService:

    @staticmethod
    async def register(
        db: AsyncSession,
        tenant: Tenant,
        url: str,
        events: list[str],
    ) -> WebhookEndpoint:
        """Register a webhook endpoint."""
        for event in events:
            if event not in VALID_EVENTS:
                raise ValueError(f"Invalid event: {event}. Valid: {VALID_EVENTS}")

        endpoint = WebhookEndpoint(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            url=url,
            events=events,
            secret=os.urandom(32).hex(),
        )
        db.add(endpoint)
        await db.flush()
        return endpoint

    @staticmethod
    async def list_webhooks(db: AsyncSession, tenant: Tenant) -> list[WebhookEndpoint]:
        """List all webhook endpoints for a tenant."""
        result = await db.execute(
            select(WebhookEndpoint)
            .where(WebhookEndpoint.tenant_id == tenant.id, WebhookEndpoint.active.is_(True))
        )
        return list(result.scalars().all())
