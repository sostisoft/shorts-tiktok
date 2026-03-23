"""
saas/services/analytics_service.py
YouTube Analytics fetcher and query service.
"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from saas.models.tenant import Tenant
from saas.models.video import Video, VideoStatus
from saas.models.video_analytics import VideoAnalytics

logger = logging.getLogger("saas.services.analytics")


class AnalyticsService:

    @staticmethod
    async def get_video_analytics(
        db: AsyncSession, tenant: Tenant, video_id: uuid.UUID,
    ) -> VideoAnalytics | None:
        """Get latest analytics for a video."""
        result = await db.execute(
            select(VideoAnalytics)
            .join(Video, VideoAnalytics.video_id == Video.id)
            .where(Video.id == video_id, Video.tenant_id == tenant.id)
            .order_by(VideoAnalytics.fetched_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_tenant_summary(db: AsyncSession, tenant: Tenant) -> dict:
        """Get aggregated analytics summary for a tenant."""
        # Subquery: latest analytics per video
        latest = (
            select(
                VideoAnalytics.video_id,
                func.max(VideoAnalytics.fetched_at).label("max_fetched"),
            )
            .group_by(VideoAnalytics.video_id)
            .subquery()
        )

        result = await db.execute(
            select(
                func.coalesce(func.sum(VideoAnalytics.views), 0),
                func.coalesce(func.sum(VideoAnalytics.likes), 0),
                func.coalesce(func.sum(VideoAnalytics.comments), 0),
                func.avg(VideoAnalytics.click_through_rate),
                func.avg(VideoAnalytics.avg_view_percentage),
            )
            .join(Video, VideoAnalytics.video_id == Video.id)
            .join(
                latest,
                (VideoAnalytics.video_id == latest.c.video_id)
                & (VideoAnalytics.fetched_at == latest.c.max_fetched),
            )
            .where(Video.tenant_id == tenant.id)
        )
        row = result.one()

        # Best performing video
        best_result = await db.execute(
            select(Video.id, Video.title, VideoAnalytics.views)
            .join(VideoAnalytics, VideoAnalytics.video_id == Video.id)
            .where(Video.tenant_id == tenant.id)
            .order_by(VideoAnalytics.views.desc())
            .limit(1)
        )
        best = best_result.first()

        return {
            "total_views": int(row[0]),
            "total_likes": int(row[1]),
            "total_comments": int(row[2]),
            "avg_ctr": float(row[3]) if row[3] else None,
            "avg_retention": float(row[4]) if row[4] else None,
            "best_video_id": best[0] if best else None,
            "best_video_title": best[1] if best else None,
            "best_video_views": best[2] if best else 0,
        }

    @staticmethod
    async def upsert_analytics(
        db: AsyncSession, video_id: uuid.UUID, data: dict,
    ) -> VideoAnalytics:
        """Insert or update analytics for a video."""
        analytics = VideoAnalytics(
            id=uuid.uuid4(),
            video_id=video_id,
            fetched_at=datetime.now(timezone.utc),
            views=data.get("views", 0),
            likes=data.get("likes", 0),
            comments=data.get("comments", 0),
            shares=data.get("shares", 0),
            impressions=data.get("impressions"),
            click_through_rate=data.get("click_through_rate"),
            avg_view_duration_seconds=data.get("avg_view_duration_seconds"),
            avg_view_percentage=data.get("avg_view_percentage"),
        )
        db.add(analytics)
        await db.flush()
        return analytics
