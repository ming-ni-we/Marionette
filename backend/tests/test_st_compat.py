"""AC-05 / AC-06 机械证据：SillyTavern V2 导入还原 + 导出可回导（逐字段等价）。

这些是**纯单元测试**，不需要数据库：直接驱动 STCompatAdapter 与 st_image 的字节读写。
"""

from __future__ import annotations

import base64
import copy
import io
import json
from typing import Any

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from app.core.errors import BadRequestError
from app.services.st_compat import STCompatAdapter, to_st_v2

ADAPTER = STCompatAdapter()

# 一张字段最全的 ST V2 卡：覆盖 AC-05 要求的 描述/人格/场景/开场白/示例对话/头像 + 内嵌角色书
ST_V2: dict[str, Any] = {
    "spec": "chara_card_v2",
    "spec_version": "2.0",
    "data": {
        "name": "沈知夏",
        "description": "二十七岁，图书馆管理员，说话总是不紧不慢。",
        "personality": "安静、耐心、偶尔冷幽默",
        "scenario": "市图书馆的闭馆前半小时，阅览室只剩你们两个。",
        "first_mes": "她把手里的书合上：「闭馆还有半小时，你要借的话，我帮你先办。」",
        "mes_example": "{{user}}: 这本书好看吗？\n{{char}}: 「还行。看完你会想去一趟北方。」",
        "creator_notes": "测试用备注，不应进入 prompt 渲染。",
        "system_prompt": "你是 {{char}}，请保持语气克制。",
        "post_history_instructions": "回复控制在三句以内。",
        "alternate_greetings": ["她把灯关了一盏：「再不走就锁门了。」"],
        "tags": ["日常", "图书馆", "安静"],
        "creator": "tester",
        "character_version": "1.3",
        "extensions": {"talkativeness": 0.4, "custom_plugin": {"flag": True}},
        "character_book": {
            "name": "市图书馆",
            "description": "闭馆前的图书馆全景。",
            "scan_depth": 3,
            "token_budget": 512,
            "recursive_scanning": True,
            "entries": [
                {
                    "keys": ["图书馆", "闭馆"],
                    "content": "这间图书馆晚上七点闭馆，借还台在门口左手边。",
                    "comment": "场馆规则",
                    "enabled": True,
                    "insertion_order": 10,
                    "priority": 40,
                    "id": 7,
                },
                {
                    "key": "雨",
                    "content": "窗外开始下雨，雨声压在玻璃上。",
                    "disable": True,
                    "order": 5,
                    "uid": 11,
                },
            ],
        },
    },
    "create_date": "2026-01-01T00:00:00Z",
    "custom_plugin_flag": True,
}


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    """剔除每次导入都会变的字段（imported_at 时间戳、平台生成的条目 UUID），其余逐字段比较。"""
    clone = json.loads(json.dumps(data, ensure_ascii=False))
    rpg = ((clone.get("extensions") or {}).get("rpg") or {})
    if isinstance(rpg.get("source"), dict):
        rpg["source"]["imported_at"] = "<ts>"
    book = clone.get("character_book")
    if isinstance(book, dict):
        for index, entry in enumerate(book.get("entries") or []):
            if isinstance(entry, dict):
                # 平台生成 UUID（外部原始 id 保存在 extensions.st_original_id，必须保留）
                entry["id"] = f"<entry-{index}>"
    return clone


def _png_with_text(chunks: dict[str, Any]) -> bytes:
    image = Image.new("RGB", (128, 192), (18, 24, 38))
    meta = PngInfo()
    for key, payload in chunks.items():
        token = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
        meta.add_text(key, token)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", pnginfo=meta)
    return buffer.getvalue()


