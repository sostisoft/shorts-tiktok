"""
saas/auth/api_key.py
API key authentication dependency for FastAPI.
Extracts X-API-Key header, hashes with SHA-256, looks up tenant.
"""
import hashlib
import hmac

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saas.database.session import get_db
from saas.models.tenant import Tenant

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_api_key(api_key: str) -> str:
    """Hash an API key with SHA-256. Used for storage and lookup."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


async def get_current_tenant(
    api_key: str | None = Security(_api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """FastAPI dependency: authenticate tenant via X-API-Key header."""
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    key_hash = hash_api_key(api_key)

    result = await db.execute(
        select(Tenant).where(Tenant.api_key_hash == key_hash)
    )
    tenant = result.scalar_one_or_none()

    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if not tenant.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant account is inactive",
        )

    return tenant
