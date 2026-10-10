"""通用信封与分页模型（openapi.yaml components.schemas）。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Envelope[T](BaseModel):
    """统一响应信封：code=0 成功，非 0 为错误码。"""

    model_config = ConfigDict(extra="allow")

    code: int = 0
    data: T | None = None
    message: str = ""


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: int = 5000
    data: object | None = None
    message: str = ""
    error_class: str | None = None
    model_seen: str | None = None


class Paged[T](BaseModel):
    model_config = ConfigDict(extra="allow")

    total: int = 0
    page: int = 1
    limit: int = 20
    hasMore: bool = Field(default=False)
    items: list[T] = Field(default_factory=list)


class PaginationMeta(BaseModel):
    total: int
    page: int
    limit: int
    hasMore: bool = False