# --------------------------------------------------------------------------- #
# AC-05：导入还原
# --------------------------------------------------------------------------- #
def test_ac05_png_card_restores_description_personality_scenario_greeting_example() -> None:
    parsed = ADAPTER.parse_bytes(_png_with_text({"chara": ST_V2}), filename="shen.png")
    data = parsed.payload["data"]

    assert parsed.source_format == "st_v2"
    assert data["description"] == ST_V2["data"]["description"]
    assert data["personality"] == ST_V2["data"]["personality"]
    assert data["scenario"] == ST_V2["data"]["scenario"]
    assert data["first_mes"] == ST_V2["data"]["first_mes"]
    assert data["mes_example"] == ST_V2["data"]["mes_example"]
    assert data["alternate_greetings"] == ST_V2["data"]["alternate_greetings"]
    assert data["tags"] == ST_V2["data"]["tags"]
    # 头像：PNG 原始字节被保留为头像载体
    assert parsed.image is not None
    assert parsed.image.content_type == "image/png"
    assert parsed.image.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_ac05_character_book_entries_are_normalized() -> None:
    parsed = ADAPTER.parse_bytes(_png_with_text({"chara": ST_V2}), filename="shen.png")
    book = parsed.payload["data"]["character_book"]

    assert book["name"] == "市图书馆"
    assert book["token_budget"] == 512
    assert book["recursive_scanning"] is True
    first, second = book["entries"]
    assert first["keys"] == ["图书馆", "闭馆"]
    assert first["priority"] == 40
    assert first["extensions"]["st_original_id"] == 7
    # key(单数) -> keys；disable -> enabled 取反；order -> insertion_order
    assert second["keys"] == ["雨"]
    assert second["enabled"] is False
    assert second["insertion_order"] == 5


def test_ccv3_takes_priority_over_chara() -> None:
    v3 = copy.deepcopy(ST_V2)
    v3["spec"] = "chara_card_v3"
    v3["spec_version"] = "3.0"
    v3["data"]["name"] = "V3角色"
    v3["data"]["assets"] = [{"type": "icon", "uri": "ccdefault:"}]
    parsed = ADAPTER.parse_bytes(_png_with_text({"chara": ST_V2, "ccv3": v3}), filename="both.png")

    assert parsed.payload["data"]["name"] == "V3角色"
    assert parsed.source_format == "st_v3"
    # V3 独有字段落 st_unknown 保全，不参与渲染
    assert "assets" in parsed.unknown_data


def test_v1_bare_fields_are_accepted() -> None:
    parsed = ADAPTER.parse_payload(
        {
            "name": "旧卡",
            "description": "只有六个字段的 V1 卡",
            "personality": "沉默",
            "scenario": "走廊",
            "first_mes": "他点了点头。",
            "mes_example": "{{user}}: 在吗\n{{char}}: 在。",
        }
    )
    assert parsed.source_format == "st_v1"
    assert parsed.payload["data"]["name"] == "旧卡"
    assert parsed.payload["data"]["tags"] == []
    assert any("V1" in w for w in parsed.warnings)


# --------------------------------------------------------------------------- #
# AC-06：导出可回导 + 往返字段等价
# --------------------------------------------------------------------------- #
def test_ac06_roundtrip_field_equivalence() -> None:
    first = ADAPTER.parse_payload(copy.deepcopy(ST_V2))
    st_export = to_st_v2(first.payload)

    # 导出的确产出了 ST V2 结构
    assert st_export["spec"] == "chara_card_v2"
    assert st_export["spec_version"] == "2.0"
    # 逐字段与原始 ST 文件一致
    for field in (
        "name",
        "description",
        "personality",
        "scenario",
        "first_mes",
        "mes_example",
        "creator_notes",
        "system_prompt",
        "post_history_instructions",
        "alternate_greetings",
        "tags",
        "creator",
        "character_version",
    ):
        assert st_export["data"][field] == ST_V2["data"][field], field

    # 内嵌角色书：识别字段一致，别名已归一（key->keys、disable->enabled、order->insertion_order）
    book_out = st_export["data"]["character_book"]
    book_src = ST_V2["data"]["character_book"]
    assert book_out["name"] == book_src["name"]
    assert book_out["token_budget"] == book_src["token_budget"]
    first_out, second_out = book_out["entries"]
    assert first_out["keys"] == book_src["entries"][0]["keys"]
    assert first_out["content"] == book_src["entries"][0]["content"]
    assert first_out["insertion_order"] == book_src["entries"][0]["insertion_order"]
    assert first_out["id"] == book_src["entries"][0]["id"]  # 原始条目 id 原样带回
    assert second_out["keys"] == [book_src["entries"][1]["key"]]
    assert second_out["enabled"] is (not book_src["entries"][1]["disable"])
    assert second_out["insertion_order"] == book_src["entries"][1]["order"]

    # 未知字段原样写回
    assert st_export["data"]["extensions"]["talkativeness"] == 0.4
    assert st_export["custom_plugin_flag"] is True

    # 回导 -> 平台卡 -> 与首次导入的 data 逐字段等价
    second = ADAPTER.parse_payload(copy.deepcopy(st_export))
    assert second.source_format == "st_v2"
    assert _normalize(first.payload["data"]) == _normalize(second.payload["data"])
    assert first.unknown_data == second.unknown_data
    assert first.unknown_envelope == second.unknown_envelope


