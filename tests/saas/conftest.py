"""
tests/saas/conftest.py
Shared pytest fixtures for ShortForge SaaS tests.
Uses in-memory SQLite for fast testing (no PostgreSQL dependency).
"""
import asyncio
import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set test environment before importing app modules
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["S3_ENDPOINT"] = "http://localhost:9000"
os.environ["S3_BUCKET"] = "test-bucket"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from saas.auth.api_key import hash_api_key
from saas.models.base import Base
from saas.models.tenant import Tenant


# In-memory SQLite for tests
TEST_ENGINE = create_async_engine(
    "sqlite+aiosqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionFactory = async_sessionmaker(
    bind=TEST_ENGINE,
    class_=AsyncSession,
    expire_on_commit=False,
)

TEST_API_KEY = "sf_test_api_key_12345"
TEST_API_KEY_HASH = hash_api_key(TEST_API_KEY)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create all tables before each test, drop after."""
    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    """Get a test database session."""
    async with TestSessionFactory() as session:
        yield session


@pytest_asyncio.fixture
async def test_tenant(db_session: AsyncSession):
    """Create a starter-plan test tenant."""
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Test Tenant",
        email="test@example.com",
        api_key_hash=TEST_API_KEY_HASH,
        plan="starter",
        active=True,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest_asyncio.fixture
async def agency_tenant(db_session: AsyncSession):
    """Create an agency-tier test tenant."""
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Agency Tenant",
        email="agency@example.com",
        api_key_hash=hash_api_key("sf_agency_key"),
        plan="agency",
        active=True,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest_asyncio.fixture
async def test_client(test_tenant):
    """FastAPI test client with mocked DB session returning the test tenant."""
    from saas.database.session import get_db
    from saas.main import create_app

    app = create_app()

    async def override_get_db():
        async with TestSessionFactory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
