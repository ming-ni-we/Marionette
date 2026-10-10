"""WorldBooks 路由。本轮返回 501（下一轮实现）。"""

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
from app.schemas.content import (
    WorldBook,
    WorldBookInput,
    WorldBookTestRequest,
    WorldBookTestResult,
)

router = APIRouter(tags=["WorldBooks"])


@router.get("/worldbooks", response_model=Envelope[Paged[WorldBook]], summary="列出世界书")
async def list_worldbooks(
    q: QParam = None,
    tags: TagsParam = None,
    sort: SortParam = "updated_at",
    order: OrderParam = "desc",
    page: PageParam = 1,
    limit: LimitParam = 20,
) -> Envelope[Paged[WorldBook]]:
    raise UnimplementedError("世界书列表")


@router.post(
    "/worldbooks", response_model=Envelope[WorldBook], status_code=201, summary="创建世界书"
)
async def create_worldbook(payload: WorldBookInput) -> Envelope[WorldBook]:
    raise UnimplementedError("创建世界书")


@router.get(
    "/worldbooks/{worldBookId}", response_model=Envelope[WorldBook], summary="获取世界书"
)
async def get_worldbook(worldBookId: str) -> Envelope[WorldBook]:
    raise UnimplementedError("获取世界书")


@router.patch(
    "/worldbooks/{worldBookId}", response_model=Envelope[WorldBook], summary="部分更新世界书"
)
async def update_worldbook(worldBookId: str, payload: WorldBookInput) -> Envelope[WorldBook]:
    raise UnimplementedError("更新世界书")


@router.delete(
    "/worldbooks/{worldBookId}", response_model=Envelope[dict], summary="删除世界书"
)
async def delete_worldbook(worldBookId: str) -> Envelope[dict]:
    raise UnimplementedError("删除世界书")


@router.post(
    "/worldbooks/{worldBookId}/test",
    response_model=Envelope[WorldBookTestResult],
    summary="世界书触发自测（不落库）",
)
async def test_worldbook(
    worldBookId: str, payload: WorldBookTestRequest
) -> Envelope[WorldBookTestResult]:
    raise UnimplementedError("世界书触发自测")
