"""统一检索基元（SearchProvider 的 PostgreSQL 实现）。

ADR-005 铁律：中文检索走 `pg_trgm` 三字组 GIN + `ILIKE`，
**禁止** `to_tsvector` / 中文分词器 / Meilisearch。
本模块是 cards / worldbooks / presets / assets 四个 list 端点共用的唯一文本匹配基元
（schemas.md §9：禁止各写一套）。
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Select, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

_LIKE_ESCAPE = "\\"


@dataclass(frozen=True)
class ListQuery:
    """列表端点统一入参（对齐 openapi components.schemas.SearchQuery）。"""

    q: str | None = None
    tags: Sequence[str] = field(default_factory=tuple)
    sort: str = "updated_at"
    order: str = "desc"
    page: int = 1
    limit: int = 20


def keyword_terms(q: str | None) -> list[str]:
    """按空白拆分，多词 AND（schemas.md §9）。"""
    if not q:
        return []
    return [term for term in re.split(r"\s+", q.strip()) if term]


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def apply_keyword(
    stmt: Select, q: str | None, fields: Sequence[ColumnElement[Any]]
) -> Select:
    """每个词都必须命中至少一个字段（AND of OR）。走 ILIKE，可命中 trgm GIN 索引。"""
    for term in keyword_terms(q):
        pattern = f"%{_escape_like(term)}%"
        stmt = stmt.where(or_(*[f.ilike(pattern, escape=_LIKE_ESCAPE) for f in fields]))
    return stmt


def apply_tags(stmt: Select, column: ColumnElement[Any], tags: Sequence[str]) -> Select:
    """标签多值 AND → `tags @> ARRAY[...]`，命中 GIN(tags) 索引。"""
    wanted = [t for t in tags if t]
    if wanted:
        stmt = stmt.where(column.contains(wanted))
    return stmt


def apply_sort(
    stmt: Select,
    model: type,
    sort: str,
    order: str,
    sort_map: dict[str, ColumnElement[Any]],
) -> Select:
    """排序 + 以主键做兜底，保证分页间顺序稳定（AC-13）。"""
    column = sort_map.get(sort) or sort_map["updated_at"]
    direction = desc if order == "desc" else asc
    return stmt.order_by(direction(column), model.id.asc())


async def fetch_page(
    db: AsyncSession, stmt: Select, *, page: int, limit: int
) -> tuple[list[Any], int]:
    """分页取数 + 总数。返回 (rows, total)。"""
    page = max(1, page)
    limit = max(1, min(100, limit))
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int((await db.execute(count_stmt)).scalar_one() or 0)
    rows = (
        (await db.execute(stmt.offset((page - 1) * limit).limit(limit))).scalars().all()
    )
    return list(rows), total


def build_page(page: int, limit: int, total: int) -> dict[str, Any]:
    page = max(1, page)
    limit = max(1, min(100, limit))
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "hasMore": page * limit < total,
    }


def sort_columns(*, name_column: ColumnElement[Any], model: type) -> dict[str, ColumnElement[Any]]:
    """三个内容资源通用的排序字段映射（支持 created_at / updated_at / name）。"""
    return {
        "created_at": model.created_at,
        "updated_at": model.updated_at,
        "name": name_column,
        "last_message_at": model.updated_at,  # 非会话资源无此列，回落 updated_at
    }


__all__ = [
    "ListQuery",
    "apply_keyword",
    "apply_sort",
    "apply_tags",
    "build_page",
    "fetch_page",
    "keyword_terms",
    "sort_columns",
]
