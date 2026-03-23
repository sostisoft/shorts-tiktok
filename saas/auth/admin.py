"""
saas/auth/admin.py
Admin authentication dependency — requires tenant.is_admin == True.
"""
from fastapi import Depends, HTTPException, status

from saas.auth.api_key import get_current_tenant
from saas.models.tenant import Tenant


async def get_admin_tenant(
    tenant: Tenant = Depends(get_current_tenant),
) -> Tenant:
    """FastAPI dependency: require authenticated admin tenant."""
    if not tenant.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return tenant
