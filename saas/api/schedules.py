"""
saas/api/schedules.py
Schedule CRUD endpoints.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from saas.auth.api_key import get_current_tenant
from saas.database.session import get_db
from saas.models.tenant import Tenant
from saas.schemas.common import APIEnvelope
from saas.schemas.schedule import ScheduleCreate, ScheduleResponse, ScheduleUpdate
from saas.services.schedule_service import ScheduleService

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


@router.post("")
async def create_schedule(
    body: ScheduleCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    try:
        schedule = await ScheduleService.create_schedule(
            db, tenant, body.channel_id, body.cron_expression,
            body.timezone, body.topic_pool, body.style,
        )
        return APIEnvelope(data=ScheduleResponse.model_validate(schedule))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
async def list_schedules(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    schedules = await ScheduleService.list_schedules(db, tenant)
    return APIEnvelope(data=[ScheduleResponse.model_validate(s) for s in schedules])


@router.get("/{schedule_id}")
async def get_schedule(
    schedule_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    schedule = await ScheduleService.get_schedule(db, tenant, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return APIEnvelope(data=ScheduleResponse.model_validate(schedule))


@router.patch("/{schedule_id}")
async def update_schedule(
    schedule_id: uuid.UUID,
    body: ScheduleUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    try:
        patch = body.model_dump(exclude_none=True)
        schedule = await ScheduleService.update_schedule(db, tenant, schedule_id, patch)
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        return APIEnvelope(data=ScheduleResponse.model_validate(schedule))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    deleted = await ScheduleService.delete_schedule(db, tenant, schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return APIEnvelope(data={"deleted": True})
