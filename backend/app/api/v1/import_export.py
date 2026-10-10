"""ImportExport 路由。本轮返回 501（下一轮实现）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from app.core.errors import UnimplementedError
from app.schemas.common import Envelope
from app.schemas.import_export import ExportBundleRequest, ImportResult

router = APIRouter(tags=["ImportExport"])


@router.post(
    "/import/card",
    response_model=Envelope[ImportResult],
    status_code=201,
    summary="导入角色卡（SillyTavern V1/V2/V3 JSON/PNG/WEBP）",
)
async def import_card(
    file: Annotated[UploadFile, File()],
    on_conflict: Annotated[str, Form()] = "rename",
) -> Envelope[ImportResult]:
    raise UnimplementedError("导入角色卡")


@router.post(
    "/import/worldbook",
    response_model=Envelope[ImportResult],
    status_code=201,
    summary="导入世界书（SillyTavern World Info JSON）",
)
async def import_worldbook(
    file: Annotated[UploadFile, File()],
    on_conflict: Annotated[str, Form()] = "rename",
) -> Envelope[ImportResult]:
    raise UnimplementedError("导入世界书")


@router.post(
    "/export/bundle",
    summary="导出可移植包（卡片+世界书+预设+素材 zip）",
    responses={200: {"description": "zip 文件", "content": {"application/zip": {}}}},
)
async def export_bundle(payload: ExportBundleRequest) -> None:
    raise UnimplementedError("导出可移植包")


@router.get(
    "/export/card/{cardId}",
    summary="导出单卡片为 SillyTavern V2（json / png）",
    responses={
        200: {
            "description": "卡片文件",
            "content": {"application/json": {}, "image/png": {}},
        }
    },
)
async def export_card(cardId: str, format: str = "json") -> None:
    raise UnimplementedError("导出角色卡")
