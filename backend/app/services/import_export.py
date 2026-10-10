"""导入导出编排服务（AC-05 / AC-06）。

  - `POST /api/v1/import/card`      ST V1/V2/V3 JSON/PNG/WEBP -> 平台卡（含头像落资产）
  - `POST /api/v1/import/worldbook` ST World Info JSON -> 平台世界书
  - `GET  /api/v1/export/card/{id}` 平台卡 -> ST V2（json / png，可回导）
  - `POST /api/v1/export/bundle`    卡片+世界书+预设+素材 打包 zip

业务层不 import 厂商 SDK；图片字节处理走 st_image（Pillow）。
"""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.registry import get_asset_store
from app.core.errors import BadRequestError, NotFoundError
from app.core.ids import parse_uuid
from app.core.logging import get_logger
from app.core.text import file_suffix, safe_filename, stem
from app.models.asset import Asset
from app.models.card import Card
from app.models.preset import Preset
from app.models.worldbook import WorldBook
from app.services.content import content_service
from app.services.st_compat import STCompatAdapter, to_st_v2
from app.services.st_image import build_png_card
from app.services.wb_import import worldbook_data_from_payload

logger = get_logger(__name__)

_adapter = STCompatAdapter()


def card_payload(row: Card) -> dict[str, Any]:
    """ORM 卡片行 -> 平台 rpg_card 信封。"""
    return {
        "spec": row.spec,
        "spec_version": row.spec_version,
        "id": row.id,
        "data": row.data,
        "extensions": row.extensions,
    }


