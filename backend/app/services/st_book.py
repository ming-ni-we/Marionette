"""世界书 / 条目的 ST 双向映射（schemas.md §4.4）。

字段归一规则：
  - `key`(string) 与 `keys`(string[]) -> 统一为 `keys`；
  - `disable` -> `enabled`（取反）；
  - `order` -> `insertion_order`；
  - 条目级/书级未知键 -> 各自的 `extensions`（不销毁）；
  - 外部原始 id（ST 的 int id）-> `extensions.st_original_id`（平台自生成 UUID，铁律 7）。
"""

from __future__ import annotations

import uuid
from typing import Any

_BOOK_KNOWN = {
    "name",
    "description",
    "scan_depth",
    "token_budget",
    "recursive_scanning",
    "max_recursion_depth",
    "extensions",
    "entries",
}

_BOOK_ENTRY_KNOWN = {
    "keys",
    "key",
    "secondary_keys",
    "content",
    "comment",
    "enabled",
    "disable",
    "constant",
    "selective",
    "case_sensitive",
    "match_whole_words",
    "use_regex",
    "regex_flags",
    "insertion_order",
    "order",
    "priority",
    "position",
    "depth",
    "role",
    "vector_recall",
    "vector_threshold",
    "extensions",
    "id",
    "uid",
    "name",
}

# 平台 WorldBookEntry 的透传字段（导出时若存在则原样写出）
_ENTRY_PASSTHROUGH = (
    "use_regex",
    "regex_flags",
    "depth",
    "role",
    "vector_recall",
    "vector_threshold",
)


def as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if str(v).strip()]
    return [str(value)]


def entry_from_st(raw: dict[str, Any]) -> dict[str, Any]:
    """ST 条目 -> 平台 WorldBookEntry。"""
    out: dict[str, Any] = {}
    unknown: dict[str, Any] = {}
    keys: list[str] | None = None
    original_id: Any = None
    for key, value in raw.items():
        if key in ("key", "keys"):
            keys = as_str_list(value)
        elif key == "disable":
            out["enabled"] = not bool(value)
        elif key in ("order", "insertion_order"):
            out["insertion_order"] = int(value) if isinstance(value, (int, float)) else value
        elif key in ("id", "uid"):
            original_id = value
        elif key == "name":  # ST 部分导出用 name 作条目标题，等价于 comment
            out.setdefault("comment", str(value))
        elif key in _BOOK_ENTRY_KNOWN:
            out[key] = value
        else:
            unknown[key] = value
    out["keys"] = keys or []
    out.setdefault("content", "")
    out.setdefault("enabled", True)
    out.setdefault("comment", "")
    out.setdefault("insertion_order", 100)
    out["id"] = str(uuid.uuid4())
    ext = dict(out.get("extensions") or {})
    if unknown:
        ext = {**unknown, **ext}
    if original_id is not None:
        ext["st_original_id"] = original_id
    if ext:
        out["extensions"] = ext
    return out


def book_from_st(raw: Any) -> dict[str, Any] | None:
    """ST character_book / world info -> 平台 WorldBookData。"""
    if not isinstance(raw, dict):
        return None
    out: dict[str, Any] = {}
    unknown: dict[str, Any] = {}
    raw_entries = raw.get("entries")
    for key, value in raw.items():
        if key == "entries":
            continue
        if key in _BOOK_KNOWN:
            out[key] = value
        else:
            unknown[key] = value
    out["entries"] = [entry_from_st(e) for e in (raw_entries or []) if isinstance(e, dict)]
    ext = dict(out.get("extensions") or {})
    if unknown:
        ext = {**unknown, **ext}
    if ext:
        out["extensions"] = ext
    out.setdefault("name", "")
    out.setdefault("description", "")
    out.setdefault("scan_depth", 4)
    out.setdefault("token_budget", 1024)
    out.setdefault("recursive_scanning", False)
    out.setdefault("max_recursion_depth", 3)
    return out


def entry_to_st(entry: dict[str, Any]) -> dict[str, Any]:
    """平台 WorldBookEntry -> ST 条目。"""
    ext = dict(entry.get("extensions") or {})
    original = ext.pop("st_original_id", None)
    out: dict[str, Any] = {
        "keys": as_str_list(entry.get("keys")),
        "secondary_keys": as_str_list(entry.get("secondary_keys")),
        "content": entry.get("content", ""),
        "comment": entry.get("comment", ""),
        "enabled": bool(entry.get("enabled", True)),
        "constant": bool(entry.get("constant", False)),
        "selective": bool(entry.get("selective", False)),
        "case_sensitive": bool(entry.get("case_sensitive", False)),
        "match_whole_words": bool(entry.get("match_whole_words", False)),
        "insertion_order": int(entry.get("insertion_order", 100) or 0),
        "priority": int(entry.get("priority", 10) or 0),
        "position": entry.get("position", "before_char"),
        "extensions": ext,
    }
    for optional in _ENTRY_PASSTHROUGH:
        if entry.get(optional) is not None:
            out[optional] = entry[optional]
    if original is not None:
        out["id"] = original
    return out


def book_to_st(book: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(book, dict):
        return None
    return {
        "name": book.get("name", ""),
        "description": book.get("description", ""),
        "scan_depth": book.get("scan_depth", 4),
        "token_budget": book.get("token_budget", 1024),
        "recursive_scanning": book.get("recursive_scanning", False),
        "extensions": dict(book.get("extensions") or {}),
        "entries": [entry_to_st(e) for e in (book.get("entries") or []) if isinstance(e, dict)],
    }


__all__ = ["as_str_list", "book_from_st", "book_to_st", "entry_from_st", "entry_to_st"]
