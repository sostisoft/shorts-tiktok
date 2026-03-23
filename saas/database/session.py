"""
saas/database/session.py
FastAPI dependency for database sessions.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from saas.database.engine import get_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
