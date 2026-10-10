"""Cards 路由：角色卡 CRUD + 检索（F16 / AC-13）。

路由只做编排：解析入参 -> 调 ContentSvc -> 套统一信封。业务逻辑一律在 services/。
"""

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
    TagsParam,
    to_list_query,
)
from app.core.envelope import deleted
from app.schemas.common import Envelope, Paged
from app.schemas.content import Card, CardInput
from app.services.content import content_service

router = APIRouter(tags=["Cards"])


@router.get("/cards", response_model=Envelope[Paged[Card]], summary="列出角色卡")
async def list_cards(
    db: DbSession,
    q: QParam = None,
    tags: TagsParam = None,
    sort: SortParam = "updated_at",
    order: OrderParam = "desc",
    page: PageParam = 1,
    limit: LimitParam = 20,
) -> Envelope[Paged[Card]]:
    items, meta = await content_service(db, "card").list(
        to_list_query(q=q, tags=tags, sort=sort, order=order, page=page, limit=limit)
    )
    return Envelope(data=Paged[Card](items=items, **meta))


@router.post("/cards", response_model=Envelope[Card], status_code=201, summary="创建角色卡")
async def create_card(db: DbSession, payload: CardInput) -> Envelope[Card]:
    svc = content_service(db, "card")
    row = await svc.create(payload.model_dump(mode="json"))
    return Envelope(data=svc.serialize(row))


@router.get("/cards/{cardId}", response_model=Envelope[Card], summary="获取角色卡")
async def get_card(db: DbSession, cardId: str) -> Envelope[Card]:
    svc = content_service(db, "card")
    return Envelope(data=svc.serialize(await svc.get(cardId)))


@router.patch("/cards/{cardId}", response_model=Envelope[Card], summary="部分更新角色卡")
async def update_card(db: DbSession, cardId: str, payload: dict[str, Any]) -> Envelope[Card]:
    svc = content_service(db, "card")
    return Envelope(data=svc.serialize(await svc.update(cardId, payload)))


@router.delete("/cards/{cardId}", response_model=Envelope[dict], summary="删除角色卡")
async def delete_card(db: DbSession, cardId: str) -> Envelope[dict]:
    return Envelope(data=deleted(await content_service(db, "card").delete(cardId)))
