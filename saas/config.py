"""
saas/config.py
Centralized configuration via pydantic-settings.
Reads from environment variables and .env files.
"""
from enum import Enum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PlanTier(str, Enum):
    TRIAL = "trial"
    STARTER = "starter"
    GROWTH = "growth"
    AGENCY = "agency"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database ---
    database_url: str = Field(
        default="postgresql+asyncpg://shortforge:shortforge@localhost:5438/shortforge",
        description="PostgreSQL async connection URL",
    )

    # --- Redis ---
    redis_url: str = Field(
        default="redis://localhost:6382/0",
        description="Redis URL for Celery broker and rate limiter",
    )

    # --- S3 / MinIO ---
    s3_endpoint: str = Field(default="http://localhost:9002")
    s3_bucket: str = Field(default="shortforge-videos")
    s3_access_key: str = Field(default="minioadmin")
    s3_secret_key: str = Field(default="minioadmin")
    s3_region: str = Field(default="us-east-1")

    # --- Security ---
    secret_key: str = Field(
        default="change-me-in-production",
        description="Server-side key for Fernet encryption of channel credentials",
    )
    cors_origins: list[str] = Field(default=["http://localhost:3000"])

    # --- External API keys ---
    anthropic_api_key: str = Field(default="")
    fal_api_key: str = Field(default="")
    kling_api_key: str = Field(default="")
    elevenlabs_api_key: str = Field(default="")

    # --- Stock footage (existing bot vars) ---
    pexels_api_key: str = Field(default="")
    pixabay_api_key: str = Field(default="")

    # --- Rate limits per plan (requests/minute) ---
    rate_limit_trial: int = Field(default=5)
    rate_limit_starter: int = Field(default=10)
    rate_limit_growth: int = Field(default=30)
    rate_limit_agency: int = Field(default=60)

    # --- Video limits per plan (videos/month) ---
    video_limit_trial: int = Field(default=3)
    video_limit_starter: int = Field(default=15)
    video_limit_growth: int = Field(default=30)
    video_limit_agency: int = Field(default=90)

    # --- Celery ---
    celery_task_soft_time_limit: int = Field(default=1800, description="30 min soft limit")
    celery_task_time_limit: int = Field(default=2100, description="35 min hard limit")

    # --- Stripe ---
    stripe_secret_key: str = Field(default="")
    stripe_webhook_secret: str = Field(default="")
    stripe_price_starter: str = Field(default="")
    stripe_price_growth: str = Field(default="")
    stripe_price_agency: str = Field(default="")
    dashboard_url: str = Field(default="http://localhost:3050")

    def rate_limit_for_plan(self, plan: PlanTier) -> int:
        return {
            PlanTier.TRIAL: self.rate_limit_trial,
            PlanTier.STARTER: self.rate_limit_starter,
            PlanTier.GROWTH: self.rate_limit_growth,
            PlanTier.AGENCY: self.rate_limit_agency,
        }[plan]

    def video_limit_for_plan(self, plan: PlanTier) -> int:
        return {
            PlanTier.TRIAL: self.video_limit_trial,
            PlanTier.STARTER: self.video_limit_starter,
            PlanTier.GROWTH: self.video_limit_growth,
            PlanTier.AGENCY: self.video_limit_agency,
        }[plan]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
