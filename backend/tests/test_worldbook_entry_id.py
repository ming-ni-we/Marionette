"""`WorldBookEntry.id` 放宽为字符串（无需数据库）。

回归背景：ST 的条目 id 是 int（`id`/`uid`），平台内部也把 entry id 当作
不透明字符串（见 `services/world_info.py`）。旧 Schema 强制 `UUID` 会让
`{"id": "c", ...}` 在创建校验（400）与响应序列化（500）两处同时炸。
"""

from __future__ import annotations

import uuid

from app.schemas.content import WorldBookData, WorldBookEntry


def test_entry_accepts_custom_string_id() -> None:
    book = WorldBookData.model_validate(
        {
            "name": "常驻书",
            "entries": [
                {"id": "c", "keys": [], "content": "常驻设定", "constant": True, "priority": 100}
            ],
        }
    )
    assert book.entries[0].id == "c"


def test_entry_accepts_uuid_string_id() -> None:
    uid = str(uuid.uuid4())
    book = WorldBookData.model_validate(
        {"entries": [{"id": uid, "keys": ["a"], "content": "x"}]}
    )
    assert book.entries[0].id == uid


def test_entry_id_is_optional() -> None:
    entry = WorldBookEntry.model_validate({"keys": ["a"], "content": "x"})
    assert entry.id is None


def test_entry_dumps_custom_id_as_plain_string() -> None:
    """model_dump(mode="json") 后 id 仍是字符串，不因类型放宽而变形。"""
    entry = WorldBookEntry.model_validate({"id": "c", "keys": [], "content": "x"})
    assert entry.model_dump(mode="json")["id"] == "c"
