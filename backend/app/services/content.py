"""内容仓库服务（角色卡 / 世界书 / 预设 的 CRUD 与检索）。

分层铁律：本服务只依赖 ORM 模型与 Schema，不 import FastAPI 的 req/res。
Router 只做「解析入参 -> 调本服务 -> 组装信封」。

统一约定：
  - 写入时从 `data.name` / `data.tags` 反规范化到 `name` / `tags` 列（供 GIN 索引）；
  - `spec_version` 高于本机支持版本时拒绝写入（schemas.md §1 铁律 2）；
  - PATCH 采用**深合并**语义：未提交的字段保持原值，且未知字段不销毁（铁律 3）。

资源类型注册表（模型/Schema/q 命中字段）见 content_kinds.py。
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.registry import get_asset_store
from app.core.errors import BadRequestError, NotFoundError
from app.core.ids import parse_uuid
from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.base import Base
from app.services.content_kinds import (
    KINDS,
    ContentKind,
    assert_supported_version,
    build_search_spec,
)
from app.services.content_search import ContentSearchSvc
from app.services.search import ListQuery

logger = get_logger(__name__)


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """递归合并：dict 逐键合并，非 dict 直接覆盖。未知字段一并保留。"""
    out = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class ContentSvc:
    """内容对象读写编排（cards / worldbooks / presets 同构）。"""

    def __init__(self, db: AsyncSession, kind: ContentKind) -> None:
        self._db = db
        self.kind = kind
        self._search = ContentSearchSvc(build_search_spec(kind))

    # ---------------- 序列化 ----------------
    def serialize(self, row: Base) -> dict[str, Any]:
        return {
            "spec": row.spec,
            "spec_version": row.spec_version,
            "id": row.id,
            "data": row.data,
            "extensions": row.extensions,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    # ---------------- 读 ----------------
    async def list(
        self, query: ListQuery, *, extra_wheres: tuple[Any, ...] = ()
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        rows, meta = await self._search.list(self._db, query, extra_wheres=extra_wheres)
        return [self.serialize(r) for r in rows], meta

    async def get(self, obj_id: str | uuid.UUID) -> Base:
        uid = parse_uuid(obj_id, field=f"{self.kind.key}Id")
        row = (
            await self._db.execute(select(self.kind.model).where(self.kind.model.id == uid))
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError(f"{self.kind.spec_name}（id={uid}）不存在或已被删除。")
        return row

    # ---------------- 写 ----------------
    def _validated(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        try:
            validated: BaseModel = self.kind.data_cls.model_validate(raw_data)
        except ValidationError as exc:
            first = exc.errors()[0] if exc.errors() else {}
            where = ".".join(str(p) for p in first.get("loc", ())) or "data"
            raise BadRequestError(
                f"{self.kind.spec_name} 的字段 {where} 不合法（{first.get('msg', '格式不正确')}）。"
            ) from exc
        return validated.model_dump(mode="json")

    def validate_data(self, payload: dict[str, Any], *, require_envelope: bool) -> dict[str, Any]:
        """校验 `data` 节点并归一化。envelope 字段（spec/spec_version）单独处理。"""
        raw_data = payload.get("data")
        if raw_data is None:
            if require_envelope:
                raise BadRequestError("请求体缺少 data 字段，无法创建内容对象。")
            raw_data = {}
        if not isinstance(raw_data, dict):
            raise BadRequestError("data 字段必须是 JSON 对象。")
        return self._validated(raw_data)

    async def create(self, payload: dict[str, Any]) -> Base:
        assert_supported_version(self.kind, payload.get("spec_version"))
        data = self.validate_data(payload, require_envelope=True)
        row = self.kind.model(
            owner_id="local",
            name=str(data.get("name") or ""),
            spec=self.kind.spec_name,
            spec_version=str(payload.get("spec_version") or "1.0"),
            data=data,
            extensions=payload.get("extensions") or {},
            **self._tags_kwargs(data),
        )
        self._db.add(row)
        await self._db.flush()
        await self._db.refresh(row)
        # 注意：日志 extra 的键**不得**与 LogRecord 保留属性同名（name/module/msg/args...），
        # 否则 Logger.makeRecord 会抛 KeyError 把请求打成 500。故此处用 content_name。
        # 全仓静态门禁见 tests/test_logging_extra_keys.py。
        logger.info(
            "content created",
            extra={"kind": self.kind.key, "id": str(row.id), "content_name": row.name},
        )
        return row

    async def update(self, obj_id: str | uuid.UUID, patch: dict[str, Any]) -> Base:
        row = await self.get(obj_id)
        assert_supported_version(self.kind, patch.get("spec_version"))
        merged_data = dict(row.data or {})
        if isinstance(patch.get("data"), dict):
            merged_data = _deep_merge(merged_data, patch["data"])
        data = self._validated(merged_data)
        merged_ext = dict(row.extensions or {})
        if isinstance(patch.get("extensions"), dict):
            merged_ext = _deep_merge(merged_ext, patch["extensions"])

        row.data = data
        row.extensions = merged_ext
        row.name = str(data.get("name") or "")
        for column, value in self._tags_kwargs(data).items():
            setattr(row, column, value)
        await self._db.flush()
        await self._db.refresh(row)
        logger.info("content updated", extra={"kind": self.kind.key, "id": str(row.id)})
        return row

    async def delete(self, obj_id: str | uuid.UUID) -> str:
        row = await self.get(obj_id)
        if self.kind.key == "card":
            await self._purge_card_assets(row.id)
        deleted_id = str(row.id)
        await self._db.delete(row)
        await self._db.flush()
        logger.info("content deleted", extra={"kind": self.kind.key, "id": deleted_id})
        return deleted_id

    # ---------------- 内部 ----------------
    def _tags_kwargs(self, data: dict[str, Any]) -> dict[str, Any]:
        if not hasattr(self.kind.model, "tags"):
            return {}
        return {"tags": self.kind.tags_from(data)}

    async def _purge_card_assets(self, card_id: uuid.UUID) -> None:
        """删除卡片时清理其专属资产（行 + 文件），避免留下孤儿文件。"""
        rows = (
            await self._db.execute(select(Asset).where(Asset.card_id == card_id))
        ).scalars().all()
        store = get_asset_store()
        for asset in rows:
            try:
                await store.delete(asset.storage_key)
            except Exception as exc:  # noqa: BLE001 —— 文件缺失不应阻断删除
                logger.warning(
                    "asset file purge skipped",
                    extra={"key": asset.storage_key, "err": type(exc).__name__},
                )
            await self._db.delete(asset)
        if rows:
            logger.info("card assets purged", extra={"card_id": str(card_id), "count": len(rows)})


def content_service(db: AsyncSession, kind: str) -> ContentSvc:
    if kind not in KINDS:
        raise KeyError(f"未知的内容类型：{kind}")
    return ContentSvc(db, KINDS[kind])


__all__ = ["ContentSvc", "content_service"]
