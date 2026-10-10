"""Onboarding 路由（首启向导：内置示例内容）。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.deps import DbSession
from app.schemas.common import Envelope
from app.schemas.import_export import OnboardingSamplesResult
from app.services.onboarding import install_samples

router = APIRouter(tags=["Config"])


@router.post(
    "/onboarding/samples",
    response_model=Envelope[OnboardingSamplesResult],
    status_code=201,
    summary="安装内置示例内容（3–5 张带世界书与默认预设的示例卡）",
)
async def install_sample_content(db: DbSession) -> Envelope[OnboardingSamplesResult]:
    result = await install_samples(db)
    return Envelope(data=OnboardingSamplesResult.model_validate(result))
