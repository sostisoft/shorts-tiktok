"""
saas/api/billing.py
Stripe billing endpoints: checkout, portal, webhook.
"""
import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from saas.auth.api_key import get_current_tenant
from saas.config import PlanTier, get_settings
from saas.database.session import get_db
from saas.models.tenant import Tenant
from saas.schemas.common import APIEnvelope
from saas.services.billing_service import BillingService

logger = logging.getLogger("saas.api.billing")

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.post("/checkout")
async def create_checkout(
    body: dict,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Create Stripe Checkout Session for subscription."""
    plan_str = body.get("plan")
    if not plan_str:
        raise HTTPException(status_code=400, detail="plan is required")

    try:
        plan = PlanTier(plan_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {plan_str}")

    if plan == PlanTier.TRIAL:
        raise HTTPException(status_code=400, detail="Cannot subscribe to trial plan")

    try:
        url = await BillingService.create_checkout_session(db, tenant, plan)
        return APIEnvelope(data={"url": url})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/portal")
async def create_portal(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Create Stripe Customer Portal session."""
    try:
        url = await BillingService.create_portal_session(db, tenant)
        return APIEnvelope(data={"url": url})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status")
async def billing_status(tenant: Tenant = Depends(get_current_tenant)):
    """Get current billing/subscription status."""
    return APIEnvelope(data={
        "plan": tenant.plan,
        "subscription_status": tenant.subscription_status,
        "stripe_customer_id": tenant.stripe_customer_id,
        "current_period_end": tenant.current_period_end.isoformat() if tenant.current_period_end else None,
    })


# Public Stripe webhook — NO API key auth
webhook_router = APIRouter(tags=["billing"])


@webhook_router.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Stripe webhook events. Verifies signature."""
    settings = get_settings()
    payload = await request.body()
    sig = request.headers.get("stripe-signature")

    if not sig:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.stripe_webhook_secret,
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    await BillingService.handle_webhook_event(db, event)
    return {"received": True}
