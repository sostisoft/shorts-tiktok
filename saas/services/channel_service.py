"""
saas/services/channel_service.py
Business logic for channel management.
"""
import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saas.auth.crypto import get_fernet
from saas.models.channel import Channel
from saas.models.tenant import Tenant

logger = logging.getLogger("saas.services.channel")


class ChannelService:

    @staticmethod
    async def connect_channel(
        db: AsyncSession,
        tenant: Tenant,
        platform: str,
        display_name: str,
        credentials: dict,
    ) -> Channel:
        """Connect a new channel (YouTube/TikTok/Instagram)."""
        if platform not in ("youtube", "tiktok", "instagram"):
            raise ValueError(f"Unsupported platform: {platform}")

        # Encrypt credentials
        fernet = _get_fernet()
        encrypted = fernet.encrypt(json.dumps(credentials).encode()).decode()

        channel = Channel(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            platform=platform,
            display_name=display_name,
            credentials_encrypted=encrypted,
        )
        db.add(channel)
        await db.flush()

        logger.info(f"Channel connected: {display_name} ({platform}) for {tenant.name}")
        return channel

    @staticmethod
    async def list_channels(db: AsyncSession, tenant: Tenant) -> list[Channel]:
        """List all channels for a tenant."""
        result = await db.execute(
            select(Channel)
            .where(Channel.tenant_id == tenant.id, Channel.active.is_(True))
            .order_by(Channel.created_at.desc())
        )
        return list(result.scalars().all())
