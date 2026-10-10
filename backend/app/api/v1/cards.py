"""Cards 路由。本轮除路径/方法/参数对齐外，返回 501（下一轮实现）。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.deps import (
    LimitParam,
    OrderParam,
    PageParam,
    QParam,
    SortParam,
    TagsParam,
)
from app.core.errors import UnimplementedError
from app.schemas.common import Envelope, Paged
from app.schemas.content import Card, CardInput

router = APIRouter(tags=["Cards"])


@router.get("/cards", response_model=Envelope[Paged[Card]], summary="列出角色卡")
async def list_cards(
    q: QParam = None,
    tags: TagsParam = None,
    sort: SortParam = "updated_at",
    order: OrderParam = "desc",
    page: PageParam = 1,
    limit: LimitParam = 20,
) -> Envelope[Paged[Card]]:
    raise UnimplementedError("角色卡列表")


@router.post(
    "/cards", response_model=Envelope[Card], status_code=201, summary="创建角色卡"
)
async def create_card(payload: CardInput) -> Envelope[Card]:
    raise UnimplementedError("创建角色卡")


@router.get(
    "/cards/{cardId}", response_model=Envelope[Card], summary="获取角色卡"
)
async def get_card(cardId: str) -> Envelope[Card]:
    raise UnimplementedError("获取角色卡")


@router.patch(
    "/cards/{cardId}", response_model=Envelope[Card], summary="部分更新角色卡"
)
async def update_card(cardId: str, payload: CardInput) -> Envelope[Card]:
    raise UnimplementedError("更新角色卡")


@router.delete("/cards/{cardId}", response_model=Envelope[dict], summary="删除角色卡")
async def delete_card(cardId: str) -> Envelope[dict]:
    raise UnimplementedError("删除角色卡")
