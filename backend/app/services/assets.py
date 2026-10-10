"""资产查询服务（SPEC §6 `assets` / schemas.md §10）。

只做查询与元数据序列化；上传/出图归档在第二波（运行时）实现。
列表复用统一检索基元：`q` 命中 `filename` / `tags` / `meta.prompt`，无数据返回空分页（不 500）。
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.registry import get_asset_store
from app.core.errors import BadRequestError, NotFoundError
from app.core.ids import parse_uuid
from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.card import Card
from app.schemas.asset import AssetKind
from app.services.content_search import ContentSearchSvc, ResourceSpec
from app.services.search import ListQuery

logger = get_logger(__name__)

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_KINDS: tuple[str, ...] = ("avatar", "gallery", "background", "generated")


def _asset_spec() -> ResourceSpec:
    return ResourceSpec(
        model=Asset,
        name_column=Asset.filename,
        q_fields=lambda: (
            Asset.filename,
            func.array_to_string(Asset.tags, " "),
            Asset.meta["prompt"].astext,
        ),
        tags_column=Asset.tags,
    )


class AssetSvc:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._search = ContentSearchSvc(_asset_spec())

    def serialize(self, row: Asset) -> dict[str, Any]:
        return {
            "id": row.id,
            "kind": row.kind,
            "filename": row.filename,
            "content_type": row.content_type,
            "size_bytes": row.size_bytes,
            "card_id": row.card_id,
            "session_id": row.session_id,
            "message_id": row.message_id,
            "tags": list(row.tags or []),
            "meta": row.meta or {},
            "created_at": row.created_at,
        }

    async def list(
        self,
        query: ListQuery,
        *,
        card_id: str | uuid.UUID | None = None,
        session_id: str | uuid.UUID | None = None,
        kind: AssetKind | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        wheres: list[Any] = []
        if card_id:
            wheres.append(Asset.card_id == parse_uuid(card_id, field="cardId"))
        if session_id:
            wheres.append(Asset.session_id == parse_uuid(session_id, field="sessionId"))
        if kind:
            wheres.append(Asset.kind == kind)
        rows, meta = await self._search.list(self._db, query, extra_wheres=wheres)
        return [self.serialize(r) for r in rows], meta

    async def get(self, asset_id: str | uuid.UUID) -> Asset:
        uid = parse_uuid(asset_id, field="assetId")
        row = (await self._db.execute(select(Asset).where(Asset.id == uid))).scalar_one_or_none()
        if row is None:
            raise NotFoundError(f"资产（id={uid}）不存在或已被删除。")
        return row

    async def read_content(self, asset_id: str | uuid.UUID) -> tuple[bytes, str, str]:
        row = await self.get(asset_id)
        data = await get_asset_store().read(row.storage_key)
        return data, row.content_type or "application/octet-stream", row.filename or "asset.bin"

    async def delete(self, asset_id: str | uuid.UUID) -> str:
        row = await self.get(asset_id)
        await get_asset_store().delete(row.storage_key)
        deleted_id = str(row.id)
        await self._db.delete(row)
        await self._db.flush()
        return deleted_id

    async def create(
        self,
        *,
        data: bytes,
        filename: str,
        content_type: str,
        kind: str,
        card_id: str | uuid.UUID | None = None,
        session_id: str | uuid.UUID | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        if kind not in ALLOWED_KINDS:
            raise BadRequestError(f"不支持的资产类型「{kind}」，可选：{', '.join(ALLOWED_KINDS)}。")
        if not data:
            raise BadRequestError("上传的文件为空，请重新选择文件。")
        if len(data) > MAX_UPLOAD_BYTES:
            raise BadRequestError(
                f"文件超过 {MAX_UPLOAD_BYTES // (1024 * 1024)}MB 上限，请压缩后再上传。"
            )
        card_uuid = parse_uuid(card_id, field="card_id") if card_id else None
        if card_uuid is not None:
            exists = (
                await self._db.execute(select(Card.id).where(Card.id == card_uuid))
            ).scalar_one_or_none()
            if exists is None:
                raise NotFoundError(f"归属角色（id={card_uuid}）不存在，无法挂载资产。")
        session_uuid = parse_uuid(session_id, field="session_id") if session_id else None

        stored = await get_asset_store().save(
            data, filename=filename, content_type=content_type, kind=kind
        )
        row = Asset(
            owner_id="local",
            kind=kind,
            filename=filename,
            content_type=content_type,
            size_bytes=stored.size_bytes,
            storage_key=stored.storage_key,
            card_id=card_uuid,
            session_id=session_uuid,
            tags=[t.strip() for t in (tags or []) if t.strip()],
            meta={},
        )
        self._db.add(row)
        await self._db.flush()
        await self._db.refresh(row)
        logger.info("asset uploaded", extra={"kind": kind, "id": str(row.id), "size": stored.size_bytes})
        return self.serialize(row)


__all__ = ["AssetSvc"]
