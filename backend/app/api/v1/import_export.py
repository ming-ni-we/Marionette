"""ImportExport 路由：Tavern V1/V2/V3 导入、ST V2 导出、可移植包导出（AC-05 / AC-06）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import Response

from app.api.v1.deps import DbSession
from app.core.errors import BadRequestError
from app.schemas.common import Envelope
from app.schemas.import_export import ExportBundleRequest, ImportResult
from app.services.import_export import ImportExportSvc

router = APIRouter(tags=["ImportExport"])


@router.post(
    "/import/card",
    response_model=Envelope[ImportResult],
    status_code=201,
    summary="导入角色卡（SillyTavern V1/V2/V3 JSON/PNG/WEBP）",
)
async def import_card(
    db: DbSession,
    file: Annotated[UploadFile, File()],
    on_conflict: Annotated[str, Form()] = "rename",
) -> Envelope[ImportResult]:
    if on_conflict not in ("rename", "overwrite", "skip"):
        raise BadRequestError("on_conflict 只支持 rename / overwrite / skip。")
    raw = await file.read()
    if not raw:
        raise BadRequestError("上传的文件为空，请重新选择卡片文件。")
    result = await ImportExportSvc(db).import_card(
        raw=raw, filename=file.filename or "", on_conflict=on_conflict
    )
    return Envelope(data=ImportResult.model_validate(result))


@router.post(
    "/import/worldbook",
    response_model=Envelope[ImportResult],
    status_code=201,
    summary="导入世界书（SillyTavern World Info JSON）",
)
async def import_worldbook(
    db: DbSession,
    file: Annotated[UploadFile, File()],
    on_conflict: Annotated[str, Form()] = "rename",
) -> Envelope[ImportResult]:
    if on_conflict not in ("rename", "overwrite", "skip"):
        raise BadRequestError("on_conflict 只支持 rename / overwrite / skip。")
    raw = await file.read()
    if not raw:
        raise BadRequestError("上传的文件为空，请重新选择世界书文件。")
    result = await ImportExportSvc(db).import_worldbook(
        raw=raw, filename=file.filename or "", on_conflict=on_conflict
    )
    return Envelope(data=ImportResult.model_validate(result))


@router.post(
    "/export/bundle",
    summary="导出可移植包（卡片+世界书+预设+素材 zip）",
    responses={200: {"description": "zip 文件", "content": {"application/zip": {}}}},
)
async def export_bundle(db: DbSession, payload: ExportBundleRequest) -> Response:
    blob = await ImportExportSvc(db).export_bundle(payload.model_dump(mode="json"))
    return Response(
        content=blob,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="marionette-bundle.zip"'},
    )


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
async def export_card(db: DbSession, cardId: str, format: str = "json") -> Response:
    blob, media_type, filename = await ImportExportSvc(db).export_card(cardId, format)
    return Response(
        content=blob,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
