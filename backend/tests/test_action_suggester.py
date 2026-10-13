"""行动建议服务（ActionSuggesterSvc）单元测试。

核心验收：`actions` 帧有内容；suggester 抛错 → **不抛异常**（返回兜底或空列表），
对话主流程正常 done。外加：JSON 容错、字段清洗、tone 归一、去重、条数上限、
提示词纯函数、规则兜底。
"""

from __future__ import annotations

from typing import Any

import pytest

from app.adapters.base import ChatMessage
from app.services.action_suggester import (
    DEFAULT_COUNT,
    MAX_COUNT,
    TONES,
    ActionSuggesterSvc,
    build_suggest_prompt,
    fallback_suggestions,
)


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
        self.calls.append({"messages": list(messages), "params": dict(params or {})})
        if not self._replies:
            raise AssertionError("stub router exhausted")
        item = self._replies.pop(0)
        if isinstance(item, BaseException):
            raise item
        return str(item)


VALID = """{"actions": [
  {"label": "把账册推到他面前", "hint": "看他会不会露馅", "tone": "act"},
  {"label": "问他三十七笔银子去哪了", "hint": "直接施压", "tone": "speak"},
  {"label": "盯着他的指尖看", "hint": "小动作会出卖人", "tone": "observe"}
]}"""


def _kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "scene": {"location": "老弄堂", "time": "深夜", "mood": "压抑", "beat": "两人对质",
                  "present": ["su_wan", "lin_jiu"]},
        "story": {"flags": {"saw_ledger": True}},
        "cast": [
            {"id": "su_wan", "name": "苏晚", "voice": "克制、短句"},
            {"id": "lin_jiu", "name": "林九", "voice": "油滑"},
        ],
        "recent_messages": [
            {"role": "assistant", "name": "苏晚", "content": "你来晚了。"},
            {"role": "user", "content": "账册是我找到的。"},
        ],
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# 主路径
# --------------------------------------------------------------------------- #
class TestSuggestHappyPath:
    async def test_valid_json_returns_three(self) -> None:
        svc = ActionSuggesterSvc(router=_StubRouter([VALID]))
        actions = await svc.suggest(**_kwargs())
        assert len(actions) == 3
        assert actions[0]["label"] == "把账册推到他面前"
        assert actions[0]["tone"] == "act"
        assert all(set(a) == {"id", "label", "hint", "tone"} for a in actions)

    async def test_fenced_json_tolerated(self) -> None:
        svc = ActionSuggesterSvc(router=_StubRouter(["```json\n" + VALID + "\n```"]))
        actions = await svc.suggest(**_kwargs())
        assert len(actions) == 3

    async def test_prose_around_json_tolerated(self) -> None:
        svc = ActionSuggesterSvc(router=_StubRouter(["好的：\n" + VALID + "\n以上。"]))
        actions = await svc.suggest(**_kwargs())
        assert len(actions) == 3

    async def test_bare_array_accepted(self) -> None:
        """模型偶尔直接给数组，没有 actions 包装。"""
        svc = ActionSuggesterSvc(
            router=_StubRouter(['[{"label": "观察", "tone": "observe"}]'])
        )
        actions = await svc.suggest(**_kwargs())
        assert actions[0]["label"] == "观察"

    async def test_fenced_bare_array_accepted(self) -> None:
        svc = ActionSuggesterSvc(
            router=_StubRouter(['```json\n[{"label": "围栏数组"}]\n```'])
        )
        actions = await svc.suggest(**_kwargs())
        assert actions[0]["label"] == "围栏数组"

    async def test_array_with_prose_accepted(self) -> None:
        svc = ActionSuggesterSvc(
            router=_StubRouter(['建议如下：\n[{"label": "夹在散文里的数组"}]\n以上。'])
        )
        actions = await svc.suggest(**_kwargs())
        assert actions[0]["label"] == "夹在散文里的数组"

    async def test_ids_are_stable_and_unique(self) -> None:
        svc = ActionSuggesterSvc(router=_StubRouter([VALID]))
        actions = await svc.suggest(**_kwargs())
        ids = [a["id"] for a in actions]
        assert ids == ["a0", "a1", "a2"]

    async def test_count_limits_output(self) -> None:
        svc = ActionSuggesterSvc(router=_StubRouter([VALID]))
        actions = await svc.suggest(**_kwargs(count=2))
        assert len(actions) == 2

    async def test_count_clamped_to_max(self) -> None:
        seven = '{"actions": [' + ",".join(
            f'{{"label": "选项{i}", "tone": "act"}}' for i in range(7)
        ) + "]}"
        svc = ActionSuggesterSvc(router=_StubRouter([seven]))
        actions = await svc.suggest(**_kwargs(count=99))
        assert len(actions) == MAX_COUNT

    async def test_count_zero_clamped_to_one(self) -> None:
        svc = ActionSuggesterSvc(router=_StubRouter([VALID]))
        actions = await svc.suggest(**_kwargs(count=0))
        assert len(actions) == 1


