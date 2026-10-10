"""运行时 M1 纯逻辑单测（不依赖数据库）。

覆盖：
  - SessionSvc 的状态迁移表（会话外壳 + 单轮状态机）与乐观锁判定
  - 配置密钥脱敏 mask_secret
  - ContextAssembler 的组装顺序、占位符替换、预算裁剪、世界书三态复用
  - MemorySvc 的正则事实抽取 / 合并 / 触发判定
"""

from __future__ import annotations

from app.core.errors import ConflictError
from app.services.config import has_secret_placeholder, mask_secret
from app.services.context_assembler import ContextAssembler
from app.services.memory import MemorySvc
from app.services.session import (
    SESSION_STATUS_TRANSITIONS,
    STATE_MACHINE_TRANSITIONS,
    SessionSvc,
)


# --------------------------------------------------------------------------- #
# 密钥脱敏
# --------------------------------------------------------------------------- #
def test_mask_secret_keeps_edges() -> None:
    assert mask_secret("sk-abcdefghijkl") == "sk-***jkl"
    assert mask_secret("short") == "***"
    assert mask_secret("") == ""
    assert mask_secret(None) == ""


def test_secret_placeholder_detection() -> None:
    assert has_secret_placeholder("sk-***xyz") is True
    assert has_secret_placeholder("sk-realvalue") is False
    assert has_secret_placeholder("") is False


# --------------------------------------------------------------------------- #
# 状态迁移表
# --------------------------------------------------------------------------- #
def test_session_status_transitions_valid() -> None:
    SessionSvc.assert_session_transition("active", "paused")
    SessionSvc.assert_session_transition("active", "archived")
    SessionSvc.assert_session_transition("archived", "active")


def test_session_status_transition_invalid_raises() -> None:
    import pytest

    from app.core.errors import BadRequestError

    # archived 不能直接到 paused
    with pytest.raises(ConflictError):
        SessionSvc.assert_session_transition("archived", "paused")
    # 同态迁移是无操作，允许通过（不抛错）
    SessionSvc.assert_session_transition("active", "active")
    # 未知目标状态 -> 400
    with pytest.raises(BadRequestError):
        SessionSvc.assert_session_transition("active", "generating")


def test_transition_tables_cover_all_states() -> None:
    # 会话外壳：三态都有出边
    assert set(SESSION_STATUS_TRANSITIONS) == {"active", "paused", "archived"}
    # 单轮状态机：仅 idle 是入口，其余均可回 idle（interrupted/error 经 reset/regenerate）
    assert STATE_MACHINE_TRANSITIONS["idle"] == frozenset({"assembling"})
    assert "idle" in STATE_MACHINE_TRANSITIONS["interrupted"]
    assert "idle" in STATE_MACHINE_TRANSITIONS["error"]
    assert "idle" in STATE_MACHINE_TRANSITIONS["post_processing"]


def test_transition_state_updates_version() -> None:
    svc = SessionSvc(db=None)  # 不触碰 db：仅测纯状态迁移

    class _Row:
        state_machine: dict = {"current": "idle", "turn": 0, "version": 3, "last_error": None}

    row = _Row()
    svc.transition_state(row, "assembling")
    assert row.state_machine["current"] == "assembling"
    assert row.state_machine["version"] == 4


def test_transition_state_illegal_raises() -> None:
    import pytest

    svc = SessionSvc(db=None)

    class _Row:
        state_machine: dict = {"current": "idle", "turn": 0, "version": 0, "last_error": None}

    with pytest.raises(ConflictError):
        svc.transition_state(_Row(), "generating")  # idle 不能直接到 generating


