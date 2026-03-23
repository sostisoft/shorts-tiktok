"""
saas/auth/rate_limiter.py
Redis-based sliding window rate limiter per tenant/plan.
"""
import time

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis

from saas.config import PlanTier, get_settings
from saas.models.tenant import Tenant

_redis_client: Redis | None = None


async def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def close_redis():
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


# Lua script for atomic sliding window rate limit check
_SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

-- Remove expired entries
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

-- Count current requests in window
local count = redis.call('ZCARD', key)

if count >= limit then
    return 0
end

-- Add current request
redis.call('ZADD', key, now, now .. '-' .. math.random(1000000))
redis.call('EXPIRE', key, window)

return 1
"""


class RateLimiter:
    """FastAPI dependency that enforces per-plan rate limits."""

    async def __call__(
        self,
        request: Request,
        tenant: Tenant = Depends(),
    ) -> None:
        settings = get_settings()
        plan = PlanTier(tenant.plan)
        limit = settings.rate_limit_for_plan(plan)

        redis = await get_redis()
        key = f"ratelimit:{tenant.id}"
        window = 60  # 1 minute window
        now = time.time()

        allowed = await redis.eval(
            _SLIDING_WINDOW_SCRIPT, 1, key, window, limit, now,
        )

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded ({limit} requests/minute for {plan.value} plan)",
                headers={"Retry-After": "60"},
            )


rate_limiter = RateLimiter()