class ImportExportSvc:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._cards = content_service(db, "card")
        self._worldbooks = content_service(db, "worldbook")
        self._presets = content_service(db, "preset")

    # ---------------- 导入 ----------------
    async def import_card(
        self, *, raw: bytes, filename: str, on_conflict: str = "rename"
    ) -> dict[str, Any]:
        parsed = _adapter.parse_bytes(raw, filename=filename)
        existing = await self._find_card_by_name(parsed.payload["data"]["name"])
        warnings = list(parsed.warnings)

        if existing is not None and on_conflict == "skip":
            warnings.append(f"已存在同名角色「{existing.name}」，按 on_conflict=skip 跳过导入。")
            return self._result(parsed, existing.id, warnings)

        if existing is not None and on_conflict == "overwrite":
            row = await self._cards.update(existing.id, parsed.payload)
            warnings.append(f"已覆盖同名角色「{existing.name}」。")
        else:
            if existing is not None:  # rename
                parsed.payload["data"]["name"] = self._renamed(parsed.payload["data"]["name"])
                warnings.append("检测到同名角色，已自动重命名以免覆盖。")
            row = await self._cards.create(parsed.payload)

        if parsed.image is not None:
            asset_id = await self._attach_avatar(row, parsed.image)
            warnings.append("卡片内嵌图片已存为头像资产。")
            logger.info(
                "card avatar stored", extra={"card_id": str(row.id), "asset_id": str(asset_id)}
            )
        return self._result(parsed, row.id, warnings)

    async def import_worldbook(
        self, *, raw: bytes, filename: str, on_conflict: str = "rename"
    ) -> dict[str, Any]:
        try:
            payload = json.loads(raw.decode("utf-8-sig"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise BadRequestError("世界书必须是 UTF-8 编码的 JSON 文件。") from exc
        if not isinstance(payload, dict):
            raise BadRequestError("世界书 JSON 顶层必须是对象。")
        data, source_format = worldbook_data_from_payload(payload)

        name = str(data.get("name") or stem(filename) or "导入的世界书")
        data["name"] = name
        warnings: list[str] = []
        existing = (
            await self._db.execute(select(WorldBook).where(WorldBook.name == name))
        ).scalar_one_or_none()
        envelope = {"spec": "rpg_worldbook", "spec_version": "1.0", "data": data, "extensions": {}}

        if existing is not None and on_conflict == "skip":
            warnings.append(f"已存在同名世界书「{name}」，按 on_conflict=skip 跳过。")
            return self._ok(source_format, existing.id, warnings, [])
        if existing is not None and on_conflict == "overwrite":
            row = await self._worldbooks.update(existing.id, envelope)
            warnings.append(f"已覆盖同名世界书「{name}」。")
        else:
            if existing is not None:
                data["name"] = self._renamed(name)
                envelope["data"] = data
                warnings.append("检测到同名世界书，已自动重命名。")
            row = await self._worldbooks.create(envelope)

        preserved = sorted((data.get("extensions") or {}).keys())
        if not data.get("entries"):
            warnings.append("该世界书没有任何条目，导入后需自行补充。")
        return self._ok(source_format, row.id, warnings, preserved)

    # ---------------- 导出 ----------------
    async def export_card(self, card_id: str, fmt: str = "json") -> tuple[bytes, str, str]:
        row = await self._cards.get(card_id)
        st = to_st_v2(card_payload(row))
        name = safe_filename(row.name or "card", fallback="card")
        if fmt == "png":
            avatar = await self._avatar_bytes(row)
            return build_png_card(st, base_image=avatar, seed=name), "image/png", f"{name}.png"
        if fmt != "json":
            raise BadRequestError(f"不支持的导出格式「{fmt}」，可选 json 或 png。")
        body = json.dumps(st, ensure_ascii=False, indent=2).encode("utf-8")
        return body, "application/json", f"{name}.json"

    async def export_bundle(self, req: dict[str, Any]) -> bytes:
        cards = await self._load_many(Card, req.get("card_ids"))
        worldbooks = await self._load_many(WorldBook, req.get("worldbook_ids"))
        presets = await self._load_many(Preset, req.get("preset_ids"))
        include_assets = bool(req.get("include_assets", True))

        manifest: dict[str, Any] = {
            "format": "marionette.bundle",
            "format_version": "1.0",
            "cards": [self._manifest_entry(r) for r in cards],
            "worldbooks": [self._manifest_entry(r) for r in worldbooks],
            "presets": [self._manifest_entry(r) for r in presets],
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            if include_assets:
                manifest["assets"] = await self._write_assets(zf, cards)
            for card in cards:
                blob = json.dumps(to_st_v2(card_payload(card)), ensure_ascii=False, indent=2)
                zf.writestr(f"cards/{card.id}.json", blob)
            for book in worldbooks:
                self._write_json(zf, f"worldbooks/{book.id}.json", self._envelope(book))
            for preset in presets:
                self._write_json(zf, f"presets/{preset.id}.json", self._envelope(preset))
            self._write_json(zf, "manifest.json", manifest)
        return buffer.getvalue()

    # ---------------- 内部 ----------------
    async def _write_assets(self, zf: zipfile.ZipFile, cards: list[Any]) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        store = get_asset_store()
        for card in cards:
            for asset in await self._card_assets(card.id):
                try:
                    blob = await store.read(asset.storage_key)
                except Exception:  # noqa: BLE001 —— 单个素材缺失不阻断整包导出
                    logger.warning("bundle asset skipped", extra={"asset_id": str(asset.id)})
                    continue
                arc = f"assets/{asset.id}{file_suffix(asset.storage_key)}"
                zf.writestr(arc, blob)
                entries.append({"id": str(asset.id), "card_id": str(card.id), "path": arc})
        return entries

    @staticmethod
    def _write_json(zf: zipfile.ZipFile, path: str, payload: Any) -> None:
        zf.writestr(path, json.dumps(payload, ensure_ascii=False, indent=2))

    async def _find_card_by_name(self, name: str) -> Card | None:
        return (
            await self._db.execute(select(Card).where(Card.name == name).limit(1))
        ).scalar_one_or_none()

    async def _attach_avatar(self, card: Card, image: Any) -> uuid.UUID:
        stored = await get_asset_store().save(
            image.data, filename=image.filename, content_type=image.content_type, kind="avatar"
        )
        asset = Asset(
            owner_id="local",
            kind="avatar",
            filename=image.filename,
            content_type=image.content_type,
            size_bytes=stored.size_bytes,
            storage_key=stored.storage_key,
            card_id=card.id,
            tags=[],
            meta={"source": "card_import"},
        )
        self._db.add(asset)
        await self._db.flush()
        data = dict(card.data or {})
        extensions = dict(data.get("extensions") or {})
        rpg = dict(extensions.get("rpg") or {})
        rpg["avatar_asset_id"] = str(asset.id)
        extensions["rpg"] = rpg
        data["extensions"] = extensions
        card.data = data
        await self._db.flush()
        return asset.id

    async def _avatar_bytes(self, card: Card) -> bytes | None:
        asset_id = (((card.data or {}).get("extensions") or {}).get("rpg") or {}).get(
            "avatar_asset_id"
        )
        if not asset_id:
            return None
        asset = (
            await self._db.execute(select(Asset).where(Asset.id == parse_uuid(asset_id, field="assetId")))
        ).scalar_one_or_none()
        if asset is None:
            return None
        try:
            return await get_asset_store().read(asset.storage_key)
        except Exception:  # noqa: BLE001 —— 头像文件缺失时回落占位图
            return None

    async def _card_assets(self, card_id: uuid.UUID) -> list[Asset]:
        rows = (
            await self._db.execute(select(Asset).where(Asset.card_id == card_id))
        ).scalars().all()
        return list(rows)

    async def _load_many(self, model: type, ids: Any) -> list[Any]:
        parsed = [parse_uuid(i, field="id") for i in (ids or [])]
        if not parsed:
            return []
        rows = (await self._db.execute(select(model).where(model.id.in_(parsed)))).scalars().all()
        found = {r.id for r in rows}
        missing = [str(i) for i in parsed if i not in found]
        if missing:
            raise NotFoundError(f"导出对象不存在：{', '.join(missing)}。")
        return list(rows)

    @staticmethod
    def _manifest_entry(row: Any) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "name": getattr(row, "name", ""),
            "spec": getattr(row, "spec", ""),
            "spec_version": getattr(row, "spec_version", ""),
        }

    @staticmethod
    def _envelope(row: Any) -> dict[str, Any]:
        return {
            "spec": row.spec,
            "spec_version": row.spec_version,
            "id": str(row.id),
            "data": row.data,
            "extensions": row.extensions,
        }

    @staticmethod
    def _result(parsed: Any, object_id: uuid.UUID, warnings: list[str]) -> dict[str, Any]:
        return {
            "source_format": parsed.source_format,
            "object_id": object_id,
            "warnings": warnings,
            "preserved_unknown_keys": parsed.unknown_keys,
        }

    @staticmethod
    def _ok(
        source_format: str, object_id: uuid.UUID, warnings: list[str], preserved: list[str]
    ) -> dict[str, Any]:
        return {
            "source_format": source_format,
            "object_id": object_id,
            "warnings": warnings,
            "preserved_unknown_keys": preserved,
        }

    @staticmethod
    def _renamed(name: str) -> str:
        return f"{name} (导入副本)" if "(导入副本)" not in name else f"{name} 2"


__all__ = ["ImportExportSvc", "card_payload"]
