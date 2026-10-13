"""AI 导演服务（DirectorSvc）单元测试。

核心验收：4 种输入 **均返回 DirectorDecision 且不抛异常**
  1. 正常 JSON          → 完整解析
  2. 带 ```json 围栏    → 剥围栏解析
  3. 非法 JSON          → fallback（degraded=True）
  4. 上游抛错           → fallback（degraded=True）

外加：熔断跳调用、重试路径（L1 失败→L2 成功）、字段清洗与边界、提示词纯函数。
"""

from __future__ import annotations

from typing import Any

import pytest

from app.adapters.base import ChatMessage
from app.services.director import (
    MAX_SPEAKERS,
    DirectorDecision,
    DirectorSvc,
    _extract_json,
    build_decision_prompt,
)


# --------------------------------------------------------------------------- #
# 假 router：可编程返回文本 / 抛错 / 记录调用
# --------------------------------------------------------------------------- #
class _StubRouter:
    def __init__(self, replies: list[Any]) -> None:
        """`replies` 逐次消费：str=返回文本，Exception 实例=抛出。"""
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


VALID_JSON = """{
  "speakers": [
    {"id": "su_wan", "name": "苏晚", "intent": "试探林九", "direction": "压低声音，不看他"}
  ],
  "narration": "雨敲着铁皮棚。",
  "scene_patch": {"mood": "紧绷", "beat": "两人对质", "present": ["su_wan", "lin_jiu"]},
  "node_triggered": {"id": "n-003", "title": "旧案重启", "brief": "苏晚拿出了那本账册"},
  "relation_updates": [{"from": "su_wan", "to": "lin_jiu", "kind": "猜忌", "tension": -0.4, "note": "她开始怀疑他"}],
  "flags": {"saw_ledger": true},
  "reason": "玩家主动提到了账册"
}"""


def _decide_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "card": {"name": "苏晚", "scenario": "民国上海，一桩旧案。"},
        "preset": {"prompt_template": {"system": "你饰演苏晚。"}},
        "story": {"arc_id": "act1", "beat_index": 3, "flags": {"met_su_wan": True}},
        "cast": [
            {"id": "su_wan", "name": "苏晚", "role": "主角", "voice": "克制、短句"},
            {"id": "lin_jiu", "name": "林九", "role": "配角", "voice": "油滑"},
        ],
        "relations": [{"from": "su_wan", "to": "lin_jiu", "kind": "旧识", "tension": 0.6}],
        "scene": {"location": "老弄堂", "time": "深夜", "present": ["su_wan", "lin_jiu"]},
        "history": [{"role": "user", "content": "我推开那扇门。"}],
        "user_input": "我把账册拍在桌上。",
        "outline": {
            "main_goal": "查明旧案",
            "nodes": [
                {"id": "n-003", "title": "旧案重启", "trigger": "玩家出示账册"},
                {"id": "n-004", "title": "真凶浮现", "trigger": "与林九对峙"},
            ],
        },
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# 1–4：四种输入都不抛异常
# --------------------------------------------------------------------------- #
class TestFourScenarios:
    async def test_normal_json_parsed(self) -> None:
        router = _StubRouter([VALID_JSON])
        decision = await DirectorSvc(router=router).decide(**_decide_kwargs())
        assert isinstance(decision, DirectorDecision)
        assert decision.degraded is False
        assert decision.speakers[0]["id"] == "su_wan"
        assert decision.narration == "雨敲着铁皮棚。"
        assert decision.node_triggered == {
            "id": "n-003",
            "title": "旧案重启",
            "brief": "苏晚拿出了那本账册",
        }
        assert decision.scene_patch["present"] == ["su_wan", "lin_jiu"]
        assert decision.flags == {"saw_ledger": True}
        assert decision.relation_updates[0]["tension"] == -0.4

    async def test_fenced_json_parsed(self) -> None:
        router = _StubRouter(["```json\n" + VALID_JSON + "\n```"])
        decision = await DirectorSvc(router=router).decide(**_decide_kwargs())
        assert decision.degraded is False
        assert decision.speakers[0]["id"] == "su_wan"

    async def test_illegal_json_falls_back(self) -> None:
        router = _StubRouter(["这不是 JSON，我只是随便说了句话。", "第二次也还是垃圾"])
        decision = await DirectorSvc(router=router).decide(
            **_decide_kwargs(fallback_speaker={"id": "su_wan", "name": "苏晚"})
        )
        assert isinstance(decision, DirectorDecision)
        assert decision.degraded is True
        assert "JSON" in decision.reason
        # 降级时保留单角色接话，体验连续
        assert decision.speakers[0]["id"] == "su_wan"
        assert len(router.calls) == 2  # L1 + L2 都试过

    async def test_upstream_error_falls_back(self) -> None:
        router = _StubRouter([RuntimeError("boom"), RuntimeError("boom again")])
        decision = await DirectorSvc(router=router).decide(**_decide_kwargs())
        assert isinstance(decision, DirectorDecision)
        assert decision.degraded is True
        assert decision.speakers == []  # 未给 fallback_speaker → 纯旁白


