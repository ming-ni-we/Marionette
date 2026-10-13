"""序幕服务（OpeningSvc）单元测试。

核心验收：`generate` 返回的草稿每段 `meta.beat_role == "opening"`；
LLM 挂掉 → fallback 文案仍可用（不抛异常、内容非空）。
外加：不落库（返回的是 dict 草稿）、分段规则、三级降级、提示词纯函数。
"""

from __future__ import annotations

from typing import Any

import pytest

from app.adapters.base import ChatMessage
from app.services.opening import (
    BEAT_ROLE_OPENING,
    OpeningSvc,
    build_opening_prompt,
    fallback_from_card,
    fallback_template,
)

LOG = ("多年以后，人们还记得那场雨。\n\n"
       "你推开那扇门，风铃轻响。")


class _StubRouter:
    def __init__(self, replies: list[Any]) -> None:
        self._replies = list(replies)
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        messages: Any,
        *,
        params: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> str:
        self.calls.append({"params": dict(params or {})})
        if not self._replies:
            raise AssertionError("stub router exhausted")
        item = self._replies.pop(0)
        if isinstance(item, BaseException):
            raise item
        return str(item)


WORLD: dict[str, Any] = {
    "title": "雨巷旧案",
    "setting": {
        "summary": "1935 年的上海，雨连着下了半个月。",
        "era": "民国",
        "tone": "阴冷、克制",
        "locations": ["老弄堂", "码头"],
        "rules": ["没人愿意谈起那桩案子"],
    },
    "factions": [{"name": "巡捕房", "stance": "中立"}],
    "outline": {"main_goal": "查明旧案", "nodes": [{"title": "旧案重启"}, {"title": "真凶浮现"}]},
    "opening": "雨敲着铁皮棚。",
    "cast": [{"id": "su_wan", "name": "苏晚"}],
}

CARD: dict[str, Any] = {
    "name": "苏晚",
    "description": "在旧书店做账房",
    "personality": "克制，记性好",
    "first_mes": "「你来晚了。」她头也不抬。",
}

PRESET: dict[str, Any] = {
    "prompt_template": {"system": "克制的民国叙事。"},
    "context_budget": {"max_context_tokens": 8192},
}


def _kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "world": WORLD,
        "card": CARD,
        "preset": PRESET,
        "cast": WORLD["cast"],
        "user_persona": {"name": "记者", "description": "来查旧案"},
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# 主路径
# --------------------------------------------------------------------------- #
class TestGenerateHappyPath:
    async def test_each_paragraph_has_opening_beat_role(self) -> None:
        svc = OpeningSvc(router=_StubRouter([LOG]))
        drafts = await svc.generate(**_kwargs())
        assert len(drafts) == 2
        assert all(d["meta"]["beat_role"] == BEAT_ROLE_OPENING for d in drafts)

    async def test_drafts_are_assistant_narration(self) -> None:
        svc = OpeningSvc(router=_StubRouter([LOG]))
        drafts = await svc.generate(**_kwargs())
        assert all(d["role"] == "assistant" for d in drafts)
        assert all(d["meta"]["is_narration"] is True for d in drafts)

    async def test_paragraphs_split_and_ordered(self) -> None:
        svc = OpeningSvc(router=_StubRouter([LOG]))
        drafts = await svc.generate(**_kwargs())
        assert drafts[0]["content"].startswith("多年以后")
        assert drafts[1]["content"].startswith("你推开那扇门")
        assert [d["meta"]["opening_index"] for d in drafts] == [0, 1]

    async def test_turn_zero(self) -> None:
        svc = OpeningSvc(router=_StubRouter([LOG]))
        drafts = await svc.generate(**_kwargs())
        assert all(d["meta"]["turn"] == 0 for d in drafts)

    async def test_no_speaker_attached_to_narration(self) -> None:
        svc = OpeningSvc(router=_StubRouter([LOG]))
        drafts = await svc.generate(**_kwargs())
        assert all(d["meta"]["speaker_id"] is None for d in drafts)
        assert all(d["meta"]["is_director_note"] is False for d in drafts)

    async def test_single_paragraph_output(self) -> None:
        svc = OpeningSvc(router=_StubRouter(["只有一段没有空行。"]))
        drafts = await svc.generate(**_kwargs())
        assert len(drafts) == 1
        assert drafts[0]["meta"]["beat_role"] == BEAT_ROLE_OPENING

    async def test_whitespace_stripped(self) -> None:
        svc = OpeningSvc(router=_StubRouter(["  首段。  \n\n   次段。   "]))
        drafts = await svc.generate(**_kwargs())
        assert drafts[0]["content"] == "首段。"
        assert drafts[1]["content"] == "次段。"

    async def test_params_are_stable(self) -> None:
        router = _StubRouter([LOG])
        await OpeningSvc(router=router).generate(**_kwargs())
        assert router.calls[0]["params"] == {"temperature": 0.7, "max_tokens": 700}