# --------------------------------------------------------------------------- #
# 失败路径：绝不抛异常
# --------------------------------------------------------------------------- #
class TestFailurePaths:
    async def test_upstream_error_returns_fallback(self) -> None:
        svc = ActionSuggesterSvc(router=_StubRouter([RuntimeError("boom"), RuntimeError("boom")]))
        actions = await svc.suggest(**_kwargs())
        assert actions  # 非空：走了规则兜底
        assert actions[0]["label"].startswith("仔细观察")

    async def test_upstream_error_no_fallback_returns_empty(self) -> None:
        svc = ActionSuggesterSvc(router=_StubRouter([RuntimeError("boom"), RuntimeError("boom")]))
        actions = await svc.suggest(**_kwargs(use_fallback=False))
        assert actions == []

    async def test_illegal_json_returns_fallback(self) -> None:
        svc = ActionSuggesterSvc(router=_StubRouter(["我不知道该建议什么。", "还是不知道。"]))
        actions = await svc.suggest(**_kwargs())
        assert actions
        assert all(a["tone"] in TONES for a in actions)

    async def test_empty_actions_list_returns_fallback(self) -> None:
        svc = ActionSuggesterSvc(router=_StubRouter(['{"actions": []}', '{"actions": []}']))
        actions = await svc.suggest(**_kwargs())
        assert actions  # 空列表视为失败 -> 兜底

    async def test_retry_removes_response_format(self) -> None:
        router = _StubRouter([RuntimeError("400 unsupported"), VALID])
        svc = ActionSuggesterSvc(router=router)
        actions = await svc.suggest(**_kwargs())
        assert len(actions) == 3
        assert "response_format" in router.calls[0]["params"]
        assert "response_format" not in router.calls[1]["params"]

    async def test_never_raises_on_many_failures(self) -> None:
        svc = ActionSuggesterSvc(router=_StubRouter([RuntimeError("x")] * 4))
        actions = await svc.suggest(**_kwargs())
        assert isinstance(actions, list)

    async def test_low_token_params(self) -> None:
        router = _StubRouter([VALID])
        await ActionSuggesterSvc(router=router).suggest(**_kwargs())
        assert router.calls[0]["params"]["max_tokens"] == 200


# --------------------------------------------------------------------------- #
# 清洗
# --------------------------------------------------------------------------- #
class TestCleaning:
    async def test_item_without_label_dropped(self) -> None:
        raw = '{"actions": [{"hint": "无 label"}, {"label": "有效", "tone": "speak"}]}'
        svc = ActionSuggesterSvc(router=_StubRouter([raw]))
        actions = await svc.suggest(**_kwargs())
        assert [a["label"] for a in actions] == ["有效"]

    async def test_text_key_accepted_as_label(self) -> None:
        svc = ActionSuggesterSvc(router=_StubRouter(['{"actions": [{"text": "用 text 字段"}]}']))
        actions = await svc.suggest(**_kwargs())
        assert actions[0]["label"] == "用 text 字段"

    async def test_invalid_tone_normalized_to_observe(self) -> None:
        raw = '{"actions": [{"label": "A", "tone": "打架"}, {"label": "B", "tone": "SPEAK"}]}'
        svc = ActionSuggesterSvc(router=_StubRouter([raw]))
        actions = await svc.suggest(**_kwargs())
        assert actions[0]["tone"] == "observe"  # 非法 -> observe
        assert actions[1]["tone"] == "speak"  # 大小写不敏感

    async def test_duplicate_labels_deduped(self) -> None:
        raw = '{"actions": [{"label": "同样的话"}, {"label": "同样的话"}, {"label": "别的"}]}'
        svc = ActionSuggesterSvc(router=_StubRouter([raw]))
        actions = await svc.suggest(**_kwargs())
        assert [a["label"] for a in actions] == ["同样的话", "别的"]

    async def test_long_label_truncated(self) -> None:
        raw = '{"actions": [{"label": "' + "很长的建议" * 20 + '"}]}'
        svc = ActionSuggesterSvc(router=_StubRouter([raw]))
        actions = await svc.suggest(**_kwargs())
        assert len(actions[0]["label"]) <= 40

    async def test_non_dict_items_dropped(self) -> None:
        svc = ActionSuggesterSvc(router=_StubRouter(['{"actions": ["字符串", 42, {"label": "好"}]}']))
        actions = await svc.suggest(**_kwargs())
        assert [a["label"] for a in actions] == ["好"]

    async def test_missing_hint_defaults_empty(self) -> None:
        svc = ActionSuggesterSvc(router=_StubRouter(['{"actions": [{"label": "A"}]}']))
        actions = await svc.suggest(**_kwargs())
        assert actions[0]["hint"] == ""

    async def test_actions_key_wrong_type_falls_back(self) -> None:
        svc = ActionSuggesterSvc(router=_StubRouter(['{"actions": "三条建议"}'] * 2))
        actions = await svc.suggest(**_kwargs())
        assert actions  # 走兜底

    async def test_unrelated_object_falls_back(self) -> None:
        """模型返回了一个无关 JSON 对象（无 actions 键）→ 视为失败，走兜底。"""
        svc = ActionSuggesterSvc(
            router=_StubRouter(['{"scene": "老弄堂", "mood": "压抑"}'] * 2)
        )
        actions = await svc.suggest(**_kwargs())
        assert actions[0]["label"].startswith("仔细观察")


