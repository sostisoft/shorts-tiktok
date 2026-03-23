"""
saas/schemas/common.py
Shared Pydantic models: API envelope, pagination.
"""
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    total: int
    page: int
    limit: int
    pages: int


class APIEnvelope(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    error: str | None = None
    meta: PaginationMeta | None = None
