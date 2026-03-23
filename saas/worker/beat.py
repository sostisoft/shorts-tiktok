"""
saas/worker/beat.py
Periodic Celery tasks — schedule evaluation.
"""
import logging
import os
from datetime import datetime, timezone

from saas.worker.celery_app import app

logger = logging.getLogger("saas.worker.beat")


@app.task(name="saas.worker.beat.check_schedules")
def check_schedules():
    """Evaluate all active schedules and dispatch due pipelines."""
    from saas.worker.tasks import _get_sync_session, dispatch_pipeline
    from saas.models.schedule import Schedule
    from saas.models.tenant import Tenant
    from saas.services.schedule_service import ScheduleService

    session = _get_sync_session()
    try:
        schedules = (
            session.query(Schedule)
            .filter(Schedule.active.is_(True))
            .all()
        )

        for schedule in schedules:
            try:
                if not ScheduleService.is_schedule_due(schedule):
                    continue

                tenant = session.query(Tenant).filter(Tenant.id == schedule.tenant_id).first()
                if not tenant or not tenant.active:
                    continue

                topic = ScheduleService.pick_topic(schedule)
                effective_topic = topic or "finanzas personales"

                job_id = os.urandom(8).hex()
                dispatch_pipeline(
                    job_id=job_id,
                    tenant_id=str(tenant.id),
                    topic=effective_topic,
                    style=schedule.style,
                )

                schedule.last_run_at = datetime.now(timezone.utc)
                session.commit()

                logger.info(
                    f"Schedule fired: {schedule.cron_expression} "
                    f"({schedule.timezone}) for {tenant.name} -> '{effective_topic}'"
                )

            except Exception as e:
                logger.error(f"Schedule {schedule.id} error: {e}")
                session.rollback()

    except Exception as e:
        logger.error(f"check_schedules error: {e}")
    finally:
        session.close()