# --------------------------------------------------------------------------- #
# 降级
# --------------------------------------------------------------------------- #
class TestFallback:
    async def test_upstream_error_falls_back_to_card_and_world(self) -> None:
        svc = OpeningSvc(router=_StubRouter([RuntimeError("boom")]))
        drafts = await svc.generate(**_kwargs())
        assert drafts  # 非空
        assert all(d["meta"]["beat_role"] == BEAT_ROLE_OPENING for d in drafts)
        # L2：world.opening 一段 + card.first_mes 一段
        assert drafts[0]["content"] == "雨敲着铁皮棚。"
        assert "你来晚了" in drafts[1]["content"]
        assert drafts[1]["meta"]["speaker_name"] == "苏晚"
        assert drafts[1]["meta"]["is_narration"] is False

    async def test_empty_llm_output_falls_back(self) -> None:
        svc = OpeningSvc(router=_StubRouter([""]))
        drafts = await svc.generate(**_kwargs())
        assert drafts

    async def test_whitespace_only_output_falls_back(self) -> None:
        svc = OpeningSvc(router=_StubRouter(["   \n\n   "]))
        drafts = await svc.generate(**_kwargs())
        assert drafts
        assert drafts[0]["content"].strip()

    async def test_no_world_opening_uses_composed_blurb(self) -> None:
        world = {**WORLD, "opening": ""}
        svc = OpeningSvc(router=_StubRouter([RuntimeError("x")]))
        drafts = await svc.generate(**_kwargs(world=world))
        text = drafts[0]["content"]
        assert "雨巷旧案" in text
        assert "1935 年的上海" in text

    async def test_no_world_and_no_greeting_uses_template(self) -> None:
        svc = OpeningSvc(router=_StubRouter([RuntimeError("x")]))
        drafts = await svc.generate(**_kwargs(world={"title": "无名之地"}, card={}))
        assert drafts[0]["content"]
        assert drafts[0]["meta"]["beat_role"] == BEAT_ROLE_OPENING

    async def test_never_raises(self) -> None:
        svc = OpeningSvc(router=_StubRouter([RuntimeError("a")]))
        drafts = await svc.generate(**_kwargs())
        assert isinstance(drafts, list)

    async def test_no_worldbook_or_db_dependency(self) -> None:
        """序幕不依赖世界书；空 world/card 也必须给出可用草稿。"""
        svc = OpeningSvc(router=_StubRouter([RuntimeError("x")]))
        drafts = await svc.generate(world={}, card={}, preset={})
        assert drafts and drafts[0]["content"].strip()


