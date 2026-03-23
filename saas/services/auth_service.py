"""
saas/services/auth_service.py
Registration and login business logic.
"""
import logging
import secrets
import uuid

from passlib.hash import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saas.auth.api_key import hash_api_key
from saas.models.tenant import Tenant

logger = logging.getLogger("saas.services.auth")


class AuthService:

    @staticmethod
    async def register(
        db: AsyncSession, name: str, email: str, password: str,
    ) -> tuple[Tenant, str]:
        """Register a new tenant. Returns (tenant, plaintext_api_key)."""
        existing = await db.execute(
            select(Tenant).where(Tenant.email == email)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Email already registered")

        api_key = f"sf_{secrets.token_urlsafe(32)}"
        key_hash = hash_api_key(api_key)
        pw_hash = bcrypt.using(rounds=12).hash(password)

        tenant = Tenant(
            id=uuid.uuid4(),
            name=name,
            email=email,
            api_key_hash=key_hash,
            password_hash=pw_hash,
            plan="trial",
            active=True,
            is_admin=False,
            email_verified=False,
        )
        db.add(tenant)
        await db.commit()

        logger.info(f"Tenant registered: {email} (trial)")
        return tenant, api_key

    @staticmethod
    async def login(
        db: AsyncSession, email: str, password: str,
    ) -> Tenant:
        """Login with email/password. Returns tenant (use existing API key)."""
        result = await db.execute(
            select(Tenant).where(Tenant.email == email)
        )
        tenant = result.scalar_one_or_none()

        if not tenant or not tenant.password_hash:
            raise ValueError("Invalid email or password")

        if not bcrypt.verify(password, tenant.password_hash):
            raise ValueError("Invalid email or password")

        if not tenant.active:
            raise ValueError("Account is inactive")

        return tenant
