"""
saas/api/admin.py
Admin panel endpoints — cross-tenant operations.
"""
import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from saas.auth.admin import get_admin_tenant
from saas.database.session import get_db
from saas.models.tenant import Tenant
from saas.schemas.admin import AdminJobResponse, AdminMetrics, TenantDetail, TenantListItem, TenantPatch
from saas.schemas.common import APIEnvelope, PaginationMeta
from saas.services.admin_service import AdminService

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/tenants")
async def list_tenants(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    _admin: Tenant = Depends(get_admin_tenant),
    db: AsyncSession = Depends(get_db),
):
    tenants, total = await AdminService.list_tenants(db, page, limit)
    return APIEnvelope(
        data=[TenantListItem(**t) for t in tenants],
        meta=PaginationMeta(total=total, page=page, limit=limit, pages=math.ceil(total / limit) if total else 0),
    )


@router.get("/tenants/{tenant_id}")
async def get_tenant(
    tenant_id: uuid.UUID,
    _admin: Tenant = Depends(get_admin_tenant),
    db: AsyncSession = Depends(get_db),
):
    detail = await AdminService.get_tenant(db, tenant_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return APIEnvelope(data=TenantDetail(**detail))


@router.patch("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: uuid.UUID,
    body: TenantPatch,
    _admin: Tenant = Depends(get_admin_tenant),
    db: AsyncSession = Depends(get_db),
):
    patch = body.model_dump(exclude_none=True)
    tenant = await AdminService.update_tenant(db, tenant_id, patch)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return APIEnvelope(data={"updated": True})


@router.get("/jobs")
async def list_jobs(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    tenant_id: uuid.UUID | None = Query(default=None),
    _admin: Tenant = Depends(get_admin_tenant),
    db: AsyncSession = Depends(get_db),
):
    jobs, total = await AdminService.list_jobs(db, page, limit, status, tenant_id)
    return APIEnvelope(
        data=[AdminJobResponse(**j) for j in jobs],
        meta=PaginationMeta(total=total, page=page, limit=limit, pages=math.ceil(total / limit) if total else 0),
    )


@router.get("/metrics")
async def get_metrics(
    _admin: Tenant = Depends(get_admin_tenant),
    db: AsyncSession = Depends(get_db),
):
    metrics = await AdminService.get_metrics(db)
    return APIEnvelope(data=AdminMetrics(**metrics))
