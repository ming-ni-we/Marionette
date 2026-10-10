"""Assets 路由（含 /cards/{cardId}/assets 便捷子集）。本轮返回 501（下一轮实现）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from app.api.v1.deps import (
    AssetKindParam,
    LimitParam,
    OrderParam,
    PageParam,
    QParam,
    SortParam,
    TagsParam,
)
from app.core.errors import UnimplementedError
from app.schemas.asset import Asset
from app.schemas.common import Envelope, Paged

router = APIRouter(tags=["Assets"])


@router.get("/assets", response_model=Envelope[Paged[Asset]], summary="列出资产")
async def list_assets(
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
    raise UnimplementedError("资产列表")


@router.post(
    "/assets", response_model=Envelope[Asset], status_code=201, summary="上传资产"
)
async def upload_asset(
    file: Annotated[UploadFile, File()],
    kind: Annotated[str, Form()],
    card_id: Annotated[str | None, Form()] = None,
    session_id: Annotated[str | None, Form()] = None,
    tags: Annotated[str | None, Form()] = None,
) -> Envelope[Asset]:
    raise UnimplementedError("上传资产")


@router.get(
    "/assets/{assetId}", response_model=Envelope[Asset], summary="获取资产元数据"
)
async def get_asset(assetId: str) -> Envelope[Asset]:
    raise UnimplementedError("获取资产元数据")


@router.delete("/assets/{assetId}", response_model=Envelope[dict], summary="删除资产")
async def delete_asset(assetId: str) -> Envelope[dict]:
    raise UnimplementedError("删除资产")


@router.get(
    "/assets/{assetId}/content",
    summary="获取资产二进制内容",
    responses={200: {"description": "二进制内容", "content": {"application/octet-stream": {}}}},
)
async def get_asset_content(assetId: str) -> None:
    raise UnimplementedError("获取资产内容")


@router.get(
    "/cards/{cardId}/assets",
    response_model=Envelope[Paged[Asset]],
    summary="列出某角色的资产（等价于 /assets?card_id={cardId}）",
)
async def list_card_assets(
    cardId: str,
    q: QParam = None,
    tags: TagsParam = None,
    kind: AssetKindParam = None,
    sort: SortParam = "created_at",
    order: OrderParam = "desc",
    page: PageParam = 1,
    limit: LimitParam = 20,
) -> Envelope[Paged[Asset]]:
    raise UnimplementedError("角色资产列表")
