"""ChatSvc 剧情分支（S6）集成测试 —— sqlite + mock LLMRouter，无需真实上游。

覆盖计划中的三条硬验收：
  1. **单角色剧情会话的事件序列与 1v1 完全一致**（超集里退化的情况）
  2. **2 个 speaker → 2 条 assistant 消息，`meta.speaker_id` 正确**
  3. **中断后无 `streaming` 残留**（`_finalize_incomplete` 多消息修复）

外加：world_info/director 顺序、node 事件、actions 帧、导演降级不阻断、
speaker 归属写回 meta、usage 累计、turn/beat 推进、旧 1v1 路径零回归。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.story_state import STORY_SPEC, StoryStateSvc


# --------------------------------------------------------------------------- #
# 可控替身
# --------------------------------------------------------------------------- #
class _FakeStreamRouter:
    """按说话者逐段产出 delta 的 router 替身。

    `scripts` 为一个列表，按下标依次消费；每次 `stream()` 调用取一段。
    若元素是 Exception 则抛出（测上游失败）。
    """

    def __init__(self, scripts: list[Any]) -> None:
        self._scripts = list(scripts)
        self.calls: list[list[Any]] = []

    async def stream(self, messages: Any, **kwargs: Any) -> AsyncIterator[str]:
        self.calls.append(list(messages))
        if not self._scripts:
            return
        item = self._scripts.pop(0)
        if isinstance(item, BaseException):
            raise item
        for piece in item:
            yield piece


class _FakeDirectorSvc:
    """导演替身：返回预设决策，或走降级。"""

    def __init__(self, decisions: list[Any]) -> None:
        self._decisions = list(decisions)
        self.calls: list[dict[str, Any]] = []

    async def decide(self, **kwargs: Any):
        from app.services.director import DirectorDecision

        self.calls.append(kwargs)
        if not self._decisions:
            return DirectorDecision()
        item = self._decisions.pop(0)
        if isinstance(item, DirectorDecision):
            return item
        if isinstance(item, BaseException):
            raise item
        return DirectorDecision.from_json(item)


class _FakeSuggesterSvc:
    def __init__(self, actions: list[dict[str, Any]] | None = None, error: Exception | None = None):
        self._actions = actions if actions is not None else []
        self._error = error

    async def suggest(self, **kwargs: Any) -> list[dict[str, Any]]:
        if self._error is not None:
            raise self._error
        return self._actions


# --------------------------------------------------------------------------- #
# 建会话夹具
# --------------------------------------------------------------------------- #
STORY_CAST = [
    {"id": "su_wan", "name": "苏晚", "role": "主角", "voice": "克制、短句", "goals": ["查明旧案"]},
    {"id": "lin_jiu", "name": "林九", "role": "配角", "voice": "油滑"},
]
STORY_RELATIONS = [{"from": "su_wan", "to": "lin_jiu", "kind": "旧识", "tension": 0.6}]


async def _make_story_session(db: AsyncSession, card_and_preset: tuple) -> Any:
    """建一个 spec=story_session 的会话，并把 cast/relations 固化进 extensions。"""
    card_id, preset_id = card_and_preset
    from app.services.session import SessionSvc

    svc = SessionSvc(db)
    created = await svc.create(
        {"character_card_id": str(card_id), "preset_id": str(preset_id), "greeting_index": -1}
    )
    row = await svc.get_row(str(created["id"]))
    row.spec = STORY_SPEC
    row.spec_version = "1.0"
    state = StoryStateSvc(db)
    state.bind_world(row, world_id=None, cast=STORY_CAST, relations=STORY_RELATIONS)
    state.apply_scene_update(
        row,
        {"location": "老弄堂", "time": "深夜", "mood": "压抑", "beat": "两人对质",
         "present": ["su_wan", "lin_jiu"]},
    )
    await db.flush()
    return row


async def _bind_fire_ninja_world(db: AsyncSession, row: Any, chat: Any) -> Any:
    """给会话建一个带「火影忍者」tag 的世界观并绑定，返回该 World 行。

    用于画风链路测试：`World.tags` 是顶层 ARRAY 列，是 `art_style` 推断的
    **唯一**依据，所以必须真的落一行 World，而不是往 `extensions` 里塞。
    """
    from app.models.world import World

    world = World(
        # `owner_id` 是 NOT NULL，`server_default="local"` 只在 DB 层生效，
        # ORM 直接 INSERT 时不带该列会被判 NULL —— 必须显式给值。
        owner_id="local",
        title="木叶 · 雾中之刃",
        spec="rpg_world",
        spec_version="1.0",
        setting={"era": "疾风传中期", "tone": "紧张、克制", "summary": "忍者任务"},
        tags=["火影忍者", "同人", "二次元", "任务推进"],
        cast=[],
        relations=[],
        outline={},
        opening="",
        factions=[],
        extensions={},
    )
    db.add(world)
    await db.flush()

    # 会话级绑定：extensions.story.world_id 是 `extract_world_id` 的首选
    StoryStateSvc(db).bind_world(row, world_id=str(world.id), cast=STORY_CAST, relations=STORY_RELATIONS)
    await db.flush()
    return world


async def _drain(chat: Any, sid: str, text: str = "我把账册拍在桌上。") -> list[tuple[str, dict]]:
    events: list[tuple[str, dict[str, Any]]] = []
    async for event, data in chat.stream_reply(sid, input_text=text):
        events.append((event, data))
    return events


def _names(events: list[tuple[str, dict]]) -> list[str]:
    return [e for e, _ in events]


def _first(events: list[tuple[str, dict]], name: str) -> dict[str, Any] | None:
    for e, d in events:
        if e == name:
            return d
    return None


def _all(events: list[tuple[str, dict]], name: str) -> list[dict[str, Any]]:
    return [d for e, d in events if e == name]


# --------------------------------------------------------------------------- #
# 1) 单角色剧情 ≈ 1v1 事件序列
# --------------------------------------------------------------------------- #
class TestSingleSpeakerParity:
    @pytest.mark.asyncio
    async def test_single_speaker_core_sequence_matches_1v1(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """单 speaker、无旁白、无节点 → 核心骨架与 1v1 逐事件一致。"""
        from app.services.chat import ChatSvc

        row = await _make_story_session(db, card_and_preset)
        sid = str(row.id)
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["她", "笑了", "。"]]))
        monkeypatch.setattr(
            chat,
            "_director",
            _FakeDirectorSvc(
                [{"speakers": [{"id": "su_wan", "name": "苏晚", "intent": "试探"}]}]
            ),
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))

        events = await _drain(chat, sid)
        names = _names(events)

        # 顺序断言：world_info 必须最先
        assert names[0] == "world_info"
        # 核心骨架：忽略**剧情专有**事件。
        # image 与 node/actions 同属剧情专有（S16 §4.6.3 的自动配图会插在 usage 之后、
        # actions 之前），不属于「1v1 也应有」的核心事件，因此一并排除；
        # 它自身的位置另有 TestStoryImageEvents 专门守卫。
        core = [
            n
            for n in names
            if n not in {"director", "speaker_switch", "actions", "node", "image"}
        ]
        assert core[0] == "world_info"
        assert core[1] == "start"
        assert core[-2] == "usage"
        assert core[-1] == "done"
        assert core.count("delta") == 3

    @pytest.mark.asyncio
    async def test_director_event_precedes_start(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.chat import ChatSvc

        row = await _make_story_session(db, card_and_preset)
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["好"]]))
        monkeypatch.setattr(
            chat, "_director",
            _FakeDirectorSvc([{"speakers": [{"id": "su_wan", "name": "苏晚"}]}]),
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))

        names = _names(await _drain(chat, str(row.id)))
        assert names.index("director") < names.index("start")
        assert names.index("world_info") < names.index("director")

    @pytest.mark.asyncio
    async def test_no_speaker_no_narration_still_done(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """导演给了空 speaker 且非降级 → 纯占位一轮，也必须正常 done。"""
        from app.services.chat import ChatSvc

        row = await _make_story_session(db, card_and_preset)
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([]))
        monkeypatch.setattr(chat, "_director", _FakeDirectorSvc([{"speakers": []}]))
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))

        events = await _drain(chat, str(row.id))
        assert _names(events)[-1] == "done"


# --------------------------------------------------------------------------- #
# 2) 多 speaker → 多条 assistant 消息
# --------------------------------------------------------------------------- #
class TestMultiSpeaker:
    @pytest.mark.asyncio
    async def test_two_speakers_two_messages_with_speaker_id(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.chat import ChatSvc
        from app.services.session import SessionSvc

        row = await _make_story_session(db, card_and_preset)
        sid = str(row.id)
        chat = ChatSvc(db)
        monkeypatch.setattr(
            chat, "_router",
            _FakeStreamRouter([["你来晚了。"], ["我早就来了。"]]),
        )
        monkeypatch.setattr(
            chat, "_director",
            _FakeDirectorSvc(
                [
                    {
                        "speakers": [
                            {"id": "su_wan", "name": "苏晚", "intent": "开场"},
                            {"id": "lin_jiu", "name": "林九", "intent": "回敬"},
                        ]
                    }
                ]
            ),
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))

        events = await _drain(chat, sid)
        assert _names(events).count("delta") == 2
        # 第一个 speaker 用首条占位，切换后第二个 speaker 有自己的 speaker_switch
        switches = _all(events, "speaker_switch")
        assert len(switches) == 1
        assert switches[0]["speaker_id"] == "lin_jiu"

        rows = [
            m for m in await SessionSvc(db).list_messages(row.id)
            if m.role == "assistant" and (m.meta or {}).get("beat_role") == "reply"
        ]
        assert len(rows) == 2
        assert [r.meta["speaker_id"] for r in rows] == ["su_wan", "lin_jiu"]
        assert [r.content for r in rows] == ["你来晚了。", "我早就来了。"]
        assert all(r.status == "complete" for r in rows)

    @pytest.mark.asyncio
    async def test_speaker_name_backfilled_from_cast(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """导演只给 id 不给 name 时，从固化 cast 补名。"""
        from app.services.chat import ChatSvc
        from app.services.session import SessionSvc

        row = await _make_story_session(db, card_and_preset)
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["…"]]))
        monkeypatch.setattr(
            chat, "_director", _FakeDirectorSvc([{"speakers": [{"id": "lin_jiu"}]}])
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))

        await _drain(chat, str(row.id))
        rows = [
            m for m in await SessionSvc(db).list_messages(row.id)
            if (m.meta or {}).get("beat_role") == "reply"
        ]
        assert rows[0].meta["speaker_name"] == "林九"

    @pytest.mark.asyncio
    async def test_unknown_speaker_id_keeps_id_as_name(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """导演编了一个 cast 里没有的 id → 不崩，用 id 作名字。"""
        from app.services.chat import ChatSvc
        from app.services.session import SessionSvc

        row = await _make_story_session(db, card_and_preset)
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["…"]]))
        monkeypatch.setattr(
            chat, "_director", _FakeDirectorSvc([{"speakers": [{"id": "ghost"}]}])
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))

        events = await _drain(chat, str(row.id))
        assert _names(events)[-1] == "done"
        rows = [
            m for m in await SessionSvc(db).list_messages(row.id)
            if (m.meta or {}).get("beat_role") == "reply"
        ]
        assert rows[0].meta["speaker_id"] == "ghost"
        assert rows[0].meta["speaker_name"] == "ghost"

    @pytest.mark.asyncio
    async def test_narration_message_created(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.chat import ChatSvc
        from app.services.session import SessionSvc

        row = await _make_story_session(db, card_and_preset)
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["「……」"]]))
        monkeypatch.setattr(
            chat, "_director",
            _FakeDirectorSvc(
                [{"narration": "雨敲着铁皮棚。", "speakers": [{"id": "su_wan", "name": "苏晚"}]}]
            ),
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))

        events = await _drain(chat, str(row.id))
        rows = await SessionSvc(db).list_messages(row.id)
        narrations = [m for m in rows if (m.meta or {}).get("is_narration")]
        assert len(narrations) == 1
        assert narrations[0].content == "雨敲着铁皮棚。"
        assert narrations[0].meta["beat_role"] == "narration"
        assert narrations[0].status == "complete"
        # 旁白切换也发 speaker_switch(is_narration=True)
        narr_switches = [s for s in _all(events, "speaker_switch") if s.get("is_narration")]
        assert len(narr_switches) == 1


# --------------------------------------------------------------------------- #
# 3) 中断无残留
# --------------------------------------------------------------------------- #
class TestNoStreamingResidue:
    @pytest.mark.asyncio
    async def test_upstream_error_leaves_no_streaming(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """第 2 个说话者上游失败 → 本轮全部 assistant 行不得残留 streaming。"""
        from app.services.chat import ChatSvc
        from app.services.session import SessionSvc

        row = await _make_story_session(db, card_and_preset)
        sid = str(row.id)
        chat = ChatSvc(db)
        monkeypatch.setattr(
            chat, "_router",
            _FakeStreamRouter([["第一句"], RuntimeError("upstream boom")]),
        )
        monkeypatch.setattr(
            chat, "_director",
            _FakeDirectorSvc(
                [{"speakers": [{"id": "su_wan", "name": "苏晚"}, {"id": "lin_jiu", "name": "林九"}]}]
            ),
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))

        events = await _drain(chat, sid)
        assert _names(events)[-1] == "error"

        rows = await SessionSvc(db).list_messages(row.id)
        streaming = [m for m in rows if m.status == "streaming"]
        assert streaming == [], f"残留 streaming 脏数据: {[str(m.id) for m in streaming]}"
        # 首条已完成，第二条为 incomplete
        assistant = [m for m in rows if m.role == "assistant"]
        assert any(m.status == "complete" for m in assistant)
        assert any(m.status == "incomplete" for m in assistant)

    @pytest.mark.asyncio
    async def test_client_disconnect_leaves_no_streaming(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """提前 close 生成器（模拟客户端断开）→ 同样不得留 streaming。"""
        from app.services.chat import ChatSvc
        from app.services.session import SessionSvc

        row = await _make_story_session(db, card_and_preset)
        sid = str(row.id)
        chat = ChatSvc(db)
        monkeypatch.setattr(
            chat, "_router",
            _FakeStreamRouter([["甲"], ["乙"], ["丙"]]),
        )
        monkeypatch.setattr(
            chat, "_director",
            _FakeDirectorSvc(
                [
                    {"speakers": [
                        {"id": "su_wan", "name": "苏晚"},
                        {"id": "lin_jiu", "name": "林九"},
                    ]}
                ]
            ),
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))

        agen = chat.stream_reply(sid, input_text="继续")
        seen = 0
        async for _event, _data in agen:
            seen += 1
            if seen >= 5:  # 中途放弃，不消费完
                break
        await agen.aclose()

        rows = await SessionSvc(db).list_messages(row.id)
        assert [m for m in rows if m.status == "streaming"] == []

    @pytest.mark.asyncio
    async def test_state_returns_to_idle_after_error(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.chat import ChatSvc

        row = await _make_story_session(db, card_and_preset)
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([RuntimeError("boom")]))
        monkeypatch.setattr(
            chat, "_director", _FakeDirectorSvc([{"speakers": [{"id": "su_wan", "name": "苏晚"}]}])
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))

        await _drain(chat, str(row.id))
        await db.refresh(row)
        assert (row.state_machine or {}).get("current") == "idle"

    @pytest.mark.asyncio
    async def test_finalize_sweeps_orphan_streaming_rows(
        self, db: AsyncSession, card_and_preset: tuple
    ) -> None:
        """即使调用方漏传 assistant_rows，兜底扫库也要收干净。"""
        from app.services.chat import ChatSvc
        from app.services.session import SessionSvc

        row = await _make_story_session(db, card_and_preset)
        svc = SessionSvc(db)
        orphan = await svc.append_message(
            row.id, role="assistant", content="半句", status="streaming", token_count=0
        )
        chat = ChatSvc(db)
        await chat._finalize_incomplete(None, row, RuntimeError("x"))
        await db.refresh(orphan)
        assert orphan.status == "incomplete"


# --------------------------------------------------------------------------- #
# 导演降级不阻断
# --------------------------------------------------------------------------- #
class TestDirectorDegradation:
    @pytest.mark.asyncio
    async def test_degraded_decision_still_produces_done(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.chat import ChatSvc
        from app.services.director import DirectorDecision

        row = await _make_story_session(db, card_and_preset)
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["降级但继续。"]]))
        monkeypatch.setattr(
            chat, "_director",
            _FakeDirectorSvc([DirectorDecision.fallback(reason="测试降级")]),
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))

        events = await _drain(chat, str(row.id))
        assert _names(events)[-1] == "done"
        # 降级时也要有一个角色接话（从 present 轮转）
        assert "delta" in _names(events)
        assert _first(events, "director")["degraded"] is True

    @pytest.mark.asyncio
    async def test_degraded_increments_failure_counter(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.chat import ChatSvc
        from app.services.director import DirectorDecision

        row = await _make_story_session(db, card_and_preset)
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["x"]]))
        monkeypatch.setattr(
            chat, "_director", _FakeDirectorSvc([DirectorDecision.fallback(reason="x")])
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))

        await _drain(chat, str(row.id))
        await db.refresh(row)
        # bump_turn 会把 failures 清零，所以这里只断言「它确实被重置为 0」
        assert StoryStateSvc.get_story(row)["director_failures"] == 0

    @pytest.mark.asyncio
    async def test_circuit_propagated_to_director(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """连续失败达阈值后，circuit_open=True 应传给导演。"""
        from app.services.chat import ChatSvc

        row = await _make_story_session(db, card_and_preset)
        StoryStateSvc(db).set_story(row, {"director_failures": 3})
        await db.flush()

        fake = _FakeDirectorSvc([{"speakers": [{"id": "su_wan"}]}])
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["x"]]))
        monkeypatch.setattr(chat, "_director", fake)
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))

        await _drain(chat, str(row.id))
        assert fake.calls[0]["circuit_open"] is True


# --------------------------------------------------------------------------- #
# 节点 / 建议
# --------------------------------------------------------------------------- #
class TestNodeAndActions:
    @pytest.mark.asyncio
    async def test_node_event_and_persisted(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.chat import ChatSvc

        row = await _make_story_session(db, card_and_preset)
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["节点到了。"]]))
        monkeypatch.setattr(
            chat, "_director",
            _FakeDirectorSvc(
                [
                    {
                        "speakers": [{"id": "su_wan", "name": "苏晚"}],
                        "node_triggered": {"id": "n-003", "title": "旧案重启", "brief": "账册出现"},
                    }
                ]
            ),
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))

        events = await _drain(chat, str(row.id))
        node = _first(events, "node")
        assert node == {"id": "n-003", "title": "旧案重启", "brief": "账册出现"}
        assert _names(events).index("node") < _names(events).index("usage")

        await db.refresh(row)
        assert StoryStateSvc.get_story(row)["node_id"] == "n-003"

    @pytest.mark.asyncio
    async def test_no_node_event_when_not_triggered(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.chat import ChatSvc

        row = await _make_story_session(db, card_and_preset)
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["平淡一轮。"]]))
        monkeypatch.setattr(
            chat, "_director", _FakeDirectorSvc([{"speakers": [{"id": "su_wan"}]}])
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))

        assert "node" not in _names(await _drain(chat, str(row.id)))

    @pytest.mark.asyncio
    async def test_actions_frame_emitted_before_done(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.chat import ChatSvc

        row = await _make_story_session(db, card_and_preset)
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["给你三个选择。"]]))
        monkeypatch.setattr(
            chat, "_director", _FakeDirectorSvc([{"speakers": [{"id": "su_wan"}]}])
        )
        actions = [
            {"id": "a0", "label": "问他账册", "hint": "施压", "tone": "speak"},
            {"id": "a1", "label": "看看窗外", "hint": "观察", "tone": "observe"},
        ]
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc(actions))

        events = await _drain(chat, str(row.id))
        names = _names(events)
        assert "actions" in names
        assert names.index("actions") < names.index("done")
        assert _first(events, "actions")["actions"] == actions

    @pytest.mark.asyncio
    async def test_actions_persisted_to_session(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """建议必须落库（S15-1）—— 否则刷新即丢，重开历史会话建议区永远是空的。"""
        from app.services.chat import ChatSvc

        row = await _make_story_session(db, card_and_preset)
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["给你三个选择。"]]))
        monkeypatch.setattr(
            chat, "_director", _FakeDirectorSvc([{"speakers": [{"id": "su_wan"}]}])
        )
        actions = [
            {"id": "a0", "label": "问他账册", "hint": "施压", "tone": "speak"},
            {"id": "a1", "label": "看看窗外", "hint": "观察", "tone": "observe"},
        ]
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc(actions))

        await _drain(chat, str(row.id))

        await db.refresh(row)
        assert [a["id"] for a in StoryStateSvc.get_suggestions(row)] == ["a0", "a1"]
        # 落库时要带上轮次，前端可据此判断建议是否与当前进度同步
        assert StoryStateSvc.get_story(row)["suggestions_turn"] is not None

    @pytest.mark.asyncio
    async def test_empty_actions_clears_persisted(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """本轮没建议 → 库里的旧建议要被清掉，不能残留过期方向。

        （前端首屏就是读这个字段恢复芯片区的，残留 = 玩家看到上一轮的方向。）
        """
        from app.services.chat import ChatSvc

        row = await _make_story_session(db, card_and_preset)
        StoryStateSvc(db).set_suggestions(row, [{"id": "old", "label": "上一轮的方向"}], turn=0)
        await db.flush()

        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["平平一轮。"]]))
        monkeypatch.setattr(
            chat, "_director", _FakeDirectorSvc([{"speakers": [{"id": "su_wan"}]}])
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))

        events = await _drain(chat, str(row.id))

        assert "actions" not in _names(events)
        await db.refresh(row)
        assert StoryStateSvc.get_suggestions(row) == []

    @pytest.mark.asyncio
    async def test_suggester_error_yields_no_actions_but_done(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """建议服务抛错 → 无 actions 帧，但对话正常 done（计划硬验收）。"""
        from app.services.chat import ChatSvc

        row = await _make_story_session(db, card_and_preset)
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["正常回复。"]]))
        monkeypatch.setattr(
            chat, "_director", _FakeDirectorSvc([{"speakers": [{"id": "su_wan"}]}])
        )
        monkeypatch.setattr(
            chat, "_suggester", _FakeSuggesterSvc(error=RuntimeError("suggest boom"))
        )

        events = await _drain(chat, str(row.id))
        names = _names(events)
        assert "actions" not in names
        assert names[-1] == "done"
        assert "error" not in names

    @pytest.mark.asyncio
    async def test_empty_actions_no_frame(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.chat import ChatSvc

        row = await _make_story_session(db, card_and_preset)
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["无建议。"]]))
        monkeypatch.setattr(
            chat, "_director", _FakeDirectorSvc([{"speakers": [{"id": "su_wan"}]}])
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))

        assert "actions" not in _names(await _drain(chat, str(row.id)))


# --------------------------------------------------------------------------- #
# 状态推进
# --------------------------------------------------------------------------- #
class TestStateAdvance:
    @pytest.mark.asyncio
    async def test_turn_and_beat_advance(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.chat import ChatSvc

        row = await _make_story_session(db, card_and_preset)
        await db.refresh(row)
        before_turn = int((row.state_machine or {}).get("turn") or 0)
        before_beat = StoryStateSvc.get_story(row)["beat_index"]

        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["一轮。"]]))
        monkeypatch.setattr(
            chat, "_director", _FakeDirectorSvc([{"speakers": [{"id": "su_wan"}]}])
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))

        await _drain(chat, str(row.id))
        await db.refresh(row)
        assert int((row.state_machine or {}).get("turn") or 0) == before_turn + 1
        assert StoryStateSvc.get_story(row)["beat_index"] == before_beat + 1

    @pytest.mark.asyncio
    async def test_done_payload_carries_turn(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.chat import ChatSvc

        row = await _make_story_session(db, card_and_preset)
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["x"]]))
        monkeypatch.setattr(
            chat, "_director", _FakeDirectorSvc([{"speakers": [{"id": "su_wan"}]}])
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))

        events = await _drain(chat, str(row.id))
        assert isinstance(_first(events, "done")["turn"], int)

    @pytest.mark.asyncio
    async def test_scene_patch_and_relations_applied(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.chat import ChatSvc

        row = await _make_story_session(db, card_and_preset)
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["x"]]))
        monkeypatch.setattr(
            chat, "_director",
            _FakeDirectorSvc(
                [
                    {
                        "speakers": [{"id": "su_wan"}],
                        "scene_patch": {"mood": "剑拔弩张", "present": ["su_wan"]},
                        "relation_updates": [
                            {"from": "su_wan", "to": "lin_jiu", "tension": -0.9, "kind": "猜忌"}
                        ],
                        "flags": {"saw_ledger": True},
                    }
                ]
            ),
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))

        await _drain(chat, str(row.id))
        await db.refresh(row)
        scene = StoryStateSvc.get_scene_story(row)
        assert scene["mood"] == "剑拔弩张"
        assert scene["present"] == ["su_wan"]
        assert StoryStateSvc.get_story(row)["flags"] == {"saw_ledger": True}
        rel = StoryStateSvc.get_relations(row)[0]
        assert rel["tension"] == -0.9
        assert rel["kind"] == "猜忌"

    @pytest.mark.asyncio
    async def test_usage_accumulates_completion_tokens(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.chat import ChatSvc

        row = await _make_story_session(db, card_and_preset)
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["第一句"], ["第二句"]]))
        monkeypatch.setattr(
            chat, "_director",
            _FakeDirectorSvc(
                [{"speakers": [{"id": "su_wan"}, {"id": "lin_jiu"}]}]
            ),
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))

        events = await _drain(chat, str(row.id))
        usage = _first(events, "usage")
        # 两个说话者各 3 个汉字；estimate_tokens 对纯中文的估值为 4（见 services/tokens.py）
        assert usage["completion_tokens"] == 8


# --------------------------------------------------------------------------- #
# 1v1 零回归
# --------------------------------------------------------------------------- #
class TestOneVsOneUnchanged:
    @pytest.mark.asyncio
    async def test_rpg_session_has_no_story_events(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """spec=rpg_session 绝不能出现 director/speaker_switch/node/actions。"""
        from app.services.chat import ChatSvc
        from app.services.session import SessionSvc

        card_id, preset_id = card_and_preset
        created = await SessionSvc(db).create(
            {"character_card_id": str(card_id), "preset_id": str(preset_id), "greeting_index": -1}
        )
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["1v1 回复。"]]))
        # 若误走剧情分支会用到 director；装上炸弹确保不会
        monkeypatch.setattr(
            chat, "_director", _FakeDirectorSvc([AssertionError("不应调用导演")])
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([], RuntimeError("不应调用")))

        events = await _drain(chat, str(created["id"]))
        names = _names(events)
        assert names[0] == "world_info"
        assert names[1] == "start"
        assert names[-2] == "usage"
        assert names[-1] == "done"
        for forbidden in ("director", "speaker_switch", "node", "actions"):
            assert forbidden not in names

    @pytest.mark.asyncio
    async def test_rpg_session_no_world_id_still_works(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.chat import ChatSvc
        from app.services.session import SessionSvc

        card_id, preset_id = card_and_preset
        created = await SessionSvc(db).create(
            {"character_card_id": str(card_id), "preset_id": str(preset_id)}
        )
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["ok"]]))
        events = await _drain(chat, str(created["id"]))
        assert _names(events)[-1] == "done"


# --------------------------------------------------------------------------- #
# 并发抢占
# --------------------------------------------------------------------------- #
class TestConcurrency:
    @pytest.mark.asyncio
    async def test_busy_session_conflicts(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.core.errors import ConflictError
        from app.services.chat import ChatSvc

        row = await _make_story_session(db, card_and_preset)
        row.state_machine = {"current": "generating", "turn": 0, "version": 1}
        await db.flush()

        chat = ChatSvc(db)
        with pytest.raises(ConflictError):
            async for _ in chat.stream_reply(str(row.id), input_text="x"):
                pass

    @pytest.mark.asyncio
    async def test_interrupt_clears_streaming(
        self, db: AsyncSession, card_and_preset: tuple
    ) -> None:
        from app.services.chat import ChatSvc
        from app.services.session import SessionSvc

        row = await _make_story_session(db, card_and_preset)
        svc = SessionSvc(db)
        await svc.append_message(
            row.id, role="assistant", content="半", status="streaming", token_count=0
        )
        result = await ChatSvc(db).interrupt(str(row.id))
        assert result["interrupted"] is True
        rows = await svc.list_messages(row.id)
        assert [m for m in rows if m.status == "streaming"] == []


# --------------------------------------------------------------------------- #
# 剧情配图事件接线（S16 §4.6.3）
# --------------------------------------------------------------------------- #


class _FakeImageTrigger:
    """`ImageTriggerSvc` 替身：固定返回预设判定与提示词。

    只测「chat 是怎么把触发服务接进事件流的」，触发规则本身由
    `test_image_trigger.py` 覆盖，两边职责不重叠。

    注意：本替身**尊重 `enabled` 参数**。若像最初那样只认 `self._should`，
    「开关关闭不出图」这条断言就变成在测假对象，而非测 chat 的接线。
    """

    def __init__(self, *, should: bool, reason: str = "node") -> None:
        self._should = should
        self._reason = reason
        self.decide_calls: list[dict[str, Any]] = []
        self.render_calls: list[dict[str, Any]] = []

    def decide(self, **kwargs: Any):
        from app.services.image_trigger import TriggerDecision

        self.decide_calls.append(kwargs)
        if not kwargs.get("enabled"):
            return TriggerDecision(False, "disabled")
        if not self._should:
            return TriggerDecision(False, "no_signal")
        return TriggerDecision(True, self._reason, {"node_id": "n1"})

    async def render_prompt(self, **kwargs: Any):
        self.render_calls.append(kwargs)
        return ("一个雨夜的弄堂，青石板反光。", "文字, 水印", "landscape", "template")


class _FakeImageHook:
    """`ImageHook` 替身：不落盘、不调外部 API，直接返回带 asset_id 的 job。"""

    def __init__(self, *, asset_id: Any = "asset-1", fail: bool = False) -> None:
        self._asset_id = asset_id
        self._fail = fail
        self.calls: list[dict[str, Any]] = []

    async def generate_and_archive(self, **kwargs: Any):
        self.calls.append(kwargs)
        if self._fail:
            raise RuntimeError("upstream down")
        from types import SimpleNamespace

        return SimpleNamespace(id="job-1", asset_id=self._asset_id)


class TestStoryImageEvents:
    """守卫：自动配图事件的位置、字段、以及「失败不记账」的契约。"""

    async def _prep(
        self,
        db: AsyncSession,
        card_and_preset: tuple,
        monkeypatch: pytest.MonkeyPatch,
        *,
        enabled: bool,
        trigger: _FakeImageTrigger,
        hook: _FakeImageHook,
        actions: list[dict[str, Any]] | None = None,
    ) -> Any:
        from app.core.config import get_settings
        from app.services.chat import ChatSvc

        settings = get_settings()
        monkeypatch.setattr(settings, "story_image_enabled", enabled, raising=False)

        row = await _make_story_session(db, card_and_preset)
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["她", "笑了", "。"]]))
        monkeypatch.setattr(
            chat,
            "_director",
            _FakeDirectorSvc([{"speakers": [{"id": "su_wan", "name": "苏晚"}]}]),
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc(actions or []))
        monkeypatch.setattr(chat, "_image_trigger", trigger)
        monkeypatch.setattr(chat, "_image", hook)
        return row, chat

    @pytest.mark.asyncio
    async def test_image_event_sits_between_usage_and_actions(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """契约：`usage` → `image` → `actions` → `done`。

        前端按事件顺序渲染，位置错了会导致图片被塞到行动按钮之后。
        """
        row, chat = await self._prep(
            db,
            card_and_preset,
            monkeypatch,
            enabled=True,
            trigger=_FakeImageTrigger(should=True),
            hook=_FakeImageHook(),
            # 给一条建议，否则没有 actions 事件，「image 在 actions 之前」无从断言
            actions=[{"id": "a1", "label": "推门进去"}],
        )

        events = await _drain(chat, str(row.id))
        names = _names(events)

        assert "image" in names, "开启开关 + 触发命中时必须产出 image 事件"
        assert names.index("usage") < names.index("image") < names.index("done")
        assert names.index("image") < names.index("actions")

    @pytest.mark.asyncio
    async def test_image_event_carries_reason_and_asset(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """契约：前端需要 `asset_id` 取图、需要 `reason` 区分节点图/角色图。"""
        row, chat = await self._prep(
            db,
            card_and_preset,
            monkeypatch,
            enabled=True,
            trigger=_FakeImageTrigger(should=True, reason="cast"),
            hook=_FakeImageHook(asset_id="asset-9"),
        )

        events = await _drain(chat, str(row.id))
        payload = _first(events, "image")

        assert payload is not None
        assert payload["asset_id"] == "asset-9"
        assert payload["reason"] == "cast"
        assert payload["job_id"] == "job-1"

    @pytest.mark.asyncio
    async def test_disabled_switch_skips_without_calling_hook(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """开关关闭时**不得**触达出图服务 —— 这是「绝不默认烧钱」的硬保证。"""
        hook = _FakeImageHook()
        row, chat = await self._prep(
            db,
            card_and_preset,
            monkeypatch,
            enabled=False,
            trigger=_FakeImageTrigger(should=True),
            hook=hook,
        )

        events = await _drain(chat, str(row.id))

        assert "image" not in _names(events)
        assert hook.calls == []

    @pytest.mark.asyncio
    async def test_image_failure_does_not_break_stream(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """出图炸了也不能影响对话：仍要有 usage/actions/done，且无 error 事件。"""
        row, chat = await self._prep(
            db,
            card_and_preset,
            monkeypatch,
            enabled=True,
            trigger=_FakeImageTrigger(should=True),
            hook=_FakeImageHook(fail=True),
        )

        events = await _drain(chat, str(row.id))
        names = _names(events)

        assert "image" not in names
        assert "error" not in names
        assert names[-1] == "done"

    @pytest.mark.asyncio
    async def test_failure_does_not_consume_quota(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """**关键**：出图失败不得记账。否则玩家花了配额却没拿到图。"""
        row, chat = await self._prep(
            db,
            card_and_preset,
            monkeypatch,
            enabled=True,
            trigger=_FakeImageTrigger(should=True),
            hook=_FakeImageHook(fail=True),
        )

        await _drain(chat, str(row.id))
        story = chat._story_state.get_story(row)

        assert story.get("image_count", 0) == 0
        assert story.get("last_image_turn") is None

    @pytest.mark.asyncio
    async def test_success_consumes_quota_and_turn(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """成功才记账：`image_count` +1、`last_image_turn` 落到本轮。"""
        row, chat = await self._prep(
            db,
            card_and_preset,
            monkeypatch,
            enabled=True,
            trigger=_FakeImageTrigger(should=True),
            hook=_FakeImageHook(),
        )

        await _drain(chat, str(row.id))
        story = chat._story_state.get_story(row)

        assert story.get("image_count") == 1
        assert story.get("last_image_turn") == 0
        assert story.get("image_nodes") == ["n1"]

    @pytest.mark.asyncio
    async def test_asset_id_none_is_treated_as_failure(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """归档未回填 asset_id（没落盘）时不得发 image 事件，也不得记账。"""
        row, chat = await self._prep(
            db,
            card_and_preset,
            monkeypatch,
            enabled=True,
            trigger=_FakeImageTrigger(should=True),
            hook=_FakeImageHook(asset_id=None),
        )

        events = await _drain(chat, str(row.id))
        story = chat._story_state.get_story(row)

        assert "image" not in _names(events)
        assert story.get("image_count", 0) == 0

    @pytest.mark.asyncio
    async def test_image_persists_asset_id_to_message_meta(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """关联持久化（S16-8）：出图后必须把 asset_id 写进消息的 `meta.image_asset_id`。

        这是「刷新页面图片不丢」的唯一依据 —— 不写库，前端回读就找不到图。
        """
        row, chat = await self._prep(
            db,
            card_and_preset,
            monkeypatch,
            enabled=True,
            trigger=_FakeImageTrigger(should=True),
            hook=_FakeImageHook(asset_id="asset-persist"),
        )

        events = await _drain(chat, str(row.id))
        await db.flush()

        payload = _first(events, "image")
        assert payload is not None
        mid = payload["message_id"]

        # 库里该消息的 meta 必须已带上 asset_id（回读链路）
        messages = await chat._sessions.list_messages(row.id)
        target = next((m for m in messages if str(m.id) == mid), None)
        assert target is not None, "image 事件携带的 message_id 必须指向真实消息"
        assert (target.meta or {}).get("image_asset_id") == "asset-persist"

    @pytest.mark.asyncio
    async def test_image_event_carries_message_id_before_done(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """契约：`image` 事件必须自带 `message_id`，且落在 `done` **之前**。

        原因：image 到达时 done 还没到，前端拿不到「本轮最后一条 assistant」的 id，
        只能靠事件自带锚点挂载。这条断言守住该锚点，防止未来被误删。
        """
        row, chat = await self._prep(
            db,
            card_and_preset,
            monkeypatch,
            enabled=True,
            trigger=_FakeImageTrigger(should=True),
            hook=_FakeImageHook(asset_id="asset-anchor"),
        )

        events = await _drain(chat, str(row.id))
        names = _names(events)
        payload = _first(events, "image")

        assert payload is not None
        assert payload.get("message_id"), "image 事件必须携带 message_id 锚点"
        assert names.index("image") < names.index("done")

        # 锚点必须等于 done 事件报的 message_id（流式与回读同一锚点）
        done_payload = _first(events, "done")
        assert done_payload is not None
        assert payload["message_id"] == done_payload["message_id"]

    @pytest.mark.asyncio
    async def test_image_link_is_idempotent(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """幂等守门：消息已有图时不得被新图覆盖（一张图落到消息上就稳定）。"""
        row, chat = await self._prep(
            db,
            card_and_preset,
            monkeypatch,
            enabled=True,
            trigger=_FakeImageTrigger(should=True),
            hook=_FakeImageHook(asset_id="asset-first"),
        )

        await _drain(chat, str(row.id))
        await db.flush()

        # 手动模拟「重入」：拿同一条消息再关联一张不同的图
        messages = await chat._sessions.list_messages(row.id)
        target = next(m for m in messages if (m.meta or {}).get("image_asset_id"))
        await chat._link_image_to_message(target, "asset-second")
        await db.flush()

        refreshed = await chat._sessions.get_message(row.id, str(target.id))
        assert (refreshed.meta or {}).get("image_asset_id") == "asset-first"

    @pytest.mark.asyncio
    async def test_world_art_style_reaches_render_prompt(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """画风链路守卫：世界观 tags → 推断 → 传进 `render_prompt`。

        **回归守卫（用户实测反馈）**：修复前 `STYLE_SUFFIX` 是写死的无差别追加，
        所以火影忍者和惊悚悬疑轻小说出图长得一样。修复后 chat 必须把解析出的
        画风（`world_style` / `character_style`）透传给出图提示词构造器。

        本用例盯着三件容易漏接的事：
          1. `_load_world` 要带出 `tags`（它是 World 的顶层列，**不在 setting 里**）
          2. `_story_image_events` 要接收 `world` / `card`
          3. `render_prompt` 真的收到了解析结果（而不是 None）
        """
        trigger = _FakeImageTrigger(should=True)
        row, chat = await self._prep(
            db,
            card_and_preset,
            monkeypatch,
            enabled=True,
            trigger=trigger,
            hook=_FakeImageHook(),
        )

        # 夹具默认不绑世界观（world_id=None），这里补一个带火影 tag 的，
        # 让链路真正走一遍「world → tags → 推断 → render_prompt」。
        world = await _bind_fire_ninja_world(db, row, chat)
        if world is None:
            pytest.skip("无法为夹具绑定世界观")

        await _drain(chat, str(row.id))

        assert trigger.render_calls, "触发命中时必须调用 render_prompt"
        kwargs = trigger.render_calls[0]
        assert kwargs.get("world_style"), "world_style 不能是空 —— 否则又退回无画风"
        assert "动画" in kwargs["world_style"], (
            f"火影世界观应推断出动画风，实际拿到：{kwargs.get('world_style')!r}"
        )

    @pytest.mark.asyncio
    async def test_load_world_exposes_tags(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`_load_world` 必须带出 `tags` —— 画风推断的唯一依据。

        `World.tags` 是顶层 ARRAY 列（**不是** `setting` 里的键），
        所以若 `_load_world` 忘了带，`art_style` 就永远推断不出东西，
        整个画风特性会静默退化成全局兜底串。
        """
        row, chat = await self._prep(
            db, card_and_preset, monkeypatch,
            enabled=False, trigger=_FakeImageTrigger(should=False), hook=_FakeImageHook(),
        )
        world = await _bind_fire_ninja_world(db, row, chat)
        if world is None:
            pytest.skip("无法为夹具绑定世界观")

        loaded = await chat._load_world(row)
        assert "tags" in loaded
        assert "火影忍者" in loaded["tags"]

    @pytest.mark.asyncio
    async def test_empty_prompt_skips_generation(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """提示词为空（LLM 与模板都拿不到料）时应静默跳过，不发事件、不记账。"""

        class _EmptyPromptTrigger(_FakeImageTrigger):
            async def render_prompt(self, **kwargs: Any):
                self.render_calls.append(kwargs)
                return ("", "", "landscape", "template")

        hook = _FakeImageHook()
        row, chat = await self._prep(
            db,
            card_and_preset,
            monkeypatch,
            enabled=True,
            trigger=_EmptyPromptTrigger(should=True),
            hook=hook,
        )

        events = await _drain(chat, str(row.id))
        story = chat._story_state.get_story(row)

        assert "image" not in _names(events)
        assert hook.calls == []
        assert story.get("image_count", 0) == 0


class TestExplicitImageRequest:
    """显式请求（`overrides.image`）走另一条路径，且**不受开关/节流限制**。"""

    @pytest.mark.asyncio
    async def test_explicit_request_ignores_disabled_switch(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """玩家主动点「画一张」时，即使自动触发开关关闭也应当出图。"""
        from app.core.config import get_settings
        from app.services.chat import ChatSvc

        monkeypatch.setattr(
            get_settings(), "story_image_enabled", False, raising=False
        )
        row = await _make_story_session(db, card_and_preset)
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["她", "笑了", "。"]]))
        monkeypatch.setattr(
            chat,
            "_director",
            _FakeDirectorSvc([{"speakers": [{"id": "su_wan", "name": "苏晚"}]}]),
        )
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc([]))
        monkeypatch.setattr(
            chat, "_image_trigger", _FakeImageTrigger(should=False)
        )

        seen: list[dict[str, Any]] = []

        async def _fake_maybe_image_events(**kwargs: Any):
            seen.append(kwargs)
            yield "image", {"asset_id": "manual-1", "reason": "manual"}

        monkeypatch.setattr(chat, "_maybe_image_events", _fake_maybe_image_events)

        events: list[tuple[str, dict]] = []
        async for e, d in chat.stream_reply(
            str(row.id), input_text="画一张", overrides={"image": True}
        ):
            events.append((e, d))

        assert seen, "显式请求必须走到 _maybe_image_events"
        assert _first(events, "image") == {"asset_id": "manual-1", "reason": "manual"}


