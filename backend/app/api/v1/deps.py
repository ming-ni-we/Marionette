"""API 依赖：鉴权、客户端标识、统一检索参数。

访问控制约定（AC-02 与 SPEC §12 的一致性口径）：
  - 公开：`GET /api/v1/system/info`、`GET /api/v1/system/selfcheck`、`/api/v1/auth/*`
    （健康检查必须免鉴权，否则监控与容器 healthcheck 无法工作）
  - 其余所有 `/api/v1/**` 一律要求有效会话令牌，否则 401。
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.registry import get_auth_provider
from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import AuthFailedError
from app.core.security import Principal

DbSession = Annotated[AsyncSession, Depends(get_session)]

# ---------------- 统一检索/分页参数别名（对齐 openapi components.parameters） ----------------
SortField = Literal["created_at", "updated_at", "name", "last_message_at"]
OrderField = Literal["asc", "desc"]
StatusField = Literal["active", "paused", "archived"]
AssetKindField = Literal["avatar", "gallery", "background", "generated"]

QParam = Annotated[
    str | None,
    Query(max_length=200, description="关键词：pg_trgm 子串/模糊匹配，支持中文"),
]
TagsParam = Annotated[list[str] | None, Query(description="标签多值筛选（AND）")]
SortParam = Annotated[SortField, Query(description="排序字段")]
OrderParam = Annotated[OrderField, Query(description="排序方向")]
StatusParam = Annotated[StatusField | None, Query(description="会话状态筛选")]
CardIdQueryParam = Annotated[str | None, Query(description="按归属角色过滤")]
SessionIdQueryParam = Annotated[str | None, Query(description="按归属会话过滤")]
AssetKindParam = Annotated[AssetKindField | None, Query(description="资产类型过滤")]
PageParam = Annotated[int, Query(ge=1, description="页码，从 1 开始")]
LimitParam = Annotated[int, Query(ge=1, le=100, description="每页条数，1–100")]


def client_key(request: Request) -> str:
    """用于限流分桶的客户端标识。Caddy 会写入 X-Real-IP。"""
    forwarded = request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


async def require_auth(request: Request) -> Principal:
    """AC-02：无有效令牌一律 401，且不泄露任何内容数据。"""
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    principal = get_auth_provider().verify_token(token)
    if principal is None:
        raise AuthFailedError()
    return principal


CurrentPrincipal = Annotated[Principal, Depends(require_auth)]
