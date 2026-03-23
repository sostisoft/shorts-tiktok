"""
tests/test_auth.py
Tests for API key authentication.
"""
import pytest
from httpx import AsyncClient

from tests.saas.conftest import TEST_API_KEY


@pytest.mark.asyncio
async def test_missing_api_key(test_client: AsyncClient):
    """Request without X-API-Key returns 401."""
    resp = await test_client.get("/api/videos")
    assert resp.status_code == 401
    assert "Missing X-API-Key" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_api_key(test_client: AsyncClient):
    """Request with wrong API key returns 401."""
    resp = await test_client.get(
        "/api/videos",
        headers={"X-API-Key": "sf_wrong_key"},
    )
    assert resp.status_code == 401
    assert "Invalid API key" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_valid_api_key(test_client: AsyncClient):
    """Request with valid API key succeeds."""
    resp = await test_client.get(
        "/api/videos",
        headers={"X-API-Key": TEST_API_KEY},
    )
    # Should succeed (200) even if no videos exist
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_health_no_auth():
    """Health endpoint requires no authentication."""
    from httpx import ASGITransport, AsyncClient
    from saas.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
