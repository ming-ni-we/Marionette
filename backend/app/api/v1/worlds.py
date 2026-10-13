"""Worlds 路由：世界观 CRUD + 检索（剧情引擎）。

路由只做编排：解析入参 -> 调 WorldSvc -> 套统一信封。业务逻辑一律在 services/。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.v1.deps import (
    DbSession,
    LimitParam,
    PageParam,
    QParam,
    TagsParam,
    to_list_query,
)
from app.core.envelope import deleted
from app.schemas.common import Envelope, Paged
from app.schemas.world import World as WorldSchema
from app.schemas.world import WorldInput, WorldPatch
from app.services.world import WorldSvc

router = APIRouter(tags=["Worlds"])


@router.get("/worlds", response_model=Envelope[Paged[WorldSchema]], summary="列出世界观")
async def list_worlds(
    db: DbSession,
    q: QParam = None,
    tags: TagsParam = None,
    page: PageParam = 1,
    limit: LimitParam = 20,
) -> Envelope[Paged[WorldSchema]]:
    query = to_list_query(q=q, tags=tags, page=page, limit=limit)
    items, meta = await WorldSvc(db).list(
        q=query.q, tags=query.tags, page=query.page, limit=query.limit
    )
    return Envelope(data=Paged[WorldSchema](items=items, **meta))


@router.post("/worlds", response_model=Envelope[WorldSchema], status_code=201, summary="创建世界观")
async def create_world(db: DbSession, payload: WorldInput) -> Envelope[WorldSchema]:
    row = await WorldSvc(db).create(payload.model_dump(mode="json"))
    return Envelope(data=WorldSchema.model_validate(row))


@router.get("/worlds/{worldId}", response_model=Envelope[WorldSchema], summary="获取世界观")
async def get_world(db: DbSession, worldId: str) -> Envelope[WorldSchema]:
    return Envelope(data=WorldSchema.model_validate(await WorldSvc(db).get(worldId)))


@router.patch("/worlds/{worldId}", response_model=Envelope[WorldSchema], summary="部分更新世界观")
async def update_world(
    db: DbSession, worldId: str, payload: WorldPatch
) -> Envelope[WorldSchema]:
    patch: dict[str, Any] = payload.model_dump(mode="json", exclude_unset=True)
    row = await WorldSvc(db).update(worldId, patch)
    return Envelope(data=WorldSchema.model_validate(row))


@router.delete("/worlds/{worldId}", response_model=Envelope[dict], summary="删除世界观")
async def delete_world(db: DbSession, worldId: str) -> Envelope[dict]:
    return Envelope(data=deleted(await WorldSvc(db).delete(worldId)))
