"""内容检索服务：cards / worldbooks / presets 三类资源共用一套检索/分页。

设计目标（schemas.md §9）：
  - `q` / `tags` / `sort` / `order` / `page` / `limit` 六参数语义完全一致；
  - `q` 多词 AND，命中字段由各资源通过 `q_fields` 声明；
  - 排序末位追加主键兜底，保证分页间顺序稳定（AC-13）。

本模块只产出 SQL 与分页元数据，不感知资源的具体序列化方式。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.base import Base
from app.services.search import (
    ListQuery,
    apply_keyword,
    apply_sort,
    apply_tags,
    build_page,
    fetch_page,
    sort_columns,
)


@dataclass(frozen=True)
class ResourceSpec:
    """一类内容资源的检索描述。"""

    model: type[Base]
    name_column: ColumnElement[Any]
    # `q` 命中的字段（SQL 表达式），延迟构建以免在 import 期触发表元数据
    q_fields: Callable[[], Sequence[ColumnElement[Any]]]
    # `tags` 筛选列；无 GIN 标签列的资源（preset）传 None
    tags_column: ColumnElement[Any] | None = None
    supports_last_message_at: bool = False


class ContentSearchSvc:
    """统一 list 端点实现（供 ContentSvc 与 AssetSvc 复用）。"""

    def __init__(self, spec: ResourceSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> ResourceSpec:
        return self._spec

    async def list(
        self, db: AsyncSession, query: ListQuery, *, extra_wheres: Sequence[Any] = ()
    ) -> tuple[list[Any], dict[str, Any]]:
        """返回 (rows, page_meta)。page_meta 可直接喂给 Paged 响应。"""
        from sqlalchemy import select

        model = self._spec.model
        stmt = select(model)
        for clause in extra_wheres:
            stmt = stmt.where(clause)
        stmt = apply_keyword(stmt, query.q, self._spec.q_fields())
        if self._spec.tags_column is not None:
            stmt = apply_tags(stmt, self._spec.tags_column, query.tags)
        stmt = apply_sort(
            stmt,
            model,
            query.sort,
            query.order,
            sort_columns(name_column=self._spec.name_column, model=model),
        )
        rows, total = await fetch_page(db, stmt, page=query.page, limit=query.limit)
        return rows, build_page(query.page, query.limit, total)


__all__ = ["ContentSearchSvc", "ResourceSpec"]