# --------------------------------------------------------------------------- #
# 规则兜底
# --------------------------------------------------------------------------- #
class TestFallback:
    def test_fallback_uses_location(self) -> None:
        actions = fallback_suggestions({"location": "地下室"})
        assert "地下室" in actions[0]["label"]

    def test_fallback_without_location(self) -> None:
        actions = fallback_suggestions({})
        assert "四周" in actions[0]["label"]

    def test_fallback_count(self) -> None:
        assert len(fallback_suggestions({}, count=2)) == 2
        assert len(fallback_suggestions({}, count=DEFAULT_COUNT)) == DEFAULT_COUNT

    def test_fallback_tones_valid(self) -> None:
        assert all(a["tone"] in TONES for a in fallback_suggestions({}))


# --------------------------------------------------------------------------- #
# 提示词
# --------------------------------------------------------------------------- #
class TestBuildPrompt:
    def test_message_shape(self) -> None:
        messages = build_suggest_prompt(**_kwargs())
        assert [m.role for m in messages] == ["system", "user"]
        assert all(isinstance(m, ChatMessage) for m in messages)

    def test_contains_scene(self) -> None:
        system = build_suggest_prompt(**_kwargs())[0].content
        assert "老弄堂" in system
        assert "两人对质" in system

    def test_contains_present_cast_with_names(self) -> None:
        system = build_suggest_prompt(**_kwargs())[0].content
        assert "苏晚（su_wan）" in system
        assert "克制、短句" in system

    def test_unknown_present_id_still_listed(self) -> None:
        system = build_suggest_prompt(**_kwargs(scene={"present": ["ghost"]}))[0].content
        assert "ghost" in system

    def test_contains_recent_messages(self) -> None:
        system = build_suggest_prompt(**_kwargs())[0].content
        assert "你来晚了" in system
        assert "账册是我找到的" in system

    def test_history_truncated_to_recent_six(self) -> None:
        messages = [{"role": "user", "content": f"第{i}句"} for i in range(20)]
        system = build_suggest_prompt(**_kwargs(recent_messages=messages))[0].content
        assert "第19句" in system
        assert "第0句" not in system

    def test_flags_rendered(self) -> None:
        system = build_suggest_prompt(**_kwargs())[0].content
        assert "saw_ledger = True" in system

    def test_no_flags_omits_block(self) -> None:
        system = build_suggest_prompt(**_kwargs(story={}))[0].content
        assert "已知事实" not in system

    def test_no_present_omits_block(self) -> None:
        system = build_suggest_prompt(**_kwargs(scene={}))[0].content
        assert "在场角色" not in system

    def test_count_embedded_in_instruction(self) -> None:
        system = build_suggest_prompt(**_kwargs(count=2))[0].content
        assert "2 条行动建议" in system

    def test_missing_everything_tolerated(self) -> None:
        messages = build_suggest_prompt(scene={}, story={}, cast=[], recent_messages=[])
        assert len(messages) == 2
        assert "未指定" in messages[0].content

    @pytest.mark.parametrize("tone", sorted(TONES))
    def test_all_tones_documented_in_system(self, tone: str) -> None:
        system = build_suggest_prompt(**_kwargs())[0].content
        assert tone in system
