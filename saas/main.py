"""
saas/main.py
FastAPI application factory for ShortForge SaaS API.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from saas.api.router import api_router
from saas.config import get_settings
from saas.database.engine import dispose_engine, get_engine

logger = logging.getLogger("saas")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    settings = get_settings()
    logger.info("ShortForge SaaS API starting up...")

    # Verify DB connection
    from sqlalchemy import text
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Database connection OK")

    yield

    # Shutdown
    await dispose_engine()
    from saas.auth.rate_limiter import close_redis
    await close_redis()
    logger.info("ShortForge SaaS API shut down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="ShortForge API",
        description="Multi-tenant video generation SaaS",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(api_router)

    return app


# Default app instance for uvicorn
app = create_app()