def test_ac06_png_export_is_reimportable() -> None:
    from app.services.st_image import build_png_card

    first = ADAPTER.parse_payload(copy.deepcopy(ST_V2))
    blob = build_png_card(to_st_v2(first.payload), seed="沈知夏")
    assert blob[:8] == b"\x89PNG\r\n\x1a\n"

    second = ADAPTER.parse_bytes(blob, filename="export.png")
    assert second.payload["data"]["name"] == "沈知夏"
    assert second.payload["data"]["mes_example"] == ST_V2["data"]["mes_example"]
    assert _normalize(second.payload["data"]) == _normalize(first.payload["data"])


def test_unknown_fields_survive_three_conversions() -> None:
    payload = copy.deepcopy(ST_V2)
    payload["data"]["future_field"] = {"nested": [1, 2, 3]}
    payload["envelope_only"] = "keep-me"

    first = ADAPTER.parse_payload(payload)
    assert first.unknown_data["future_field"] == {"nested": [1, 2, 3]}
    assert first.unknown_envelope["envelope_only"] == "keep-me"
    assert "data.future_field" in first.unknown_keys

    st = to_st_v2(first.payload)
    assert st["data"]["future_field"] == {"nested": [1, 2, 3]}
    assert st["envelope_only"] == "keep-me"

    second = ADAPTER.parse_payload(st)
    assert second.unknown_data == first.unknown_data
    assert second.unknown_envelope == first.unknown_envelope


# --------------------------------------------------------------------------- #
# 非 V2 格式必须给明确中文错误，不得 500
# --------------------------------------------------------------------------- #
def test_unrecognized_payload_raises_bad_request() -> None:
    with pytest.raises(BadRequestError) as err:
        ADAPTER.parse_payload({"hello": "world"})
    assert "无法识别" in str(err.value)


def test_non_image_bytes_raise_bad_request() -> None:
    with pytest.raises(BadRequestError) as err:
        ADAPTER.parse_bytes(b"this is not a card", filename="x.txt")
    assert "PNG/WEBP" in str(err.value) or "UTF-8 JSON" in str(err.value)


def test_png_without_card_chunk_raises_bad_request() -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), (1, 2, 3)).save(buffer, format="PNG")
    with pytest.raises(BadRequestError) as err:
        ADAPTER.parse_bytes(buffer.getvalue(), filename="plain.png")
    assert "角色卡数据" in str(err.value)


def test_native_card_is_passthrough() -> None:
    native = {
        "spec": "rpg_card",
        "spec_version": "1.0",
        "data": {"name": "原生", "first_mes": "你好", "tags": ["x"]},
        "extensions": {"rpg": {"owner_id": "local"}},
    }
    parsed = ADAPTER.parse_payload(native)
    assert parsed.source_format == "native"
    assert parsed.payload["data"]["name"] == "原生"
    assert parsed.unknown_keys == []