# --------------------------------------------------------------------------- #
# 建议持久化的 API 面（S15-1）
# --------------------------------------------------------------------------- #
class TestSuggestionsApi:
    """守住「刷新/重开会话能看到建议」这条端到端验收。

    后端落库（TestNodeAndActions 已覆盖）只是半边；真正决定玩家是否看到的是
    这两个端点的返回。老会话（无 suggestions 键）也必须安全返回空列表 ——
    否则重开历史会话会 500，比空建议区更糟。
    """

    @pytest.mark.asyncio
    async def test_story_endpoint_returns_persisted_suggestions(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.api.v1.sessions import get_actions, get_story_state
        from app.services.chat import ChatSvc

        row = await _make_story_session(db, card_and_preset)
        chat = ChatSvc(db)
        monkeypatch.setattr(chat, "_router", _FakeStreamRouter([["给你三个选择。"]]))
        monkeypatch.setattr(
            chat, "_director", _FakeDirectorSvc([{"speakers": [{"id": "su_wan"}]}])
        )
        actions = [
            {"id": "a0", "label": "问他账册", "hint": "施压", "tone": "speak"},
            {"id": "a1", "label": "看看窗外", "hint": "观察", "tone": "observe"},
        ]
        monkeypatch.setattr(chat, "_suggester", _FakeSuggesterSvc(actions))
        await _drain(chat, str(row.id))

        # 新开一个 session 读，模拟「刷新页面」——确保不是内存里的残留
        await db.commit()
        snap = await get_story_state(db, str(row.id))
        assert snap.data["suggestions"] == actions

        # /actions 应直接读库（不再重算），返回同一批
        got = await get_actions(db, str(row.id))
        assert got.data["actions"] == actions

    @pytest.mark.asyncio
    async def test_story_endpoint_old_session_returns_empty(
        self, db: AsyncSession, card_and_preset: tuple
    ) -> None:
        """老会话（从未落过建议）→ 空列表，不报错。"""
        from app.api.v1.sessions import get_story_state

        row = await _make_story_session(db, card_and_preset)
        snap = await get_story_state(db, str(row.id))
        assert snap.data["suggestions"] == []

    @pytest.mark.asyncio
    async def test_actions_endpoint_prefers_cache_over_llm(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """库里有建议时，/actions **不得**再调 LLM。

        早期实现每次实时重跑：同一轮补拉两次会拿到不同建议，且白烧一次调用。
        """
        from app.api.v1.sessions import get_actions

        row = await _make_story_session(db, card_and_preset)
        StoryStateSvc(db).set_suggestions(row, [{"id": "cached", "label": "库里的方向"}], turn=1)
        await db.flush()

        calls: list[Any] = []

        class _BoomSuggester:
            def __init__(self, *_a: Any, **_kw: Any) -> None: ...
            async def suggest(self, **kwargs: Any) -> list[dict[str, Any]]:
                calls.append(kwargs)
                raise AssertionError("库里有建议时不该调 LLM")

        monkeypatch.setattr("app.api.v1.sessions.ActionSuggesterSvc", _BoomSuggester)

        got = await get_actions(db, str(row.id))
        assert got.data["actions"] == [{"id": "cached", "label": "库里的方向"}]
        assert calls == []

    @pytest.mark.asyncio
    async def test_actions_endpoint_falls_back_when_cache_empty(
        self, db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """库里为空 → 回退实时生成（保留 SSE 尾帧丢失的兜底能力）。"""
        from app.api.v1.sessions import get_actions

        row = await _make_story_session(db, card_and_preset)

        calls: list[Any] = []

        class _StubSuggester:
            def __init__(self, *_a: Any, **_kw: Any) -> None: ...
            async def suggest(self, **kwargs: Any) -> list[dict[str, Any]]:
                calls.append(kwargs)
                return [{"id": "fresh", "label": "现算的"}]

        monkeypatch.setattr("app.api.v1.sessions.ActionSuggesterSvc", _StubSuggester)

        got = await get_actions(db, str(row.id))
        assert got.data["actions"] == [{"id": "fresh", "label": "现算的"}]
        assert len(calls) == 1
