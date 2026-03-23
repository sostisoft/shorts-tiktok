"""
saas/schemas/auth.py
Authentication and registration schemas.
"""
import uuid

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    tenant_id: uuid.UUID
    name: str
    email: str
    plan: str
    api_key: str
    is_admin: bool


class MeResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    plan: str
    is_admin: bool

    model_config = {"from_attributes": True}
