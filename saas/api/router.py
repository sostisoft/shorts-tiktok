"""
saas/api/router.py
Main API router — aggregates all sub-routers.
"""
from fastapi import APIRouter

from saas.api.ab_tests import router as ab_tests_router
from saas.api.admin import router as admin_router
from saas.api.analytics import router as analytics_router
from saas.api.auth import router as auth_router
from saas.api.billing import router as billing_router
from saas.api.billing import webhook_router as stripe_webhook_router
from saas.api.channels import router as channels_router
from saas.api.health import router as health_router
from saas.api.schedules import router as schedules_router
from saas.api.templates import router as templates_router
from saas.api.trends import router as trends_router
from saas.api.usage import router as usage_router
from saas.api.videos import router as videos_router
from saas.api.webhooks import router as webhooks_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(templates_router)
api_router.include_router(videos_router)
api_router.include_router(channels_router)
api_router.include_router(schedules_router)
api_router.include_router(usage_router)
api_router.include_router(analytics_router)
api_router.include_router(trends_router)
api_router.include_router(ab_tests_router)
api_router.include_router(webhooks_router)
api_router.include_router(billing_router)
api_router.include_router(stripe_webhook_router)
api_router.include_router(admin_router)
