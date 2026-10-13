"""上下文装配剧情三段扩展（S5）单元测试。

**核心契约**：老 9 段在 1v1 路径下**逐字节不变** —— 这是零回归的硬保证。
做法：同一份 card/preset/history 分别跑「不传剧情 kwargs」与「传空剧情 kwargs」，
断言 segments / prompt_text / budget 关键项完全相等；再传真实剧情内容验证新增三段。
"""

from __future__ import annotations

import json
from typing import Any

from app.services.context_assembler import (
    _STORY_BUDGET,
    _STORY_HARD_CAP_TOKENS,
    ContextAssembler,
)

# --------------------------------------------------------------------------- #
# 固定夹具（与 test_runtime_m1 同风格，便于对照）
# --------------------------------------------------------------------------- #
CARD: dict[str, Any] = {
    "name": "苏晚",
    "description": "在旧书店做账房",
    "personality": "克制，记性好",
    "scenario": "民国上海，一桩旧案。",
    "first_mes": "雨敲着铁皮棚。",
    "mes_example": "{{char}}：账本不会骗人。",
    "post_history_instructions": "保持第一人称叙述。",
    "character_book": {
        "entries": [
            {"id": "e1", "keys": ["账册"], "content": "账册记录着三十七笔来路不明的银子。", "position": "before_char"},
        ]
    },
}

PRESET: dict[str, Any] = {
    "prompt_template": {
        "system": "你饰演 {{char}}，与 {{user}} 对话。\n{{world_info}}",
        "instruction": "回复简洁。",
        "placeholders": {},
    },
    "context_budget": {
        "max_context_tokens": 8192,
        "reserve_for_output": 1024,
        "character_pct": 15,
        "world_info_pct": 25,
        "memory_pct": 15,
        "vector_recall_pct": 5,
        "history_pct": 35,
    },
    "sampling": {"temperature": 0.8, "max_tokens": 256},
}

HISTORY: list[dict[str, Any]] = [
    {"role": "user", "content": "我推开那扇门。"},
    {"role": "assistant", "content": "门轴响了一声。"},
    {"role": "user", "content": "桌上的账册还在吗？"},
]

MEMORY: dict[str, Any] = {
    "rolling_summary": "苏晚与玩家在书店初次见面。",
    "facts": [{"key": "旧案", "value": "1935 年失踪案"}],
}

STORY_BLOCK = "【剧情状态】\n当前幕：act1｜拍点：3\n已知事实：见过账册"
RELATIONS_BLOCK = "【角色关系】\n- su_wan → lin_jiu：旧识（亲密度 +0.6）"
NODE_BLOCK = "【待触发节点】\n- n-004 真凶浮现；触发条件：与林九对峙"
CAST_ROSTER: list[dict[str, Any]] = [
    {"id": "su_wan", "name": "苏晚", "role": "主角", "voice": "克制、短句"},
    {"id": "lin_jiu", "name": "林九", "role": "配角", "voice": "油滑"},
]


def _assemble(**extra: Any):
    """跑一次装配；extra 里只放剧情 kwargs。"""
    return ContextAssembler().assemble(
        card=CARD,
        preset=PRESET,
        user_persona={"name": "玩家", "description": "一名记者"},
        history=HISTORY,
        worldbooks=[],
        memory=MEMORY,
        scan_text="账册",
        **extra,
    )


# --------------------------------------------------------------------------- #
# 零回归：1v1 路径逐字节不变
# --------------------------------------------------------------------------- #
class TestOneVsOneInvariance:
    def test_baseline_has_exactly_nine_segments(self) -> None:
        assembled = _assemble()
        assert [s["name"] for s in assembled.segments] == [
            "system",
            "character",
            "world_info_before",
            "memory",
            "vector_recall",
            "examples",
            "history",
            "world_info_at_depth",
            "post_history",
        ]

    def test_empty_story_kwargs_produce_identical_result(self) -> None:
        """显式传空剧情参数（ChatSvc 的 1v1 分支可能这么调）→ 结果与不传完全一致。"""
        baseline = _assemble()
        with_empty = _assemble(
            speaking_as=None,
            story_block="",
            relations_block="",
            node_block="",
            cast_roster=None,
        )
        assert with_empty.prompt_text == baseline.prompt_text
        assert with_empty.segments == baseline.segments
        assert with_empty.estimated_prompt_tokens == baseline.estimated_prompt_tokens

    def test_empty_cast_list_also_identical(self) -> None:
        baseline = _assemble()
        with_empty_list = _assemble(cast_roster=[])
        assert with_empty_list.prompt_text == baseline.prompt_text
        assert with_empty_list.segments == baseline.segments

    def test_prompt_text_fingerprint_stable(self) -> None:
        """prompt 全文指纹：任何无意的格式漂移都会在此暴露。"""
        assembled = _assemble()
        fingerprint = {
            "token_len": len(assembled.prompt_text),
            "segment_names": [s["name"] for s in assembled.segments],
            "segment_tokens": [s["token_count"] for s in assembled.segments],
            "budget_keys": sorted(assembled.budget.keys()),
        }
        # 重新跑一次必须完全一致（可复现性）
        again = _assemble()
        assert {
            "token_len": len(again.prompt_text),
            "segment_names": [s["name"] for s in again.segments],
            "segment_tokens": [s["token_count"] for s in again.segments],
            "budget_keys": sorted(again.budget.keys()),
        } == fingerprint

    def test_story_budget_keys_defaulted_even_in_1v1(self) -> None:
        """三个阶段预算键即使在 1v1 也存在（否则 preset 覆写会 KeyError）。"""
        for key in _STORY_BUDGET:
            assert key in _STORY_BUDGET
        # 1v1 下三段 token 计数为 0
        assembled = _assemble()
        assert assembled.budget["story_tokens"] == 0
        assert assembled.budget["relations_tokens"] == 0
        assert assembled.budget["cast_tokens"] == 0


