"""Onboarding 路由（首启向导：内置示例内容）。本轮返回 501（下一轮实现）。"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.errors import UnimplementedError
from app.schemas.common import Envelope
from app.schemas.import_export import OnboardingSamplesResult

router = APIRouter(tags=["Config"])


@router.post(
    "/onboarding/samples",
    response_model=Envelope[OnboardingSamplesResult],
    status_code=201,
    summary="安装内置示例内容（3–5 张带世界书与默认预设的示例卡）",
)
async def install_sample_content() -> Envelope[OnboardingSamplesResult]:
    raise UnimplementedError("安装示例内容")
