"""导入侧纯函数：世界书载体的归一化（无需数据库）。"""

from __future__ import annotations

import uuid
from typing import get_args

import pytest

from app.core.errors import BadRequestError
from app.schemas.import_export import ImportResult
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


def test_import_result_accepts_st_worldbook() -> None:
    """契约补齐：ImportResult.source_format 必须接受 st_worldbook（世界书导入）。"""
    result = ImportResult(source_format="st_worldbook", object_id=uuid.uuid4())
    assert result.source_format == "st_worldbook"


def test_wb_import_source_format_matches_contract_enum() -> None:
    """防止再次漂移：wb_import 返回的 source_format 必须落在 ImportResult 枚举内。"""
    allowed = set(get_args(ImportResult.model_fields["source_format"].annotation))
    _, st_source = _worldbook_data_from_payload({"entries": [{"keys": ["a"], "content": "x"}]})
    _, native_source = _worldbook_data_from_payload(
        {"spec": "rpg_worldbook", "data": {"name": "x", "entries": []}}
    )
    assert st_source in allowed
    assert native_source in allowed
    assert st_source == "st_worldbook"
