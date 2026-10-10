"""Presets 路由：预设 CRUD + 检索。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.v1.deps import (
    DbSession,
    LimitParam,
    OrderParam,
    PageParam,
    QParam,
    SortParam,
    to_list_query,
)
from app.core.envelope import deleted
from app.schemas.common import Envelope, Paged
from app.schemas.content import Preset, PresetInput
from app.services.content import content_service

router = APIRouter(tags=["Presets"])


@router.get("/presets", response_model=Envelope[Paged[Preset]], summary="列出预设")
async def list_presets(
    db: DbSession,
    q: QParam = None,
    sort: SortParam = "updated_at",
    order: OrderParam = "desc",
    page: PageParam = 1,
    limit: LimitParam = 20,
) -> Envelope[Paged[Preset]]:
    items, meta = await content_service(db, "preset").list(
        to_list_query(q=q, sort=sort, order=order, page=page, limit=limit)
    )
    return Envelope(data=Paged[Preset](items=items, **meta))


@router.post("/presets", response_model=Envelope[Preset], status_code=201, summary="创建预设")
async def create_preset(db: DbSession, payload: PresetInput) -> Envelope[Preset]:
    svc = content_service(db, "preset")
    return Envelope(data=svc.serialize(await svc.create(payload.model_dump(mode="json"))))


@router.get("/presets/{presetId}", response_model=Envelope[Preset], summary="获取预设")
async def get_preset(db: DbSession, presetId: str) -> Envelope[Preset]:
    svc = content_service(db, "preset")
    return Envelope(data=svc.serialize(await svc.get(presetId)))


@router.patch("/presets/{presetId}", response_model=Envelope[Preset], summary="部分更新预设")
async def update_preset(
    db: DbSession, presetId: str, payload: dict[str, Any]
) -> Envelope[Preset]:
    svc = content_service(db, "preset")
    return Envelope(data=svc.serialize(await svc.update(presetId, payload)))


@router.delete("/presets/{presetId}", response_model=Envelope[dict], summary="删除预设")
async def delete_preset(db: DbSession, presetId: str) -> Envelope[dict]:
    return Envelope(data=deleted(await content_service(db, "preset").delete(presetId)))
