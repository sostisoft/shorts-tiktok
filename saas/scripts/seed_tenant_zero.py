#!/usr/bin/env python3
"""
Seed script: creates the @finanzasjpg bot as tenant zero in PostgreSQL.
Run once after initial migration.

Usage:
    python -m saas.scripts.seed_tenant_zero
"""
import asyncio
import os
import secrets
import sys

from dotenv import load_dotenv
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from saas.auth.api_key import hash_api_key
from saas.database.engine import get_engine, get_session_factory, dispose_engine
from saas.models.tenant import Tenant


async def main():
    # Generate API key
    api_key = f"sf_{secrets.token_urlsafe(32)}"
    key_hash = hash_api_key(api_key)

    session_factory = get_session_factory()
    async with session_factory() as session:
        # Check if tenant zero already exists
        from sqlalchemy import select
        result = await session.execute(
            select(Tenant).where(Tenant.email == "finanzasjpg@gmail.com")
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Tenant zero already exists: {existing.name} ({existing.id})")
            print(f"Plan: {existing.plan}")
            return

        tenant = Tenant(
            name="Finanzas Claras",
            email="finanzasjpg@gmail.com",
            api_key_hash=key_hash,
            plan="agency",
            active=True,
        )
        session.add(tenant)
        await session.commit()

        print("=" * 60)
        print("Tenant zero created successfully!")
        print(f"  Name:    {tenant.name}")
        print(f"  Email:   finanzasjpg@gmail.com")
        print(f"  Plan:    agency")
        print(f"  ID:      {tenant.id}")
        print()
        print(f"  API Key: {api_key}")
        print()
        print("SAVE THIS API KEY — it cannot be recovered!")
        print("=" * 60)

    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
