"""检索基元与分页的机械证据（F16 / AC-13 的 SQL 面）。

AC-13 要求"返回过滤结果且排序在分页间保持一致"。分页稳定的根因是：排序键必须唯一。
这里直接编译出 SQL 断言 ORDER BY 末位是主键（不依赖数据库）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models.card import Card
from app.services.search import (
    ListQuery,
    apply_keyword,
    apply_sort,
    apply_tags,
    build_page,
    keyword_terms,
    sort_columns,
)


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def test_keyword_terms_splits_on_whitespace() -> None:
    assert keyword_terms("咖啡 雨天") == ["咖啡", "雨天"]
    assert keyword_terms("  咖啡   雨天  ") == ["咖啡", "雨天"]
    assert keyword_terms(None) == []
    assert keyword_terms("") == []


def test_multiple_terms_are_anded() -> None:
    stmt = apply_keyword(select(Card), "咖啡 雨天", (Card.name, Card.data["description"].astext))
    sql = _sql(stmt)
    # 2 个词 × 2 个候选字段 = 4 个 ILIKE，词之间是 AND、字段之间是 OR
    assert sql.count("ILIKE") == 4
    assert " AND " in sql and " OR " in sql


def test_like_special_chars_are_escaped() -> None:
    stmt = apply_keyword(select(Card), "100%_x", (Card.name,))
    sql = _sql(stmt)
    assert "ESCAPE" in sql
    assert "\\%" in sql and "\\_" in sql


def test_tags_filter_uses_containment() -> None:
    stmt = apply_tags(select(Card), Card.tags, ["日常", "咖啡"])
    sql = _sql(stmt)
    assert "@>" in sql
    assert "日常" in sql and "咖啡" in sql


def test_sort_appends_primary_key_tiebreaker() -> None:
    stmt = apply_sort(select(Card), Card, "updated_at", "desc", sort_columns(name_column=Card.name, model=Card))
    sql = _sql(stmt)
    assert "ORDER BY cards.updated_at DESC, cards.id ASC" in sql


def test_sort_order_direction_flips() -> None:
    stmt = apply_sort(select(Card), Card, "name", "asc", sort_columns(name_column=Card.name, model=Card))
    sql = _sql(stmt)
    assert "ORDER BY cards.name ASC, cards.id ASC" in sql


def test_unknown_sort_field_falls_back_to_updated_at() -> None:
    stmt = apply_sort(
        select(Card), Card, "not_a_field", "desc", sort_columns(name_column=Card.name, model=Card)
    )
    assert "ORDER BY cards.updated_at DESC, cards.id ASC" in _sql(stmt)


def test_build_page_reports_has_more() -> None:
    assert build_page(1, 20, 100) == {"total": 100, "page": 1, "limit": 20, "hasMore": True}
    assert build_page(5, 20, 100) == {"total": 100, "page": 5, "limit": 20, "hasMore": False}
    assert build_page(1, 20, 0)["hasMore"] is False


def test_list_query_defaults_match_contract() -> None:
    query = ListQuery()
    assert (query.sort, query.order, query.page, query.limit) == ("updated_at", "desc", 1, 20)
