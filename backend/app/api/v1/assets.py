"""Assets 路由：资产查询 / 上传 / 元数据 / 二进制内容（schemas.md §10）。

查询复用统一检索基元；无数据时返回空分页（不 500）。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import Response

from app.api.v1.deps import (
    AssetKindParam,
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
from app.schemas.asset import Asset
from app.schemas.common import Envelope, Paged
from app.services.assets import AssetSvc

router = APIRouter(tags=["Assets"])


@router.get("/assets", response_model=Envelope[Paged[Asset]], summary="列出资产")
async def list_assets(
    db: DbSession,
    q: QParam = None,
    tags: TagsParam = None,
    card_id: str | None = None,
    session_id: str | None = None,
    kind: AssetKindParam = None,
    sort: SortParam = "created_at",
    order: OrderParam = "desc",
    page: PageParam = 1,
    limit: LimitParam = 20,
) -> Envelope[Paged[Asset]]:
    items, meta = await AssetSvc(db).list(
        to_list_query(q=q, tags=tags, sort=sort, order=order, page=page, limit=limit),
        card_id=card_id,
        session_id=session_id,
        kind=kind,
    )
    return Envelope(data=Paged[Asset](items=items, **meta))


@router.post("/assets", response_model=Envelope[Asset], status_code=201, summary="上传资产")
async def upload_asset(
    db: DbSession,
    file: Annotated[UploadFile, File()],
    kind: Annotated[str, Form()],
    card_id: Annotated[str | None, Form()] = None,
    session_id: Annotated[str | None, Form()] = None,
    tags: Annotated[str | None, Form()] = None,
) -> Envelope[Asset]:
    payload = await file.read()
    data = await AssetSvc(db).create(
        data=payload,
        filename=file.filename or "upload.bin",
        content_type=file.content_type or "application/octet-stream",
        kind=kind,
        card_id=card_id,
        session_id=session_id,
        tags=[t for t in (tags or "").split(",")],
    )
    return Envelope(data=data)


@router.get("/assets/{assetId}", response_model=Envelope[Asset], summary="获取资产元数据")
async def get_asset(db: DbSession, assetId: str) -> Envelope[Asset]:
    svc = AssetSvc(db)
    return Envelope(data=svc.serialize(await svc.get(assetId)))


@router.delete("/assets/{assetId}", response_model=Envelope[dict], summary="删除资产")
async def delete_asset(db: DbSession, assetId: str) -> Envelope[dict]:
    return Envelope(data=deleted(await AssetSvc(db).delete(assetId)))


@router.get(
    "/assets/{assetId}/content",
    summary="获取资产二进制内容",
    responses={200: {"description": "二进制内容", "content": {"application/octet-stream": {}}}},
)
async def get_asset_content(db: DbSession, assetId: str) -> Response:
    data, content_type, filename = await AssetSvc(db).read_content(assetId)
    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get(
    "/cards/{cardId}/assets",
    response_model=Envelope[Paged[Asset]],
    summary="列出某角色的资产（等价于 /assets?card_id={cardId}）",
)
async def list_card_assets(
    db: DbSession,
    cardId: str,
    q: QParam = None,
    tags: TagsParam = None,
    kind: AssetKindParam = None,
    sort: SortParam = "created_at",
    order: OrderParam = "desc",
    page: PageParam = 1,
    limit: LimitParam = 20,
) -> Envelope[Paged[Asset]]:
    items, meta = await AssetSvc(db).list(
        to_list_query(q=q, tags=tags, sort=sort, order=order, page=page, limit=limit),
        card_id=cardId,
        kind=kind,
    )
    return Envelope(data=Paged[Asset](items=items, **meta))