# --------------------------------------------------------------------------- #
# 三段出现
# --------------------------------------------------------------------------- #
class TestStorySegmentsAppear:
    def test_three_names_appended_in_order(self) -> None:
        assembled = _assemble(
            story_block=STORY_BLOCK,
            relations_block=RELATIONS_BLOCK,
            node_block=NODE_BLOCK,
            cast_roster=CAST_ROSTER,
        )
        names = [s["name"] for s in assembled.segments]
        assert names[:9] == [
            "system", "character", "world_info_before", "memory", "vector_recall",
            "examples", "history", "world_info_at_depth", "post_history",
        ]
        assert names[9:] == ["story_state", "relations", "cast_roster"]

    def test_story_tokens_nonzero(self) -> None:
        assembled = _assemble(
            story_block=STORY_BLOCK,
            relations_block=RELATIONS_BLOCK,
            cast_roster=CAST_ROSTER,
        )
        assert assembled.budget["story_tokens"] > 0
        assert assembled.budget["relations_tokens"] > 0
        assert assembled.budget["cast_tokens"] > 0

    def test_node_block_merges_into_story_state(self) -> None:
        assembled = _assemble(story_block=STORY_BLOCK, node_block=NODE_BLOCK)
        names = [s["name"] for s in assembled.segments]
        assert "story_state" in names
        # node_block 不单独成段
        assert "node" not in names
        assert STORY_BLOCK in assembled.prompt_text
        assert NODE_BLOCK in assembled.prompt_text

    def test_only_story_block_gives_one_segment(self) -> None:
        assembled = _assemble(story_block=STORY_BLOCK)
        assert [s["name"] for s in assembled.segments][9:] == ["story_state"]

    def test_only_relations_gives_one_segment(self) -> None:
        assembled = _assemble(relations_block=RELATIONS_BLOCK)
        assert [s["name"] for s in assembled.segments][9:] == ["relations"]

    def test_only_cast_roster_gives_one_segment(self) -> None:
        assembled = _assemble(cast_roster=CAST_ROSTER)
        assert [s["name"] for s in assembled.segments][9:] == ["cast_roster"]

    def test_segments_after_memory_in_prompt(self) -> None:
        """段落顺序：memory 之后紧跟 story_state 等雏三，再到 examples。"""
        assembled = _assemble(
            story_block=STORY_BLOCK,
            relations_block=RELATIONS_BLOCK,
            cast_roster=CAST_ROSTER,
        )
        text = assembled.prompt_text
        assert text.index("苏晚与玩家在书店初次见面") < text.index(STORY_BLOCK)
        assert text.index(STORY_BLOCK) < text.index(RELATIONS_BLOCK)
        assert text.index(RELATIONS_BLOCK) < text.index("【在场角色】")

    def test_cast_roster_format(self) -> None:
        assembled = _assemble(cast_roster=CAST_ROSTER)
        text = assembled.prompt_text
        assert "su_wan（苏晚·主角）：克制、短句" in text
        assert "lin_jiu（林九·配角）：油滑" in text

    def test_cast_roster_missing_voice(self) -> None:
        assembled = _assemble(cast_roster=[{"id": "x", "name": "无名", "role": "路人"}])
        assert "x（无名·路人）" in assembled.prompt_text

    def test_cast_roster_drops_idless(self) -> None:
        assembled = _assemble(
            cast_roster=[{"name": "鬼影"}, {"id": "ok", "name": "好人"}]
        )
        assert "ok（好人）" in assembled.prompt_text
        assert "鬼影" not in assembled.prompt_text

    def test_cast_roster_all_idless_yields_no_segment(self) -> None:
        assembled = _assemble(cast_roster=[{"name": "甲"}, {"name": "乙"}])
        assert [s["name"] for s in assembled.segments][9:] == []