# --------------------------------------------------------------------------- #
# ContextAssembler
# --------------------------------------------------------------------------- #
_CARD = {
    "name": "林晓",
    "description": "在城市里开着一家旧书店",
    "personality": "寡言而温和",
    "scenario": "梅雨季的午后",
    "first_mes": "推门时风铃轻响。",
    "mes_example": "{{char}}：今天想找哪本书？",
    "post_history_instructions": "保持第一人称叙述。",
}
_PRESET = {
    "prompt_template": {
        "system": "你是 {{char}}，与 {{user}} 对话。\n设定：{{description}}\n{{world_info}}",
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


def _worldbook() -> dict:
    return {
        "name": "城南",
        "scan_depth": 4,
        "token_budget": 512,
        "entries": [
            {
                "id": "e1",
                "keys": ["怀表"],
                "content": "旧怀表停在三点十七分。",
                "enabled": True,
                "priority": 10,
                "position": "before_char",
                "insertion_order": 100,
            },
            {
                "id": "e2",
                "keys": ["永远不会命中"],
                "content": "不该出现的内容。",
                "enabled": True,
                "priority": 10,
                "position": "before_char",
                "insertion_order": 100,
            },
        ],
    }


def test_assembler_replaces_placeholders_and_world_info() -> None:
    asm = ContextAssembler()
    result = asm.assemble(
        card=_CARD,
        preset=_PRESET,
        user_persona={"name": "阿明", "description": "常客"},
        history=[{"role": "user", "content": "我看到那块怀表了"}],
        worldbooks=[_worldbook()],
        memory={},
    )
    system = result.messages[0].content
    assert "林晓" in system
    assert "阿明" in system
    assert "旧怀表停在三点十七分。" in system
    assert "不该出现的内容。" not in system
    # 命中的世界书条目进 trace 且 in_budget
    hit = [d for d in result.world_info_trace if d["entry_id"] == "e1"][0]
    assert hit["matched"] is True and hit["in_budget"] is True


def test_assembler_unknown_placeholder_preserved_with_warning() -> None:
    preset = {
        "prompt_template": {"system": "未知 {{nope}} 占位符", "instruction": ""},
        "context_budget": {"max_context_tokens": 4096, "reserve_for_output": 512},
    }
    result = ContextAssembler().assemble(
        card=_CARD, preset=preset, user_persona={}, history=[], worldbooks=[], memory={}
    )
    assert "{{nope}}" in result.messages[0].content
    assert any("nope" in w for w in result.warnings)


def test_assembler_trims_history_by_budget() -> None:
    small_preset = {
        **_PRESET,
        "context_budget": {"max_context_tokens": 1024, "reserve_for_output": 256},
    }
    history = [{"role": "user", "content": "很长的一段话" * 50} for _ in range(20)]
    result = ContextAssembler().assemble(
        card=_CARD, preset=small_preset, user_persona={}, history=history, worldbooks=[], memory={}
    )
    assert result.budget["dropped_messages"] > 0
    # 永不裁剪：系统基座与角色定义段仍然存在
    assert result.messages[0].role == "system"
    assert "林晓" in result.messages[0].content


def test_assembler_history_order_oldest_to_newest() -> None:
    history = [
        {"role": "user", "content": "第一句"},
        {"role": "assistant", "content": "第二句"},
        {"role": "user", "content": "第三句"},
    ]
    result = ContextAssembler().assemble(
        card=_CARD, preset=_PRESET, user_persona={}, history=history, worldbooks=[], memory={}
    )
    contents = [m.content for m in result.messages]
    assert contents.index("第一句") < contents.index("第三句")


def test_assembler_memory_block_included() -> None:
    memory = {
        "rolling_summary": "两人初次相遇。",
        "facts": [{"key": "玩家姓名", "value": "阿明", "confidence": 0.9}],
    }
    result = ContextAssembler().assemble(
        card=_CARD, preset=_PRESET, user_persona={}, history=[], worldbooks=[], memory=memory
    )
    blob = "\n".join(m.content for m in result.messages)
    assert "两人初次相遇。" in blob
    assert "玩家姓名=阿明" in blob


# --------------------------------------------------------------------------- #
# MemorySvc
# --------------------------------------------------------------------------- #
def test_memory_extract_facts_regex() -> None:
    messages = [
        {"id": "m1", "role": "user", "content": "我叫林晓，今年二十七岁"},
        {"id": "m2", "role": "assistant", "content": "我叫别的，不该被抽取"},
        {"id": "m3", "role": "user", "content": "我拿到了那块旧怀表"},
    ]
    facts = MemorySvc.extract_facts(messages)
    by_key = {f["key"]: f["value"] for f in facts}
    assert by_key.get("玩家姓名") == "林晓"
    assert "怀表" in by_key.get("获得物品", "")
    # assistant 消息不参与抽取
    assert all(f.get("source_message_id") != "m2" for f in facts)


def test_memory_merge_facts_dedup_by_key() -> None:
    existing = [{"key": "玩家姓名", "value": "阿明", "confidence": 0.4}]
    incoming = [{"key": "玩家姓名", "value": "林晓", "confidence": 0.6}]
    merged = MemorySvc.merge_facts(existing, incoming)
    assert len(merged) == 1
    assert merged[0]["value"] == "林晓"
    assert merged[0]["confidence"] == 0.6


def test_memory_should_summarize_threshold() -> None:
    messages = [{"id": "m1", "role": "user", "content": "x" * 400}]
    # 未摘要历史 token 远超历史上限的 80%
    assert MemorySvc.should_summarize(
        messages, summary_upto_message_id=None, history_budget=100
    )
    # 零预算不触发（防除零/误触）
    assert not MemorySvc.should_summarize(
        messages, summary_upto_message_id=None, history_budget=0
    )


def test_memory_should_summarize_respects_cursor() -> None:
    messages = [
        {"id": "m1", "role": "user", "content": "y" * 400},
        {"id": "m2", "role": "user", "content": "z"},
    ]
    # 已摘要到 m1，则只有 m2 计入，不应触发
    assert not MemorySvc.should_summarize(
        messages, summary_upto_message_id="m1", history_budget=100
    )


def test_memory_build_block_sorts_by_confidence() -> None:
    block = MemorySvc.build_block(
        {
            "rolling_summary": "摘要",
            "facts": [
                {"key": "a", "value": "1", "confidence": 0.2},
                {"key": "b", "value": "2", "confidence": 0.9},
            ],
        }
    )
    assert [f["key"] for f in block.facts] == ["b", "a"]
    assert "摘要" in block.render()
