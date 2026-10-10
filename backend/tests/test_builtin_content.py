"""内置示例内容必须"真实可用"（禁止占位文案），且能被引擎正确裁决。"""

from __future__ import annotations

import pytest

from app.schemas.content import CardInput, PresetInput, WorldBookInput
from app.services.builtin_content import sample_cards, sample_presets, sample_worldbooks
from app.services.world_info import WorldInfoEngine

WB_IDS = ["11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"]
# 注意："placeholders" 是预设 Schema 的合法字段名，不作为占位文案标记
PLACEHOLDER_MARKERS = ("lorem ipsum", "todo:", "占位文案", "待填", "待补充", "tbd")


def test_all_builtin_cards_match_the_contract_schema() -> None:
    cards = sample_cards(WB_IDS)
    assert 3 <= len(cards) <= 5, "首启向导要求 3–5 张示例卡"
    for payload in cards:
        model = CardInput.model_validate(payload)
        assert model.data.name
        assert model.data.first_mes, "示例卡必须有开场白"
        assert model.data.description
        assert len(model.data.description) >= 30, "描述不能是一句话敷衍"
        assert model.data.mes_example, "示例卡必须有示例对话"
        assert model.data.alternate_greetings
        assert model.data.extensions["rpg"]["default_worldbook_ids"] == WB_IDS


def test_builtin_cards_have_no_placeholder_copy() -> None:
    blob = str(sample_cards(WB_IDS)) + str(sample_worldbooks()) + str(sample_presets())
    lowered = blob.lower()
    for marker in PLACEHOLDER_MARKERS:
        assert marker not in lowered, f"示例内容出现占位痕迹：{marker}"


def test_builtin_worldbooks_match_schema_and_have_entries() -> None:
    books = sample_worldbooks()
    assert len(books) >= 1
    for payload in books:
        model = WorldBookInput.model_validate(payload)
        assert model.data.entries, "世界书必须有条目"
        for entry in model.data.entries:
            assert entry.content.strip()
            assert entry.keys or entry.constant, "条目要么有关键词，要么是常驻"


def test_builtin_preset_matches_schema() -> None:
    presets = sample_presets()
    assert len(presets) >= 1
    preset = PresetInput.model_validate(presets[0])
    assert preset.data.prompt_template.system
    assert "{{char}}" in preset.data.prompt_template.system
    assert preset.data.sampling.temperature == pytest.approx(0.85)


def test_city_worldbook_constant_entry_is_always_injected() -> None:
    """常驻条目在任何样例文本下都必须进入预算内（否则示例卡会"没设定"）。"""
    city = sample_worldbooks()[0]
    engine = WorldInfoEngine()
    result = engine.test(city["data"], "随便说一句完全无关的话。")
    constant = [e for e in result["entries"] if e["match_type"] == "constant"]
    assert constant, "城南街区世界书应含常驻总览条目"
    assert all(e["in_budget"] for e in constant)


def test_city_worldbook_keyword_triggers_named_locations() -> None:
    city = sample_worldbooks()[0]
    result = WorldInfoEngine().test(city["data"], "我们约在那家便利店门口吧。")
    hit = [e for e in result["entries"] if e["matched"] and e["match_type"] == "keyword"]
    assert hit, "提到便利店应命中至少一条关键词条目"
    assert any(e["in_budget"] for e in hit)
