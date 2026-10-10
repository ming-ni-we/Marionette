"""访问控制 Schema（SPEC §5 Auth 分组；本轮新增端点）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    password: str = Field(description="单用户访问口令")


class LoginResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    authenticated: bool = True
    expires_at: datetime | None = None
    message: str = ""


class SessionStatusResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    authenticated: bool = False
    subject: str | None = None
    expires_at: datetime | None = None


class LogoutResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    logged_out: bool = True
