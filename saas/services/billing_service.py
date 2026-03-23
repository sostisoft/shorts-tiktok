"""
saas/services/billing_service.py
Stripe billing: checkout, portal, webhook handling.
"""
import logging

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saas.config import PlanTier, get_settings
from saas.models.tenant import Tenant

logger = logging.getLogger("saas.services.billing")


def _init_stripe():
    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key


class BillingService:

    @staticmethod
    async def create_checkout_session(
        db: AsyncSession, tenant: Tenant, plan: PlanTier,
    ) -> str:
        """Create a Stripe Checkout Session. Returns the checkout URL."""
        _init_stripe()
        settings = get_settings()

        price_map = {
            PlanTier.STARTER: settings.stripe_price_starter,
            PlanTier.GROWTH: settings.stripe_price_growth,
            PlanTier.AGENCY: settings.stripe_price_agency,
        }
        price_id = price_map.get(plan)
        if not price_id:
            raise ValueError(f"No Stripe price configured for plan: {plan}")

        # Create or reuse Stripe customer
        if not tenant.stripe_customer_id:
            customer = stripe.Customer.create(
                email=tenant.email,
                name=tenant.name,
                metadata={"tenant_id": str(tenant.id)},
            )
            tenant.stripe_customer_id = customer.id
            await db.flush()

        session = stripe.checkout.Session.create(
            customer=tenant.stripe_customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{settings.dashboard_url}/dashboard/billing?status=success",
            cancel_url=f"{settings.dashboard_url}/dashboard/billing?status=cancel",
            metadata={"tenant_id": str(tenant.id), "plan": plan.value},
        )

        logger.info(f"Checkout session created for {tenant.email} -> {plan.value}")
        return session.url

    @staticmethod
    async def create_portal_session(db: AsyncSession, tenant: Tenant) -> str:
        """Create a Stripe Customer Portal session. Returns the portal URL."""
        _init_stripe()
        settings = get_settings()

        if not tenant.stripe_customer_id:
            raise ValueError("No Stripe customer ID. Subscribe first.")

        session = stripe.billing_portal.Session.create(
            customer=tenant.stripe_customer_id,
            return_url=f"{settings.dashboard_url}/dashboard/billing",
        )
        return session.url

    @staticmethod
    async def handle_webhook_event(db: AsyncSession, event: dict):
        """Process a Stripe webhook event."""
        event_type = event["type"]
        data = event["data"]["object"]

        if event_type == "checkout.session.completed":
            await BillingService._handle_checkout_completed(db, data)
        elif event_type == "customer.subscription.updated":
            await BillingService._handle_subscription_updated(db, data)
        elif event_type == "customer.subscription.deleted":
            await BillingService._handle_subscription_deleted(db, data)
        elif event_type == "invoice.payment_failed":
            await BillingService._handle_payment_failed(db, data)
        else:
            logger.debug(f"Unhandled Stripe event: {event_type}")

    @staticmethod
    async def _handle_checkout_completed(db: AsyncSession, session_data: dict):
        customer_id = session_data.get("customer")
        subscription_id = session_data.get("subscription")
        plan = session_data.get("metadata", {}).get("plan", "starter")

        result = await db.execute(
            select(Tenant).where(Tenant.stripe_customer_id == customer_id)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            logger.warning(f"No tenant for Stripe customer {customer_id}")
            return

        tenant.plan = plan
        tenant.stripe_subscription_id = subscription_id
        tenant.subscription_status = "active"
        await db.flush()

        logger.info(f"Checkout completed: {tenant.email} -> {plan}")

    @staticmethod
    async def _handle_subscription_updated(db: AsyncSession, sub_data: dict):
        customer_id = sub_data.get("customer")
        result = await db.execute(
            select(Tenant).where(Tenant.stripe_customer_id == customer_id)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            return

        tenant.subscription_status = sub_data.get("status", "active")
        # Sync plan from price
        items = sub_data.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id")
            new_plan = BillingService._price_to_plan(price_id)
            if new_plan:
                tenant.plan = new_plan.value

        period_end = sub_data.get("current_period_end")
        if period_end:
            from datetime import datetime, timezone
            tenant.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)

        await db.flush()
        logger.info(f"Subscription updated: {tenant.email} -> {tenant.plan} ({tenant.subscription_status})")

    @staticmethod
    async def _handle_subscription_deleted(db: AsyncSession, sub_data: dict):
        customer_id = sub_data.get("customer")
        result = await db.execute(
            select(Tenant).where(Tenant.stripe_customer_id == customer_id)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            return

        tenant.plan = "trial"
        tenant.subscription_status = "canceled"
        await db.flush()
        logger.info(f"Subscription canceled: {tenant.email}")

    @staticmethod
    async def _handle_payment_failed(db: AsyncSession, invoice_data: dict):
        customer_id = invoice_data.get("customer")
        result = await db.execute(
            select(Tenant).where(Tenant.stripe_customer_id == customer_id)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            return

        tenant.subscription_status = "past_due"
        await db.flush()
        logger.warning(f"Payment failed: {tenant.email}")

    @staticmethod
    def _price_to_plan(price_id: str) -> PlanTier | None:
        settings = get_settings()
        mapping = {
            settings.stripe_price_starter: PlanTier.STARTER,
            settings.stripe_price_growth: PlanTier.GROWTH,
            settings.stripe_price_agency: PlanTier.AGENCY,
        }
        return mapping.get(price_id)
