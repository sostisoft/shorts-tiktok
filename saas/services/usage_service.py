"""
saas/services/usage_service.py
Usage tracking and querying.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saas.config import PlanTier, get_settings
from saas.models.tenant import Tenant
from saas.models.usage_log import UsageLog


class UsageService:

    @staticmethod
    async def get_usage(db: AsyncSession, tenant: Tenant) -> dict:
        """Get current month usage for a tenant."""
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        settings = get_settings()
        plan = PlanTier(tenant.plan)

        result = await db.execute(
            select(UsageLog).where(
                UsageLog.tenant_id == tenant.id,
                UsageLog.month == month,
            )
        )
        usage = result.scalar_one_or_none()

        return {
            "month": month,
            "videos_generated": usage.videos_generated if usage else 0,
            "videos_published": usage.videos_published if usage else 0,
            "api_cost_usd": float(usage.api_cost_usd) if usage else 0.0,
            "plan_limit": settings.video_limit_for_plan(plan),
        }
