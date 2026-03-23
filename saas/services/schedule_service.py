"""
saas/services/schedule_service.py
Schedule CRUD and cron evaluation.
"""
import logging
import random
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saas.models.channel import Channel
from saas.models.schedule import Schedule
from saas.models.tenant import Tenant

logger = logging.getLogger("saas.services.schedule")


class ScheduleService:

    @staticmethod
    async def create_schedule(
        db: AsyncSession,
        tenant: Tenant,
        channel_id: uuid.UUID,
        cron_expression: str,
        tz: str,
        topic_pool: list[str] | None,
        style: str,
    ) -> Schedule:
        # Validate cron
        if not croniter.is_valid(cron_expression):
            raise ValueError(f"Invalid cron expression: {cron_expression}")

        # Validate timezone
        try:
            ZoneInfo(tz)
        except (KeyError, ValueError):
            raise ValueError(f"Invalid timezone: {tz}")

        # Validate channel belongs to tenant
        result = await db.execute(
            select(Channel).where(Channel.id == channel_id, Channel.tenant_id == tenant.id)
        )
        if not result.scalar_one_or_none():
            raise ValueError("Channel not found or does not belong to tenant")

        schedule = Schedule(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            channel_id=channel_id,
            cron_expression=cron_expression,
            timezone=tz,
            topic_pool=topic_pool,
            style=style,
        )
        db.add(schedule)
        await db.flush()

        logger.info(f"Schedule created: {cron_expression} ({tz}) for {tenant.name}")
        return schedule

    @staticmethod
    async def list_schedules(db: AsyncSession, tenant: Tenant) -> list[Schedule]:
        result = await db.execute(
            select(Schedule)
            .where(Schedule.tenant_id == tenant.id)
            .order_by(Schedule.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_schedule(
        db: AsyncSession, tenant: Tenant, schedule_id: uuid.UUID,
    ) -> Schedule | None:
        result = await db.execute(
            select(Schedule).where(Schedule.id == schedule_id, Schedule.tenant_id == tenant.id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_schedule(
        db: AsyncSession, tenant: Tenant, schedule_id: uuid.UUID, patch: dict,
    ) -> Schedule | None:
        schedule = await ScheduleService.get_schedule(db, tenant, schedule_id)
        if not schedule:
            return None

        if "cron_expression" in patch and patch["cron_expression"]:
            if not croniter.is_valid(patch["cron_expression"]):
                raise ValueError(f"Invalid cron expression: {patch['cron_expression']}")

        if "timezone" in patch and patch["timezone"]:
            try:
                ZoneInfo(patch["timezone"])
            except (KeyError, ValueError):
                raise ValueError(f"Invalid timezone: {patch['timezone']}")

        for key, value in patch.items():
            if value is not None and hasattr(schedule, key):
                setattr(schedule, key, value)

        await db.flush()
        return schedule

    @staticmethod
    async def delete_schedule(
        db: AsyncSession, tenant: Tenant, schedule_id: uuid.UUID,
    ) -> bool:
        schedule = await ScheduleService.get_schedule(db, tenant, schedule_id)
        if not schedule:
            return False
        schedule.active = False
        await db.flush()
        return True

    @staticmethod
    def is_schedule_due(schedule: Schedule) -> bool:
        """Check if a schedule should fire now. All comparisons in UTC."""
        tz = ZoneInfo(schedule.timezone)
        now_local = datetime.now(tz)

        cron = croniter(schedule.cron_expression, now_local)
        prev_run_local = cron.get_prev(datetime)

        if schedule.last_run_at is None:
            return True

        # Compare in UTC to avoid timezone drift issues
        prev_run_utc = prev_run_local.astimezone(timezone.utc)
        last_run_utc = schedule.last_run_at.astimezone(timezone.utc) if schedule.last_run_at.tzinfo else schedule.last_run_at.replace(tzinfo=timezone.utc)
        return prev_run_utc > last_run_utc

    @staticmethod
    def pick_topic(schedule: Schedule) -> str | None:
        """Pick a random topic from the pool, or None."""
        pool = schedule.topic_pool
        if not pool or not isinstance(pool, list) or len(pool) == 0:
            return None
        return random.choice(pool)
