"""导入侧纯函数：世界书载体的归一化（无需数据库）。"""

from __future__ import annotations

import pytest

from app.core.errors import BadRequestError
from app.services.wb_import import worldbook_data_from_payload as _worldbook_data_from_payload


def test_native_worldbook_payload_is_passthrough() -> None:
    payload = {
        "spec": "rpg_worldbook",
        "spec_version": "1.0",
        "data": {"name": "原生书", "entries": [{"keys": ["a"], "content": "内容"}]},
    }
    data, source = _worldbook_data_from_payload(payload)
    assert source == "native"
    assert data["name"] == "原生书"


def test_st_world_info_list_form_is_normalized() -> None:
    payload = {
        "entries": [
            {"keys": ["咖啡", "咖啡馆"], "content": "咖啡内容", "insertion_order": 7},
            {"key": "雨", "content": "雨的内容", "disable": True, "order": 3},
        ]
    }
    data, source = _worldbook_data_from_payload(payload)
    assert source == "st_worldbook"
    assert len(data["entries"]) == 2
    first, second = data["entries"]
    assert first["keys"] == ["咖啡", "咖啡馆"]
    assert second["keys"] == ["雨"]
    assert second["enabled"] is False
    assert second["insertion_order"] == 3


def test_st_world_info_dict_entries_form_is_normalized() -> None:
    payload = {
        "name": "字典条目世界书",
        "entries": {
            "0": {"key": "甲", "content": "甲内容", "order": 1},
            "1": {"key": "乙", "content": "乙内容", "order": 2},
        },
    }
    data, source = _worldbook_data_from_payload(payload)
    assert source == "st_worldbook"
    assert len(data["entries"]) == 2
    assert sorted(e["keys"][0] for e in data["entries"]) == ["乙", "甲"]


def test_missing_entries_raises_bad_request() -> None:
    with pytest.raises(BadRequestError) as err:
        _worldbook_data_from_payload({"name": "一本书但没有条目"})
    assert "entries" in str(err.value)
