"""
tests/test_api_videos.py
Tests for video CRUD endpoints.
"""
import pytest
from unittest.mock import patch
from httpx import AsyncClient

from tests.saas.conftest import TEST_API_KEY


@pytest.mark.asyncio
async def test_list_videos_empty(test_client: AsyncClient):
    """Empty tenant has no videos."""
    resp = await test_client.get(
        "/api/videos",
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"] == []
    assert body["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_create_video_dispatches_pipeline(test_client: AsyncClient):
    """POST /api/videos creates a job and returns 202."""
    with patch("saas.worker.tasks.dispatch_pipeline") as mock_dispatch:
        resp = await test_client.post(
            "/api/videos",
            headers={"X-API-Key": TEST_API_KEY},
            json={"topic": "Ahorro para principiantes", "style": "finance"},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "queued"
    assert body["data"]["job_id"] is not None
    mock_dispatch.assert_called_once()


@pytest.mark.asyncio
async def test_get_nonexistent_video(test_client: AsyncClient):
    """GET /api/videos/{id} returns 404 for unknown video."""
    import uuid
    resp = await test_client.get(
        f"/api/videos/{uuid.uuid4()}",
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_video(test_client: AsyncClient):
    """DELETE /api/videos/{id} returns 404 for unknown video."""
    import uuid
    resp = await test_client.delete(
        f"/api/videos/{uuid.uuid4()}",
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert resp.status_code == 404
