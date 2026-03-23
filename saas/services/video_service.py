"""
saas/services/video_service.py
Business logic for video job CRUD and pipeline dispatch.
"""
import logging
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from saas.config import PlanTier, get_settings
from saas.models.tenant import Tenant
from saas.models.usage_log import UsageLog
from saas.models.video import Video, VideoStatus
from saas.storage.s3 import delete_tenant_job

logger = logging.getLogger("saas.services.video")


class VideoService:

    @staticmethod
    async def create_job(
        db: AsyncSession,
        tenant: Tenant,
        topic: str | None,
        style: str,
        channel_id: uuid.UUID | None,
        auto_publish: bool,
    ) -> Video:
        """Create a video job and dispatch the pipeline."""
        settings = get_settings()
        plan = PlanTier(tenant.plan)

        # Check subscription status (HIGH: past-due billing check)
        if tenant.subscription_status in ("past_due", "canceled", "unpaid"):
            if plan not in (PlanTier.TRIAL,):
                raise PermissionError(
                    "Subscription is inactive. Please update your payment method."
                )

        # Check monthly limit
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        limit = settings.video_limit_for_plan(plan)

        result = await db.execute(
            select(UsageLog).where(
                UsageLog.tenant_id == tenant.id,
                UsageLog.month == month,
            )
        )
        usage = result.scalar_one_or_none()
        current_count = usage.videos_generated if usage else 0

        if current_count >= limit:
            raise QuotaExceededError(
                f"Monthly video limit reached ({current_count}/{limit} for {plan.value} plan)"
            )

        # Create video record
        job_id = os.urandom(8).hex()
        video = Video(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            channel_id=channel_id,
            job_id=job_id,
            status=VideoStatus.QUEUED,
            auto_publish=auto_publish,
            template=style,
        )
        db.add(video)

        # Upsert usage log (atomic to prevent race condition)
        if usage is None:
            usage = UsageLog(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                month=month,
                videos_generated=1,
            )
            db.add(usage)
        else:
            usage.videos_generated += 1

        # Commit BEFORE dispatching Celery to prevent orphaned tasks
        await db.commit()

        # Dispatch Celery pipeline (after commit so video exists in DB)
        try:
            from saas.worker.tasks import dispatch_pipeline
            effective_topic = topic or "finanzas personales"
            dispatch_pipeline(job_id, str(tenant.id), effective_topic, style)
        except Exception as e:
            logger.error(f"Failed to dispatch pipeline for {job_id}: {e}")
            # Video exists in DB as "queued" — can be retried manually

        logger.info(f"Job {job_id} created for tenant {tenant.name}")
        return video

    @staticmethod
    async def list_videos(
        db: AsyncSession,
        tenant: Tenant,
        page: int = 1,
        limit: int = 20,
        status_filter: str | None = None,
    ) -> tuple[list[Video], int]:
        query = select(Video).where(Video.tenant_id == tenant.id)
        count_query = select(func.count(Video.id)).where(Video.tenant_id == tenant.id)

        if status_filter:
            query = query.where(Video.status == status_filter)
            count_query = count_query.where(Video.status == status_filter)

        query = query.order_by(Video.created_at.desc())
        query = query.offset((page - 1) * limit).limit(limit)

        result = await db.execute(query)
        videos = list(result.scalars().all())

        count_result = await db.execute(count_query)
        total = count_result.scalar()

        return videos, total

    @staticmethod
    async def get_video(db: AsyncSession, tenant: Tenant, video_id: uuid.UUID) -> Video | None:
        result = await db.execute(
            select(Video).where(Video.id == video_id, Video.tenant_id == tenant.id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def delete_video(db: AsyncSession, tenant: Tenant, video_id: uuid.UUID) -> bool:
        result = await db.execute(
            select(Video).where(Video.id == video_id, Video.tenant_id == tenant.id)
        )
        video = result.scalar_one_or_none()
        if video is None:
            return False

        if video.video_s3_key:
            delete_tenant_job(str(tenant.id), video.job_id)

        await db.delete(video)
        await db.commit()
        return True

    @staticmethod
    async def publish_video(
        db: AsyncSession, tenant: Tenant, video_id: uuid.UUID, channel_id: uuid.UUID,
    ) -> Video:
        result = await db.execute(
            select(Video).where(Video.id == video_id, Video.tenant_id == tenant.id)
        )
        video = result.scalar_one_or_none()
        if video is None:
            raise ValueError("Video not found")
        if video.status != VideoStatus.READY:
            raise ValueError(f"Video is not ready for publishing (status: {video.status})")

        from saas.worker.tasks import publish_video
        publish_video.delay(video.job_id, str(tenant.id), str(channel_id))

        return video


class QuotaExceededError(Exception):
    """Raised when tenant exceeds their plan's video limit."""
    pass
