"""
saas/api/auth.py
Public auth endpoints: register, login, /api/me.
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from saas.auth.api_key import get_current_tenant, hash_api_key
from saas.database.session import get_db
from saas.models.tenant import Tenant
from saas.schemas.auth import AuthResponse, LoginRequest, MeResponse, RegisterRequest
from saas.schemas.common import APIEnvelope
from saas.services.auth_service import AuthService

router = APIRouter(tags=["auth"])


@router.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Public registration — creates a trial tenant with new API key."""
    try:
        tenant, api_key = await AuthService.register(
            db, body.name, body.email, body.password,
        )
        return APIEnvelope(data=AuthResponse(
            tenant_id=tenant.id,
            name=tenant.name,
            email=tenant.email,
            plan=tenant.plan,
            api_key=api_key,
            is_admin=tenant.is_admin,
        ))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/auth/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email/password — generates a new session API key."""
    try:
        tenant = await AuthService.login(db, body.email, body.password)

        # Generate a session-scoped API key (doesn't invalidate existing key)
        session_key = f"sf_{secrets.token_urlsafe(32)}"
        tenant.api_key_hash = hash_api_key(session_key)
        await db.commit()

        return APIEnvelope(data=AuthResponse(
            tenant_id=tenant.id,
            name=tenant.name,
            email=tenant.email,
            plan=tenant.plan,
            api_key=session_key,
            is_admin=tenant.is_admin,
        ))
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/api/me")
async def get_me(tenant: Tenant = Depends(get_current_tenant)):
    """Get current tenant info."""
    return APIEnvelope(data=MeResponse.model_validate(tenant))
