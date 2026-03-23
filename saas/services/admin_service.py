"""
saas/services/admin_service.py
Admin panel business logic — cross-tenant operations.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession

from saas.models.tenant import Tenant
from saas.models.usage_log import UsageLog
from saas.models.video import Video, VideoStatus


class AdminService:

    @staticmethod
    async def list_tenants(
        db: AsyncSession, page: int = 1, limit: int = 20,
    ) -> tuple[list[dict], int]:
        month = datetime.now(timezone.utc).strftime("%Y-%m")

        # Main query with usage join
        query = (
            select(
                Tenant,
                func.coalesce(UsageLog.videos_generated, 0).label("videos_generated"),
            )
            .outerjoin(
                UsageLog,
                (UsageLog.tenant_id == Tenant.id) & (UsageLog.month == month),
            )
            .order_by(Tenant.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await db.execute(query)
        rows = result.all()

        count_result = await db.execute(select(func.count(Tenant.id)))
        total = count_result.scalar()

        tenants = []
        for row in rows:
            tenant = row[0]
            tenants.append({
                "id": tenant.id,
                "name": tenant.name,
                "email": tenant.email,
                "plan": tenant.plan,
                "active": tenant.active,
                "is_admin": tenant.is_admin,
                "videos_generated": row[1],
                "created_at": tenant.created_at,
            })

        return tenants, total

    @staticmethod
    async def get_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> dict | None:
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if not tenant:
            return None

        # Count channels
        from saas.models.channel import Channel
        ch_count = await db.execute(
            select(func.count(Channel.id)).where(Channel.tenant_id == tenant_id)
        )
        # Count total videos
        vid_count = await db.execute(
            select(func.count(Video.id)).where(Video.tenant_id == tenant_id)
        )

        return {
            "id": tenant.id,
            "name": tenant.name,
            "email": tenant.email,
            "plan": tenant.plan,
            "active": tenant.active,
            "is_admin": tenant.is_admin,
            "videos_generated": 0,
            "created_at": tenant.created_at,
            "channels_count": ch_count.scalar(),
            "total_videos": vid_count.scalar(),
            "total_cost": 0.0,
            "stripe_customer_id": tenant.stripe_customer_id,
            "subscription_status": tenant.subscription_status,
        }

    @staticmethod
    async def update_tenant(
        db: AsyncSession, tenant_id: uuid.UUID, patch: dict,
    ) -> Tenant | None:
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if not tenant:
            return None

        for key, value in patch.items():
            if value is not None and hasattr(tenant, key):
                setattr(tenant, key, value)

        await db.flush()
        return tenant

    @staticmethod
    async def list_jobs(
        db: AsyncSession, page: int = 1, limit: int = 20,
        status_filter: str | None = None, tenant_filter: uuid.UUID | None = None,
    ) -> tuple[list[dict], int]:
        query = (
            select(Video, Tenant.name.label("tenant_name"))
            .join(Tenant, Video.tenant_id == Tenant.id)
        )
        count_query = select(func.count(Video.id))

        if status_filter:
            query = query.where(Video.status == status_filter)
            count_query = count_query.where(Video.status == status_filter)
        if tenant_filter:
            query = query.where(Video.tenant_id == tenant_filter)
            count_query = count_query.where(Video.tenant_id == tenant_filter)

        query = query.order_by(Video.created_at.desc()).offset((page - 1) * limit).limit(limit)

        result = await db.execute(query)
        rows = result.all()
        count_result = await db.execute(count_query)
        total = count_result.scalar()

        jobs = []
        for row in rows:
            video = row[0]
            jobs.append({
                "id": video.id,
                "job_id": video.job_id,
                "tenant_id": video.tenant_id,
                "tenant_name": row[1],
                "title": video.title,
                "status": video.status.value if hasattr(video.status, "value") else str(video.status),
                "error_message": video.error_message,
                "created_at": video.created_at,
                "updated_at": video.updated_at,
            })

        return jobs, total

    @staticmethod
    async def get_metrics(db: AsyncSession) -> dict:
        month = datetime.now(timezone.utc).strftime("%Y-%m")

        total_tenants = (await db.execute(select(func.count(Tenant.id)))).scalar()
        active_tenants = (await db.execute(
            select(func.count(Tenant.id)).where(Tenant.active.is_(True))
        )).scalar()

        # Usage this month
        usage_result = await db.execute(
            select(
                func.coalesce(func.sum(UsageLog.videos_generated), 0),
                func.coalesce(func.sum(UsageLog.videos_published), 0),
                func.coalesce(func.sum(UsageLog.api_cost_usd), 0),
            ).where(UsageLog.month == month)
        )
        usage_row = usage_result.one()

        # Videos by status
        status_result = await db.execute(
            select(Video.status, func.count(Video.id)).group_by(Video.status)
        )
        by_status = {
            (row[0].value if hasattr(row[0], "value") else str(row[0])): row[1]
            for row in status_result.all()
        }

        return {
            "total_tenants": total_tenants,
            "active_tenants": active_tenants,
            "total_videos_this_month": int(usage_row[0]),
            "total_published_this_month": int(usage_row[1]),
            "total_cost_this_month": float(usage_row[2]),
            "videos_by_status": by_status,
        }