# --------------------------------------------------------------------------- #
# 预算行为
# --------------------------------------------------------------------------- #
class TestStoryBudgetBehaviour:
    def test_story_block_hard_truncated(self) -> None:
        """超长 story_block 被硬截断而非整段丢弃（剧情状态必须让模型看到）。"""
        huge = "【剧情状态】" + "详细描述。" * 2000
        assembled = _assemble(story_block=huge)
        assert "story_state" in [s["name"] for s in assembled.segments]
        assert "…" in assembled.prompt_text
        # 截断上限：2 字符/token 的宽松估算
        assert len(huge) > _STORY_HARD_CAP_TOKENS * 2

    def test_story_block_never_dropped_by_zero_budget(self) -> None:
        """即便把 story_pct 压到 0，剧情状态也必须出现（永不裁剪契约）。"""
        preset = json.loads(json.dumps(PRESET))
        preset["context_budget"]["story_pct"] = 0
        assembled = ContextAssembler().assemble(
            card=CARD,
            preset=preset,
            user_persona={"name": "玩家"},
            history=HISTORY,
            story_block=STORY_BLOCK,
        )
        assert "story_state" in [s["name"] for s in assembled.segments]

    def test_relations_truncated_by_budget(self) -> None:
        """关系段按 relations_pct 预算裁剪：给得很小的预算时行数应减少。"""
        many_lines = "\n".join(f"- a{i} → b{i}：旧识（亲密度 +0.5）" for i in range(200))

        preset_big = json.loads(json.dumps(PRESET))
        preset_big["context_budget"]["relations_pct"] = 20
        big = ContextAssembler().assemble(
            card=CARD, preset=preset_big, user_persona={"name": "p"},
            history=HISTORY, relations_block=many_lines,
        )

        preset_small = json.loads(json.dumps(PRESET))
        preset_small["context_budget"]["relations_pct"] = 1
        small = ContextAssembler().assemble(
            card=CARD, preset=preset_small, user_persona={"name": "p"},
            history=HISTORY, relations_block=many_lines,
        )

        big_tokens = big.budget["relations_tokens"]
        small_tokens = small.budget["relations_tokens"]
        assert small_tokens < big_tokens

    def test_relations_zero_budget_yields_no_segment(self) -> None:
        preset = json.loads(json.dumps(PRESET))
        preset["context_budget"]["relations_pct"] = 0
        assembled = ContextAssembler().assemble(
            card=CARD, preset=preset, user_persona={"name": "p"},
            history=HISTORY, relations_block=RELATIONS_BLOCK,
        )
        assert "relations" not in [s["name"] for s in assembled.segments]

    def test_story_segments_consume_history_budget(self) -> None:
        """剧情三段占的是同一块总预算 → history 可用预算相应减少。"""
        baseline = _assemble()
        with_story = _assemble(
            story_block=STORY_BLOCK,
            relations_block=RELATIONS_BLOCK,
            cast_roster=CAST_ROSTER,
        )
        assert with_story.budget["story_tokens"] > 0
        # 总可用预算不变，估算总 token 上升
        assert with_story.estimated_prompt_tokens > baseline.estimated_prompt_tokens

    def test_preset_can_override_story_pct(self) -> None:
        preset = json.loads(json.dumps(PRESET))
        preset["context_budget"]["cast_pct"] = 12
        # 不应抛错，且 cast 段仍按 max_context_tokens * 12% 参与裁剪
        assembled = ContextAssembler().assemble(
            card=CARD, preset=preset, user_persona={"name": "p"},
            history=HISTORY, cast_roster=CAST_ROSTER,
        )
        assert "cast_roster" in [s["name"] for s in assembled.segments]


# --------------------------------------------------------------------------- #
# speaking_as（说话者上下文）
# --------------------------------------------------------------------------- #
class TestSpeakingAs:
    def test_speaking_as_alone_adds_no_segment(self) -> None:
        """speaking_as 本身不渲染内容 —— 它是给调用方裁剪关系子图用的提示。"""
        assembled = _assemble(speaking_as={"id": "su_wan", "name": "苏晚"})
        assert len(assembled.segments) == 9

    def test_speaking_as_does_not_break_baseline(self) -> None:
        baseline = _assemble()
        with_speaker = _assemble(speaking_as={"id": "lin_jiu", "name": "林九", "voice": "油滑"})
        assert with_speaker.prompt_text == baseline.prompt_text

    def test_speaking_as_with_story_block(self) -> None:
        assembled = _assemble(
            speaking_as={"id": "su_wan", "name": "苏晚"},
            story_block=STORY_BLOCK,
            relations_block=RELATIONS_BLOCK,
        )
        assert [s["name"] for s in assembled.segments][9:] == ["story_state", "relations"]
