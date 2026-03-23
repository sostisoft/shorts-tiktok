"""
saas/api/videos.py
Video CRUD endpoints.
"""
import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from saas.auth.api_key import get_current_tenant
from saas.database.session import get_db
from saas.models.tenant import Tenant
from saas.schemas.common import APIEnvelope, PaginationMeta
from saas.schemas.video import VideoCreate, VideoPublish, VideoResponse
from saas.services.video_service import VideoService
from saas.storage.s3 import generate_presigned_url

router = APIRouter(prefix="/api/videos", tags=["videos"])


def _video_to_response(video) -> VideoResponse:
    return VideoResponse(
        id=video.id,
        job_id=video.job_id,
        title=video.title,
        description=video.description,
        status=video.status.value if hasattr(video.status, "value") else str(video.status),
        video_url=generate_presigned_url(video.video_s3_key) if video.video_s3_key else None,
        preview_url=generate_presigned_url(video.preview_s3_key) if video.preview_s3_key else None,
        cost_usd=float(video.cost_usd) if video.cost_usd else None,
        youtube_id=video.youtube_id,
        tiktok_id=video.tiktok_id,
        instagram_id=video.instagram_id,
        error_message=video.error_message,
        created_at=video.created_at,
        updated_at=video.updated_at,
        published_at=video.published_at,
    )


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_video(
    body: VideoCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Create a new video generation job."""
    from saas.services.video_service import QuotaExceededError
    try:
        video = await VideoService.create_job(
            db=db,
            tenant=tenant,
            topic=body.topic,
            style=body.style,
            channel_id=body.channel_id,
            auto_publish=body.auto_publish,
        )
        return APIEnvelope(data=_video_to_response(video))
    except QuotaExceededError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("")
async def list_videos(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List videos for the authenticated tenant."""
    videos, total = await VideoService.list_videos(db, tenant, page, limit, status_filter)
    return APIEnvelope(
        data=[_video_to_response(v) for v in videos],
        meta=PaginationMeta(
            total=total,
            page=page,
            limit=limit,
            pages=math.ceil(total / limit) if total > 0 else 0,
        ),
    )


@router.get("/{video_id}")
async def get_video(
    video_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get a single video with presigned URLs."""
    video = await VideoService.get_video(db, tenant, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return APIEnvelope(data=_video_to_response(video))


@router.delete("/{video_id}", status_code=status.HTTP_200_OK)
async def delete_video(
    video_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Delete a video and its S3 assets."""
    deleted = await VideoService.delete_video(db, tenant, video_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Video not found")
    return APIEnvelope(data={"deleted": True})


@router.post("/{video_id}/publish", status_code=status.HTTP_202_ACCEPTED)
async def publish_video(
    video_id: uuid.UUID,
    body: VideoPublish,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Publish a ready video to a channel."""
    try:
        video = await VideoService.publish_video(db, tenant, video_id, body.channel_id)
        return APIEnvelope(data=_video_to_response(video))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{video_id}/preview")
async def preview_video(
    video_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Redirect to presigned preview URL."""
    from fastapi.responses import RedirectResponse

    video = await VideoService.get_video(db, tenant, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    if not video.preview_s3_key:
        raise HTTPException(status_code=404, detail="Preview not available yet")
    url = generate_presigned_url(video.preview_s3_key)
    return RedirectResponse(url=url)
