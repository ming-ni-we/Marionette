"""Images 路由（出图任务）。本轮返回 501（下一轮实现）。"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.errors import UnimplementedError
from app.schemas.asset import ImageJob, ImageJobCreateRequest
from app.schemas.common import Envelope

router = APIRouter(tags=["Images"])


@router.post(
    "/images/jobs",
    response_model=Envelope[ImageJob],
    status_code=202,
    summary="触发一次图像生成",
)
async def create_image_job(payload: ImageJobCreateRequest) -> Envelope[ImageJob]:
    raise UnimplementedError("触发出图")


@router.get(
    "/images/jobs/{jobId}", response_model=Envelope[ImageJob], summary="查询图像生成任务"
)
async def get_image_job(jobId: str) -> Envelope[ImageJob]:
    raise UnimplementedError("查询出图任务")
