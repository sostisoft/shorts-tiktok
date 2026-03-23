"""
saas/api/templates.py
Video template listing endpoint.
"""
from fastapi import APIRouter

from saas.providers.script.templates import get_template_names
from saas.schemas.common import APIEnvelope

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("")
async def list_templates():
    """List available video templates."""
    return APIEnvelope(data=get_template_names())