# --------------------------------------------------------------------------- #
# 降级层次
# --------------------------------------------------------------------------- #
class TestDegradationLayers:
    async def test_circuit_open_skips_llm(self) -> None:
        router = _StubRouter([])  # 一次都不该被调用
        decision = await DirectorSvc(router=router).decide(
            **_decide_kwargs(circuit_open=True, fallback_speaker={"id": "su_wan"})
        )
        assert decision.degraded is True
        assert router.calls == []
        assert decision.speakers[0]["id"] == "su_wan"

    async def test_l1_fails_then_l2_succeeds(self) -> None:
        """首选 response_format 失败（端点不支持）→ 去掉参数重试成功。"""
        router = _StubRouter([RuntimeError("400 bad request"), VALID_JSON])
        decision = await DirectorSvc(router=router).decide(**_decide_kwargs())
        assert decision.degraded is False
        assert len(router.calls) == 2
        assert "response_format" in router.calls[0]["params"]
        assert "response_format" not in router.calls[1]["params"]

    async def test_json_format_only_on_first_attempt(self) -> None:
        router = _StubRouter([VALID_JSON])
        await DirectorSvc(router=router).decide(**_decide_kwargs())
        assert router.calls[0]["params"]["response_format"] == {"type": "json_object"}

    async def test_director_params_are_deterministic(self) -> None:
        router = _StubRouter([VALID_JSON])
        await DirectorSvc(router=router).decide(**_decide_kwargs())
        params = router.calls[0]["params"]
        assert params["temperature"] == 0.4
        assert params["max_tokens"] == 512

    async def test_fallback_never_raises_on_weird_exception(self) -> None:
        router = _StubRouter([KeyboardInterrupt(), KeyboardInterrupt()])
        # KeyboardInterrupt 是 BaseException 子类；decide 内部只 catch Exception，
        # 因此这里断言的是「正常 Exception 族一定被吞」这一契约边界。
        with pytest.raises(KeyboardInterrupt):
            await DirectorSvc(router=router).decide(**_decide_kwargs())


