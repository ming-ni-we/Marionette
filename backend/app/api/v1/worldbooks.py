"""WorldBooks 路由：世界书 CRUD + 触发自测（AC-08）。

自测端点不落库：读库里的世界书 -> 交给 WorldInfoEngine 裁决 -> 返回逐条 trace。
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
from app.schemas.content import (
    WorldBook,
    WorldBookInput,
    WorldBookTestRequest,
    WorldBookTestResult,
)
from app.services.content import content_service
from app.services.world_info import WorldInfoEngine

router = APIRouter(tags=["WorldBooks"])
_engine = WorldInfoEngine()


@router.get("/worldbooks", response_model=Envelope[Paged[WorldBook]], summary="列出世界书")
async def list_worldbooks(
    db: DbSession,
    q: QParam = None,
    tags: TagsParam = None,
    sort: SortParam = "updated_at",
    order: OrderParam = "desc",
    page: PageParam = 1,
    limit: LimitParam = 20,
) -> Envelope[Paged[WorldBook]]:
    items, meta = await content_service(db, "worldbook").list(
        to_list_query(q=q, tags=tags, sort=sort, order=order, page=page, limit=limit)
    )
    return Envelope(data=Paged[WorldBook](items=items, **meta))


@router.post(
    "/worldbooks", response_model=Envelope[WorldBook], status_code=201, summary="创建世界书"
)
async def create_worldbook(db: DbSession, payload: WorldBookInput) -> Envelope[WorldBook]:
    svc = content_service(db, "worldbook")
    return Envelope(data=svc.serialize(await svc.create(payload.model_dump(mode="json"))))


@router.get("/worldbooks/{worldBookId}", response_model=Envelope[WorldBook], summary="获取世界书")
async def get_worldbook(db: DbSession, worldBookId: str) -> Envelope[WorldBook]:
    svc = content_service(db, "worldbook")
    return Envelope(data=svc.serialize(await svc.get(worldBookId)))


@router.patch(
    "/worldbooks/{worldBookId}", response_model=Envelope[WorldBook], summary="部分更新世界书"
)
async def update_worldbook(
    db: DbSession, worldBookId: str, payload: dict[str, Any]
) -> Envelope[WorldBook]:
    svc = content_service(db, "worldbook")
    return Envelope(data=svc.serialize(await svc.update(worldBookId, payload)))


@router.delete(
    "/worldbooks/{worldBookId}", response_model=Envelope[dict], summary="删除世界书"
)
async def delete_worldbook(db: DbSession, worldBookId: str) -> Envelope[dict]:
    return Envelope(data=deleted(await content_service(db, "worldbook").delete(worldBookId)))


@router.post(
    "/worldbooks/{worldBookId}/test",
    response_model=Envelope[WorldBookTestResult],
    summary="世界书触发自测（不落库）",
)
async def test_worldbook(
    db: DbSession, worldBookId: str, payload: WorldBookTestRequest
) -> Envelope[WorldBookTestResult]:
    row = await content_service(db, "worldbook").get(worldBookId)
    result = _engine.test(row.data, payload.sample_text, scan_depth=payload.scan_depth)
    return Envelope(data=WorldBookTestResult.model_validate(result))
