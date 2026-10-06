from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Register(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class Login(BaseModel):
    email: str = Field(min_length=5, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=1, max_length=128)


class EmailRequest(BaseModel):
    email: EmailStr


class Reset(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=12, max_length=128)


class Verify(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: Literal["SUPER_ADMIN", "ADMIN", "COACH", "CLIENT", "LEAD"]
    email_verified: bool
    active: bool
    timezone: str
    assigned_coach_id: str | None
    demo: bool


class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class Deactivate(BaseModel):
    password: str = Field(min_length=1, max_length=128)