# --------------------------------------------------------------------------- #
# 降级函数直测
# --------------------------------------------------------------------------- #
class TestFallbackHelpers:
    def test_fallback_from_card_world_and_greeting(self) -> None:
        drafts = fallback_from_card(CARD, WORLD)
        assert len(drafts) == 2
        assert drafts[0]["content"] == "雨敲着铁皮棚。"
        assert drafts[1]["meta"]["speaker_name"] == "苏晚"

    def test_fallback_from_card_without_greeting(self) -> None:
        drafts = fallback_from_card({}, WORLD)
        assert len(drafts) == 1
        assert drafts[0]["meta"]["is_narration"] is True

    def test_fallback_from_card_without_world_opening(self) -> None:
        drafts = fallback_from_card(CARD, {**WORLD, "opening": ""})
        assert "雨巷旧案" in drafts[0]["content"]

    def test_fallback_template_uses_title(self) -> None:
        drafts = fallback_template({"title": "孤舟"})
        assert "孤舟" in drafts[0]["content"]

    def test_fallback_template_without_title(self) -> None:
        drafts = fallback_template({})
        assert drafts[0]["content"]
        assert drafts[0]["meta"]["beat_role"] == BEAT_ROLE_OPENING

    def test_blurb_includes_rules_and_locations(self) -> None:
        drafts = fallback_from_card({}, {**WORLD, "opening": ""})
        text = drafts[0]["content"]
        assert "老弄堂" in text
        assert "没人愿意谈起那桩案子" in text
        assert "查明旧案" in text


# --------------------------------------------------------------------------- #
# 提示词
# --------------------------------------------------------------------------- #
class TestBuildPrompt:
    def test_message_shape(self) -> None:
        messages = build_opening_prompt(**_kwargs())
        assert [m.role for m in messages] == ["system", "user"]
        assert all(isinstance(m, ChatMessage) for m in messages)

    def test_world_details_embedded(self) -> None:
        system = build_opening_prompt(**_kwargs())[0].content
        assert "民国" in system
        assert "1935 年的上海" in system
        assert "老弄堂" in system
        assert "巡捕房" in system
        assert "查明旧案" in system

    def test_author_opening_quoted(self) -> None:
        system = build_opening_prompt(**_kwargs())[0].content
        assert "雨敲着铁皮棚。" in system

    def test_cast_rendered(self) -> None:
        system = build_opening_prompt(**_kwargs())[0].content
        assert "苏晚" in system

    def test_user_persona_rendered(self) -> None:
        system = build_opening_prompt(**_kwargs())[0].content
        assert "记者" in system
        assert "来查旧案" in system

    def test_card_details_rendered(self) -> None:
        system = build_opening_prompt(**_kwargs())[0].content
        assert "苏晚" in system
        assert "在旧书店做账房" in system

    def test_preset_tone_rendered(self) -> None:
        system = build_opening_prompt(**_kwargs())[0].content
        assert "克制的民国叙事。" in system

    def test_no_cast_omits_block(self) -> None:
        system = build_opening_prompt(**_kwargs(cast=[]))[0].content
        assert "这个世界的角色" not in system

    def test_no_persona_omits_block(self) -> None:
        system = build_opening_prompt(**_kwargs(user_persona=None))[0].content
        assert "【玩家扮演的角色】" not in system

    def test_persona_block_uses_header_marker(self) -> None:
        system = build_opening_prompt(**_kwargs())[0].content
        assert "【玩家扮演的角色】" in system

    def test_empty_world_tolerated(self) -> None:
        messages = build_opening_prompt(world={}, card={}, preset={})
        assert len(messages) == 2
        assert "（世界观信息为空）" in messages[0].content

    def test_instructions_forbid_markdown(self) -> None:
        system = build_opening_prompt(**_kwargs())[0].content
        assert "不要 JSON" in system
        assert "第二人称" in system


# --------------------------------------------------------------------------- #
# 分段
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("A\n\nB", ["A", "B"]),
        ("A\n\n\n\nB", ["A", "B"]),
        ("A\nB", ["A\nB"]),
        ("  A  \n\n  B  ", ["A", "B"]),
        ("", []),
        ("   ", []),
    ],
)
def test_split_paragraphs(text: str, expected: list[str]) -> None:
    from app.services.opening import _split_paragraphs

    assert _split_paragraphs(text) == expected
