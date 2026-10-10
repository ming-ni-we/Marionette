"""Presets 路由。本轮返回 501（下一轮实现）。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.deps import LimitParam, OrderParam, PageParam, QParam, SortParam
from app.core.errors import UnimplementedError
from app.schemas.common import Envelope, Paged
from app.schemas.content import Preset, PresetInput

router = APIRouter(tags=["Presets"])


@router.get("/presets", response_model=Envelope[Paged[Preset]], summary="列出预设")
async def list_presets(
    q: QParam = None,
    sort: SortParam = "updated_at",
    order: OrderParam = "desc",
    page: PageParam = 1,
    limit: LimitParam = 20,
) -> Envelope[Paged[Preset]]:
    raise UnimplementedError("预设列表")


@router.post(
    "/presets", response_model=Envelope[Preset], status_code=201, summary="创建预设"
)
async def create_preset(payload: PresetInput) -> Envelope[Preset]:
    raise UnimplementedError("创建预设")


@router.get("/presets/{presetId}", response_model=Envelope[Preset], summary="获取预设")
async def get_preset(presetId: str) -> Envelope[Preset]:
    raise UnimplementedError("获取预设")


@router.patch("/presets/{presetId}", response_model=Envelope[Preset], summary="部分更新预设")
async def update_preset(presetId: str, payload: PresetInput) -> Envelope[Preset]:
    raise UnimplementedError("更新预设")


@router.delete("/presets/{presetId}", response_model=Envelope[dict], summary="删除预设")
async def delete_preset(presetId: str) -> Envelope[dict]:
    raise UnimplementedError("删除预设")
