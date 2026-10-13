"""API 装配层。

公开路由（免鉴权）：System（health/info）与 Auth。
受保护路由：其余全部 —— 挂 `require_auth` 依赖，未带有效令牌一律 401（AC-02）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1 import (
    assets,
    auth,
    cards,
    images,
    import_export,
    onboarding,
    presets,
    sessions,
    system,
    telemetry,
    worldbooks,
    worlds,
)
from app.api.v1 import (
    config as config_routes,
)
from app.api.v1.deps import require_auth

api_router = APIRouter()

# ---- 公开（health check 必须免鉴权，否则容器 healthcheck / 监控无法工作） ----
api_router.include_router(system.router)
api_router.include_router(auth.router)

# ---- 受保护（AC-02） ----
protected = APIRouter(dependencies=[Depends(require_auth)])
for _module in (
    cards,
    worldbooks,
    presets,
    worlds,
    sessions,
    images,
    assets,
    import_export,
    config_routes,
    onboarding,
    telemetry,
):
    protected.include_router(_module.router)
api_router.include_router(protected)

__all__ = ["api_router"]
