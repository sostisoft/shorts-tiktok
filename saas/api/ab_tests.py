"""
saas/api/ab_tests.py
A/B testing endpoints.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from saas.auth.api_key import get_current_tenant
from saas.database.session import get_db
from saas.models.tenant import Tenant
from saas.schemas.ab_test import ABTestCreate, ABTestResponse
from saas.schemas.common import APIEnvelope
from saas.services.ab_test_service import ABTestService

router = APIRouter(prefix="/api/ab-tests", tags=["ab-tests"])


@router.post("")
async def create_ab_test(
    body: ABTestCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    test = await ABTestService.create_test(
        db, tenant, body.name, body.topic, body.template_a, body.template_b,
    )
    return APIEnvelope(data=ABTestResponse.model_validate(test))


@router.get("")
async def list_ab_tests(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    tests = await ABTestService.list_tests(db, tenant)
    return APIEnvelope(data=[ABTestResponse.model_validate(t) for t in tests])


@router.get("/{test_id}")
async def get_ab_test(
    test_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    detail = await ABTestService.get_test_detail(db, tenant, test_id)
    if not detail:
        raise HTTPException(status_code=404, detail="A/B test not found")
    return APIEnvelope(data=detail)


@router.post("/{test_id}/evaluate")
async def evaluate_ab_test(
    test_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    winner = await ABTestService.evaluate_winner(db, tenant, test_id)
    if winner is None:
        return APIEnvelope(data={"winner": None, "message": "No analytics data yet"})
    return APIEnvelope(data={"winner": winner})