# --------------------------------------------------------------------------- #
# DirectorDecision 字段清洗
# --------------------------------------------------------------------------- #
class TestDecisionCleaning:
    def test_from_json_non_dict_returns_empty(self) -> None:
        for bad in (None, "text", 42, [1, 2]):
            decision = DirectorDecision.from_json(bad)
            assert decision.speakers == []
            assert decision.degraded is False

    def test_speakers_without_id_dropped(self) -> None:
        decision = DirectorDecision.from_json(
            {"speakers": [{"name": "无名"}, {"id": "su_wan", "name": "苏晚"}]}
        )
        assert [s["id"] for s in decision.speakers] == ["su_wan"]

    def test_speakers_capped(self) -> None:
        raw = {"speakers": [{"id": f"c{i}"} for i in range(10)]}
        decision = DirectorDecision.from_json(raw)
        assert len(decision.speakers) == MAX_SPEAKERS

    def test_speakers_non_list_ignored(self) -> None:
        assert DirectorDecision.from_json({"speakers": "苏晚"}).speakers == []

    def test_scene_patch_blank_strings_dropped(self) -> None:
        decision = DirectorDecision.from_json({"scene_patch": {"location": "  ", "mood": "紧绷"}})
        assert decision.scene_patch == {"mood": "紧绷"}

    def test_scene_patch_present_cleaned(self) -> None:
        decision = DirectorDecision.from_json({"scene_patch": {"present": ["a", "", "b"]}})
        assert decision.scene_patch["present"] == ["a", "b"]

    def test_node_without_id_is_none(self) -> None:
        assert DirectorDecision.from_json({"node_triggered": {"title": "无 id"}}).node_triggered is None

    def test_node_non_dict_is_none(self) -> None:
        assert DirectorDecision.from_json({"node_triggered": "n-003"}).node_triggered is None

    def test_relation_update_tension_clamped(self) -> None:
        decision = DirectorDecision.from_json(
            {
                "relation_updates": [
                    {"from": "a", "to": "b", "tension": 5},
                    {"from": "b", "to": "a", "tension": -5},
                ]
            }
        )
        assert decision.relation_updates[0]["tension"] == 1.0
        assert decision.relation_updates[1]["tension"] == -1.0

    def test_relation_update_requires_both_ends(self) -> None:
        decision = DirectorDecision.from_json(
            {"relation_updates": [{"from": "a"}, {"to": "b"}, {"from": "a", "to": "b"}]}
        )
        assert len(decision.relation_updates) == 1

    def test_relation_update_bad_tension_omitted(self) -> None:
        decision = DirectorDecision.from_json(
            {"relation_updates": [{"from": "a", "to": "b", "tension": "很紧张"}]}
        )
        assert "tension" not in decision.relation_updates[0]

    def test_flags_only_scalars(self) -> None:
        decision = DirectorDecision.from_json(
            {"flags": {"ok": True, "n": 3, "s": "x", "bad": {"nested": 1}, "list": [1]}}
        )
        assert decision.flags == {"ok": True, "n": 3, "s": "x"}

    def test_fallback_without_speaker(self) -> None:
        decision = DirectorDecision.fallback(reason="测试")
        assert decision.speakers == []
        assert decision.degraded is True
        assert decision.reason == "测试"

    def test_fallback_with_speaker_inherits_voice(self) -> None:
        decision = DirectorDecision.fallback(
            reason="测试", speaker={"id": "su_wan", "name": "苏晚", "voice": "克制、短句"}
        )
        assert decision.speakers[0]["direction"] == "克制、短句"

    def test_fallback_speaker_without_id_ignored(self) -> None:
        assert DirectorDecision.fallback(reason="x", speaker={"name": "无名"}).speakers == []

    def test_to_payload_round_trip(self) -> None:
        decision = DirectorDecision.from_json(_extract_json(VALID_JSON))
        payload = decision.to_payload()
        assert payload["degraded"] is False
        assert payload["speakers"][0]["id"] == "su_wan"
        assert payload["node_triggered"]["id"] == "n-003"
        # 载荷是拷贝，改动不外泄
        payload["speakers"][0]["id"] = "mutated"
        assert decision.speakers[0]["id"] == "su_wan"


# --------------------------------------------------------------------------- #
# _extract_json 三策略
# --------------------------------------------------------------------------- #
class TestExtractJson:
    def test_plain_json(self) -> None:
        assert _extract_json('{"a": 1}') == {"a": 1}

    def test_fenced_json(self) -> None:
        assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_bare_fence(self) -> None:
        assert _extract_json('```\n{"a": 1}\n```') == {"a": 1}

    def test_json_with_surrounding_prose(self) -> None:
        assert _extract_json('好的，我的裁决如下：\n{"a": 1}\n以上。') == {"a": 1}

    def test_whitespace_tolerant(self) -> None:
        assert _extract_json('  \n {"a": 1} \n ') == {"a": 1}

    def test_empty_returns_none(self) -> None:
        assert _extract_json("") is None

    def test_pure_prose_returns_none(self) -> None:
        assert _extract_json("我想了很久，还是不知道说什么。") is None

    def test_json_array_of_scalars_rejected(self) -> None:
        """导演必须输出对象；数组里没有对象可抠 → 判为非法。"""
        assert _extract_json("[1, 2, 3]") is None
        assert _extract_json('["苏晚", "林九"]') is None

    def test_object_inside_array_is_recovered(self) -> None:
        """模型偶尔会用数组包一层；抠出其中的对象比整条丢弃更有用。"""
        assert _extract_json('[{"id": "su_wan"}]') == {"id": "su_wan"}

    def test_broken_json_returns_none(self) -> None:
        assert _extract_json('{"a": 1,,}') is None

    def test_nested_object_preserved(self) -> None:
        parsed = _extract_json('{"scene": {"beat": "对质"}}')
        assert parsed == {"scene": {"beat": "对质"}}


