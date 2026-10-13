"""世界观服务（剧情引擎）：worlds 表的 CRUD + 中文子串检索。

与 ContentSvc 的差异：
  - 不共享多态基表（worlds 是独立表，字段是摊平的 setting/factions/cast/...）
  - 检索策略与卡/世界书一致：pg_trgm GIN 索引支撑中文子串（ADR-005）

分层铁律：只依赖 ORM 与 schema，不认识 HTTP。
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.ids import parse_uuid
from app.core.logging import get_logger
from app.models.world import World as WorldRow

logger = get_logger(__name__)

#: 允许 PATCH 的字段白名单（其余键忽略，防脏写）
_PATCHABLE = frozenset(
    {
        "title",
        "setting",
        "factions",
        "cast",
        "relations",
        "outline",
        "opening",
        "extensions",
        "tags",
    }
)


class WorldSvc:
    """世界观 CRUD。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------ #
    # 序列化
    # ------------------------------------------------------------------ #
    @staticmethod
    def serialize(row: WorldRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "spec": row.spec,
            "spec_version": row.spec_version,
            "title": row.title,
            "setting": dict(row.setting or {}),
            "factions": list(row.factions or []),
            "cast": list(row.cast or []),
            "relations": list(row.relations or []),
            "outline": dict(row.outline or {}),
            "opening": row.opening or "",
            "extensions": dict(row.extensions or {}),
            "tags": list(row.tags or []),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    # ------------------------------------------------------------------ #
    # 读
    # ------------------------------------------------------------------ #
    async def get_row(self, world_id: str | uuid.UUID) -> WorldRow:
        uid = parse_uuid(world_id, field="worldId")
        row = (
            await self._db.execute(select(WorldRow).where(WorldRow.id == uid))
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError(f"世界观（id={uid}）不存在或已被删除。")
        return row

    async def get(self, world_id: str) -> dict[str, Any]:
        return self.serialize(await self.get_row(world_id))

    async def list(
        self,
        *,
        q: str | None = None,
        tags: Iterable[str] | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        from app.services.search import build_page

        stmt = select(WorldRow)
        if q:
            # title ILIKE 命中 pg_trgm GIN 索引（中文子串可用）
            stmt = stmt.where(WorldRow.title.ilike(f"%{q}%"))
        tag_list = [str(t) for t in (tags or []) if str(t).strip()]
        if tag_list:
            stmt = stmt.where(WorldRow.tags.contains(tag_list))

        total = int(
            (await self._db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
            or 0
        )
        page, limit = max(1, page), max(1, min(100, limit))
        rows = (
            await self._db.execute(
                stmt.order_by(WorldRow.updated_at.desc(), WorldRow.id.asc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).scalars().all()
        return [self.serialize(r) for r in rows], build_page(page, limit, total)

    # ------------------------------------------------------------------ #
    # 写
    # ------------------------------------------------------------------ #
    async def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = WorldRow(
            owner_id="local",
            title=str(payload.get("title") or "").strip() or "未命名世界",
            spec=str(payload.get("spec") or "rpg_world"),
            spec_version=str(payload.get("spec_version") or "1.0"),
            setting=dict(payload.get("setting") or {}),
            factions=list(payload.get("factions") or []),
            cast=list(payload.get("cast") or []),
            relations=list(payload.get("relations") or []),
            outline=dict(payload.get("outline") or {}),
            opening=str(payload.get("opening") or ""),
            extensions=dict(payload.get("extensions") or {}),
            tags=[str(t) for t in (payload.get("tags") or []) if str(t).strip()],
        )
        self._db.add(row)
        await self._db.flush()
        await self._db.refresh(row)
        logger.info("world created", extra={"world": str(row.id)})
        return self.serialize(row)

    async def update(self, world_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        """部分更新：只改白名单内传入的键（未传即保留）。"""
        row = await self.get_row(world_id)
        for key, value in (patch or {}).items():
            if key not in _PATCHABLE or value is None:
                continue
            if key == "tags":
                row.tags = [str(t) for t in value if str(t).strip()]
            elif key in ("setting", "outline", "extensions"):
                row.__setattr__(key, dict(value))
            elif key in ("factions", "cast", "relations"):
                row.__setattr__(key, list(value))
            else:
                row.__setattr__(key, str(value))
        await self._db.flush()
        await self._db.refresh(row)
        logger.info("world updated", extra={"world": str(row.id)})
        return self.serialize(row)

    async def delete(self, world_id: str) -> str:
        row = await self.get_row(world_id)
        deleted_id = str(row.id)
        await self._db.delete(row)  # sessions.world_id 走 ON DELETE SET NULL
        await self._db.flush()
        logger.info("world deleted", extra={"world": deleted_id})
        return deleted_id


__all__ = ["WorldSvc"]
