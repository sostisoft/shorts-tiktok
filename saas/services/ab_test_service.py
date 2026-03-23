"""
saas/services/ab_test_service.py
A/B testing — create paired video experiments and evaluate winners.
"""
import logging
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saas.models.ab_test import ABTest
from saas.models.tenant import Tenant
from saas.models.video import Video, VideoStatus
from saas.models.video_analytics import VideoAnalytics

logger = logging.getLogger("saas.services.ab_test")


class ABTestService:

    @staticmethod
    async def create_test(
        db: AsyncSession,
        tenant: Tenant,
        name: str,
        topic: str,
        template_a: str,
        template_b: str,
    ) -> ABTest:
        """Create an A/B test: generates two videos with different templates."""
        from saas.worker.tasks import dispatch_pipeline

        # Create video A
        job_id_a = os.urandom(8).hex()
        video_a = Video(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            job_id=job_id_a,
            status=VideoStatus.QUEUED,
            template=template_a,
        )
        db.add(video_a)

        # Create video B
        job_id_b = os.urandom(8).hex()
        video_b = Video(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            job_id=job_id_b,
            status=VideoStatus.QUEUED,
            template=template_b,
        )
        db.add(video_b)

        await db.flush()

        # Create A/B test
        ab_test = ABTest(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            name=name,
            topic=topic,
            template_a=template_a,
            template_b=template_b,
            status="running",
            video_a_id=video_a.id,
            video_b_id=video_b.id,
        )
        db.add(ab_test)

        # Link videos to test
        video_a.ab_test_id = ab_test.id
        video_b.ab_test_id = ab_test.id

        await db.flush()

        # Dispatch both pipelines
        dispatch_pipeline(job_id_a, str(tenant.id), topic, template_a)
        dispatch_pipeline(job_id_b, str(tenant.id), topic, template_b)

        logger.info(f"A/B test '{name}' created: {template_a} vs {template_b}")
        return ab_test

    @staticmethod
    async def list_tests(db: AsyncSession, tenant: Tenant) -> list[ABTest]:
        result = await db.execute(
            select(ABTest)
            .where(ABTest.tenant_id == tenant.id)
            .order_by(ABTest.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_test(db: AsyncSession, tenant: Tenant, test_id: uuid.UUID) -> ABTest | None:
        result = await db.execute(
            select(ABTest).where(ABTest.id == test_id, ABTest.tenant_id == tenant.id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_test_detail(db: AsyncSession, tenant: Tenant, test_id: uuid.UUID) -> dict | None:
        """Get full A/B test with video details and analytics."""
        test = await ABTestService.get_test(db, tenant, test_id)
        if not test:
            return None

        detail = {
            "id": test.id,
            "tenant_id": test.tenant_id,
            "name": test.name,
            "topic": test.topic,
            "template_a": test.template_a,
            "template_b": test.template_b,
            "status": test.status,
            "video_a_id": test.video_a_id,
            "video_b_id": test.video_b_id,
            "winner": test.winner,
            "created_at": test.created_at,
            "video_a": None,
            "video_b": None,
            "analytics_a": None,
            "analytics_b": None,
        }

        # Fetch videos
        for key, vid_id in [("video_a", test.video_a_id), ("video_b", test.video_b_id)]:
            if vid_id:
                vr = await db.execute(select(Video).where(Video.id == vid_id))
                video = vr.scalar_one_or_none()
                if video:
                    detail[key] = video

                # Latest analytics
                ar = await db.execute(
                    select(VideoAnalytics)
                    .where(VideoAnalytics.video_id == vid_id)
                    .order_by(VideoAnalytics.fetched_at.desc())
                    .limit(1)
                )
                analytics = ar.scalar_one_or_none()
                if analytics:
                    detail[f"analytics_{key[-1]}"] = {
                        "views": analytics.views,
                        "likes": analytics.likes,
                        "comments": analytics.comments,
                        "click_through_rate": float(analytics.click_through_rate) if analytics.click_through_rate else None,
                        "avg_view_percentage": float(analytics.avg_view_percentage) if analytics.avg_view_percentage else None,
                    }

        return detail

    @staticmethod
    async def evaluate_winner(db: AsyncSession, tenant: Tenant, test_id: uuid.UUID) -> str | None:
        """Evaluate which variant won based on analytics. Returns 'a', 'b', or None."""
        test = await ABTestService.get_test(db, tenant, test_id)
        if not test:
            return None

        scores = {}
        for label, vid_id in [("a", test.video_a_id), ("b", test.video_b_id)]:
            if not vid_id:
                scores[label] = 0
                continue
            ar = await db.execute(
                select(VideoAnalytics)
                .where(VideoAnalytics.video_id == vid_id)
                .order_by(VideoAnalytics.fetched_at.desc())
                .limit(1)
            )
            analytics = ar.scalar_one_or_none()
            if not analytics:
                scores[label] = 0
                continue

            # Weighted score: views * 1.0 + likes * 2.0 + CTR * 1000 + retention * 10
            score = (
                analytics.views * 1.0
                + analytics.likes * 2.0
                + (float(analytics.click_through_rate or 0) * 1000)
                + (float(analytics.avg_view_percentage or 0) * 10)
            )
            scores[label] = score

        if scores.get("a", 0) == 0 and scores.get("b", 0) == 0:
            return None  # No analytics yet

        winner = "a" if scores.get("a", 0) >= scores.get("b", 0) else "b"
        test.winner = winner
        test.status = "completed"
        await db.flush()

        logger.info(f"A/B test '{test.name}' winner: variant {winner}")
        return winner