# --------------------------------------------------------------------------- #
# 提示词构造（纯函数）
# --------------------------------------------------------------------------- #
class TestBuildPrompt:
    def test_returns_system_and_user_messages(self) -> None:
        messages = build_decision_prompt(**_decide_kwargs())
        assert [m.role for m in messages] == ["system", "user"]
        assert all(isinstance(m, ChatMessage) for m in messages)

    def test_system_contains_key_blocks(self) -> None:
        system = build_decision_prompt(**_decide_kwargs())[0].content
        for token in ("世界模拟器", "当前场景", "剧情进度", "可登场角色", "角色关系", "最近对话", "玩家这一轮的言行"):
            assert token in system

    def test_user_input_embedded(self) -> None:
        system = build_decision_prompt(**_decide_kwargs())[0].content
        assert "我把账册拍在桌上。" in system

    def test_empty_user_input_has_placeholder(self) -> None:
        system = build_decision_prompt(**_decide_kwargs(user_input=""))[0].content
        assert "（玩家未输入，视为沉默/等待）" in system

    def test_outline_nodes_listed(self) -> None:
        system = build_decision_prompt(**_decide_kwargs())[0].content
        assert "n-003" in system and "n-004" in system
        assert "玩家出示账册" in system

    def test_fired_node_excluded_from_remaining(self) -> None:
        kwargs = _decide_kwargs(story={"node_id": "n-003", "beat_index": 5})
        system = build_decision_prompt(**kwargs)[0].content
        assert "尚未触发的剧情节点" in system
        assert "id=n-003" not in system
        assert "id=n-004" in system

    def test_pending_node_marked(self) -> None:
        kwargs = _decide_kwargs(story={"pending_node": {"id": "n-004"}})
        system = build_decision_prompt(**kwargs)[0].content
        assert "【已满足待落定】" in system

    def test_all_nodes_fired_message(self) -> None:
        kwargs = _decide_kwargs(
            story={"node_id": "n-004"},
            outline={"main_goal": "x", "nodes": [{"id": "n-003"}, {"id": "n-004"}]},
        )
        system = build_decision_prompt(**kwargs)[0].content
        # n-003 尚未触发，故主线上还有剩余节点
        assert "id=n-003" in system

    def test_fully_exhausted_outline_message(self) -> None:
        """唯一节点已触发 → 提示可自由推进。"""
        kwargs = _decide_kwargs(
            story={"node_id": "n-004"},
            outline={"main_goal": "x", "nodes": [{"id": "n-004"}]},
        )
        system = build_decision_prompt(**kwargs)[0].content
        assert "剧情节点已全部触发" in system

    def test_flags_rendered(self) -> None:
        system = build_decision_prompt(**_decide_kwargs())[0].content
        assert "已知世界事实" in system
        assert "met_su_wan = True" in system

    def test_empty_cast_has_placeholder(self) -> None:
        system = build_decision_prompt(**_decide_kwargs(cast=[]))[0].content
        assert "（暂无角色群信息）" in system

    def test_empty_relations_has_placeholder(self) -> None:
        system = build_decision_prompt(**_decide_kwargs(relations=[]))[0].content
        assert "（暂无关系数据）" in system

    def test_relations_referencing_unknown_cast_skipped(self) -> None:
        kwargs = _decide_kwargs(
            relations=[
                {"from": "su_wan", "to": "lin_jiu", "kind": "旧识"},
                {"from": "ghost", "to": "phantom", "kind": "幽灵"},
            ]
        )
        system = build_decision_prompt(**kwargs)[0].content
        assert "su_wan" in system
        assert "ghost" not in system

    def test_no_worldbooks_needed(self) -> None:
        """导演不依赖世界书命中（那是演出层的事）。"""
        messages = build_decision_prompt(**_decide_kwargs())
        assert len(messages) == 2

    def test_long_history_truncated_to_recent(self) -> None:
        kwargs = _decide_kwargs(
            history=[{"role": "user", "content": f"第{i}句"} for i in range(30)]
        )
        system = build_decision_prompt(**kwargs)[0].content
        assert "第29句" in system
        assert "第0句" not in system

    def test_missing_optionals_tolerated(self) -> None:
        messages = build_decision_prompt(
            card={},
            preset={},
            story={},
            cast=[],
            relations=[],
            scene={},
            history=[],
            user_input="嗨",
        )
        assert len(messages) == 2
        assert "未指定" in messages[0].content
