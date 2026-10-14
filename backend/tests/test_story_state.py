"""剧情状态服务（StoryStateSvc）单元测试。

覆盖：模式判定、缺省值补齐、空/脏 row 边界、bump_turn、flags 增量、
关系图增量 PATCH（新增/覆盖/夹取/畸形丢弃）、scene 在场角色保序去重、
导演熔断计数、轮转下一说话者。

全部为纯函数式断言，不需要数据库（StoryStateSvc 只读写对象属性）。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.services.story_state import (
    DEFAULT_STORY,
    DIRECTOR_FAILURE_THRESHOLD,
    RPG_SPEC,
    STORY_SPEC,
    StoryStateSvc,
    is_story_session,
)


def _row(**overrides: Any) -> SimpleNamespace:
    """造一个最小会话行替身（只带 JSONB 列）。"""
    base: dict[str, Any] = {
        "spec": STORY_SPEC,
        "spec_version": "1.0",
        "world_id": None,
        "state_machine": {"current": "idle", "turn": 3, "version": 7, "last_error": None},
        "scene": {"location": "老弄堂·雨夜", "time": "深夜", "mood": "压抑", "summary": "雨没停。"},
        "extensions": {},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def svc() -> StoryStateSvc:
    return StoryStateSvc()


# --------------------------------------------------------------------------- #
# 模式判定
# --------------------------------------------------------------------------- #
class TestIsStorySession:
    def test_story_spec_true(self) -> None:
        assert is_story_session(_row(spec=STORY_SPEC)) is True

    def test_rpg_spec_false(self) -> None:
        assert is_story_session(_row(spec=RPG_SPEC)) is False

    def test_missing_spec_defaults_to_rpg(self) -> None:
        assert is_story_session(SimpleNamespace(state_machine={})) is False

    def test_none_row_is_not_story(self) -> None:
        assert is_story_session(None) is False

    def test_empty_spec_is_not_story(self) -> None:
        assert is_story_session(_row(spec="")) is False


# --------------------------------------------------------------------------- #
# get_story：缺省 / 边界
# --------------------------------------------------------------------------- #
class TestGetStory:
    def test_defaults_when_state_machine_empty(self) -> None:
        story = StoryStateSvc.get_story(_row(state_machine={}))
        for key, value in DEFAULT_STORY.items():
            assert key in story
            assert story[key] == value or story[key] == DEFAULT_STORY[key]

    def test_partial_story_merged_with_defaults(self) -> None:
        row = _row(state_machine={"story": {"beat_index": 5}})
        story = StoryStateSvc.get_story(row)
        assert story["beat_index"] == 5
        # 未提供的键仍取默认
        assert story["arc_id"] == DEFAULT_STORY["arc_id"]
        assert story["flags"] == {}

    def test_state_machine_none_is_tolerated(self) -> None:
        story = StoryStateSvc.get_story(_row(state_machine=None))
        assert story["beat_index"] == 0

    def test_story_wrong_type_is_replaced(self) -> None:
        """story 被写成字符串（脏数据）时不应炸，退化为默认。"""
        story = StoryStateSvc.get_story(_row(state_machine={"story": "oops"}))
        assert story["beat_index"] == 0
        assert isinstance(story["flags"], dict)

    def test_returned_dict_is_a_copy(self) -> None:
        """改动返回值不应污染原始 row（防止调用方误改权威状态）。"""
        row = _row(state_machine={"story": {"flags": {"a": 1}}})
        story = StoryStateSvc.get_story(row)
        story["flags"]["a"] = 999
        assert StoryStateSvc.get_story(row)["flags"]["a"] == 1

    def test_survives_bare_object(self) -> None:
        """完全没有 state_machine 属性的对象（如刚构造的 ORM 实例）也可读。"""
        assert StoryStateSvc.get_story(object())["beat_index"] == 0


# --------------------------------------------------------------------------- #
# 会话级读取
# --------------------------------------------------------------------------- #
class TestRelationsAndCast:
    def test_empty_when_extensions_empty(self) -> None:
        row = _row(extensions={})
        assert StoryStateSvc.get_relations(row) == []
        assert StoryStateSvc.get_cast(row) == []

    def test_relations_none_is_tolerated(self) -> None:
        row = _row(extensions={"story": {"relations": None}})
        assert StoryStateSvc.get_relations(row) == []

    def test_cast_map_drops_members_without_id(self) -> None:
        row = _row(
            extensions={
                "story": {
                    "cast": [
                        {"id": "su_wan", "name": "苏晚"},
                        {"name": "无名氏"},
                        {"id": "", "name": "空 id"},
                    ]
                }
            }
        )
        cast_map = StoryStateSvc.get_cast_map(row)
        assert set(cast_map) == {"su_wan"}
        assert cast_map["su_wan"]["name"] == "苏晚"

    def test_extract_world_id_prefers_extensions(self) -> None:
        row = _row(world_id="11111111-1111-1111-1111-111111111111")
        row.extensions = {"story": {"world_id": "w-fixed"}}
        assert StoryStateSvc.extract_world_id(row) == "w-fixed"

    def test_extract_world_id_falls_back_to_column(self) -> None:
        row = _row(world_id="22222222-2222-2222-2222-222222222222", extensions={})
        assert StoryStateSvc.extract_world_id(row) == "22222222-2222-2222-2222-222222222222"

    def test_extract_world_id_none_when_absent(self) -> None:
        assert StoryStateSvc.extract_world_id(_row(extensions={}, world_id=None)) is None


# --------------------------------------------------------------------------- #
# bump_turn
# --------------------------------------------------------------------------- #
class TestBumpTurn:
    def test_increments_beat_and_clears_pending_node(self, svc: StoryStateSvc) -> None:
        row = _row(state_machine={"story": {"beat_index": 2, "pending_node": {"id": "n-3"}}})
        story = svc.bump_turn(row)
        assert story["beat_index"] == 3
        assert story["pending_node"] is None

    def test_preserves_other_keys(self, svc: StoryStateSvc) -> None:
        row = _row(
            state_machine={
                "story": {"beat_index": 1, "arc_id": "act2", "flags": {"saw_letter": True}}
            }
        )
        story = svc.bump_turn(row)
        assert story["arc_id"] == "act2"
        assert story["flags"] == {"saw_letter": True}

    def test_does_not_touch_session_turn(self, svc: StoryStateSvc) -> None:
        """会话总轮次 turn 由 ChatSvc 维护，本服务不得越权修改。"""
        row = _row(state_machine={"turn": 12, "story": {"beat_index": 0}})
        svc.bump_turn(row)
        assert row.state_machine["turn"] == 12

    def test_resets_director_failures(self, svc: StoryStateSvc) -> None:
        row = _row(state_machine={"story": {"director_failures": 2}})
        assert svc.bump_turn(row)["director_failures"] == 0

    def test_repeated_bump_is_monotonic(self, svc: StoryStateSvc) -> None:
        row = _row(state_machine={"story": {"beat_index": 0}})
        for expected in (1, 2, 3):
            assert svc.bump_turn(row)["beat_index"] == expected

    def test_bump_on_bare_row(self, svc: StoryStateSvc) -> None:
        row = _row(state_machine={})
        assert svc.bump_turn(row)["beat_index"] == 1


# --------------------------------------------------------------------------- #
# set_story / flags
# --------------------------------------------------------------------------- #
class TestSetStoryAndFlags:
    def test_set_story_merges_without_dropping(self, svc: StoryStateSvc) -> None:
        row = _row(state_machine={"story": {"arc_id": "act1", "beat_index": 4}})
        svc.set_story(row, {"node_id": "n-7"})
        story = StoryStateSvc.get_story(row)
        assert story["arc_id"] == "act1"
        assert story["beat_index"] == 4
        assert story["node_id"] == "n-7"

    def test_apply_flags_is_incremental(self, svc: StoryStateSvc) -> None:
        row = _row(state_machine={"story": {"flags": {"a": 1}}})
        svc.apply_flags(row, {"b": 2})
        assert StoryStateSvc.get_story(row)["flags"] == {"a": 1, "b": 2}

    def test_apply_flags_overwrites_same_key(self, svc: StoryStateSvc) -> None:
        row = _row(state_machine={"story": {"flags": {"a": 1}}})
        svc.apply_flags(row, {"a": 9})
        assert StoryStateSvc.get_story(row)["flags"] == {"a": 9}

    def test_apply_empty_flags_is_noop(self, svc: StoryStateSvc) -> None:
        row = _row(state_machine={"story": {"flags": {"a": 1}}})
        svc.apply_flags(row, {})
        assert StoryStateSvc.get_story(row)["flags"] == {"a": 1}

    def test_flags_offset_false_is_kept(self, svc: StoryStateSvc) -> None:
        """flag 值为 False/0/"" 是有效表达「已关掉」，不能被真值判断吞掉。"""
        row = _row(state_machine={"story": {"flags": {}}})
        svc.apply_flags(row, {"met_su_wan": False})
        assert "met_su_wan" in StoryStateSvc.get_story(row)["flags"]


# --------------------------------------------------------------------------- #
# 导演熔断计数
# --------------------------------------------------------------------------- #
class TestDirectorCircuit:
    def test_failure_counter_increments(self, svc: StoryStateSvc) -> None:
        row = _row(state_machine={"story": {}})
        assert svc.mark_director_failure(row) == 1
        assert svc.mark_director_failure(row) == 2

    def test_circuit_closed_below_threshold(self, svc: StoryStateSvc) -> None:
        row = _row(state_machine={"story": {}})
        for _ in range(DIRECTOR_FAILURE_THRESHOLD - 1):
            svc.mark_director_failure(row)
        assert svc.is_director_circuit_open(row) is False

    def test_circuit_open_at_threshold(self, svc: StoryStateSvc) -> None:
        row = _row(state_machine={"story": {}})
        for _ in range(DIRECTOR_FAILURE_THRESHOLD):
            svc.mark_director_failure(row)
        assert svc.is_director_circuit_open(row) is True

    def test_success_clears_counter_and_records_turn(self, svc: StoryStateSvc) -> None:
        row = _row(state_machine={"story": {"director_failures": 3}})
        svc.mark_director_success(row, turn=8)
        story = StoryStateSvc.get_story(row)
        assert story["director_failures"] == 0
        assert story["last_director_at_turn"] == 8
        assert svc.is_director_circuit_open(row) is False

    def test_reset_director_circuit(self, svc: StoryStateSvc) -> None:
        row = _row(state_machine={"story": {"director_failures": 5}})
        svc.reset_director_circuit(row)
        assert svc.is_director_circuit_open(row) is False


# --------------------------------------------------------------------------- #
# 关系图增量更新
# --------------------------------------------------------------------------- #
class TestApplyRelationUpdates:
    @staticmethod
    def _seeded() -> SimpleNamespace:
        return _row(
            extensions={
                "story": {
                    "relations": [
                        {"from": "su_wan", "to": "lin_jiu", "kind": "旧识", "tension": 0.6},
                        {"from": "lin_jiu", "to": "su_wan", "kind": "旧识", "tension": -0.2},
                    ],
                    "relations_version": 1,
                }
            }
        )

    def test_empty_updates_returns_existing(self, svc: StoryStateSvc) -> None:
        row = self._seeded()
        result = svc.apply_relation_updates(row, [])
        assert len(result) == 2
        assert StoryStateSvc.get_relations(row)[0]["kind"] == "旧识"

    def test_existing_edge_is_patched_not_replaced(self, svc: StoryStateSvc) -> None:
        """增量语义：只覆盖传入字段，未传字段（note）保留。"""
        row = self._seeded()
        row.extensions["story"]["relations"][0]["note"] = "欠她一条命"
        svc.apply_relation_updates(
            row, [{"from": "su_wan", "to": "lin_jiu", "kind": "宿敌", "tension": -0.9}]
        )
        rel = StoryStateSvc.get_relations(row)[0]
        assert rel["kind"] == "宿敌"
        assert rel["tension"] == -0.9
        assert rel["note"] == "欠她一条命"  # 未传即保留

    def test_new_edge_is_appended(self, svc: StoryStateSvc) -> None:
        row = self._seeded()
        svc.apply_relation_updates(
            row, [{"from": "chen_bo", "to": "su_wan", "kind": "上下级", "tension": 0.3}]
        )
        rels = StoryStateSvc.get_relations(row)
        assert len(rels) == 3
        assert rels[2]["from"] == "chen_bo"

    def test_tension_is_clamped(self, svc: StoryStateSvc) -> None:
        row = self._seeded()
        svc.apply_relation_updates(
            row,
            [
                {"from": "su_wan", "to": "lin_jiu", "tension": 9.5},
                {"from": "lin_jiu", "to": "su_wan", "tension": -42},
            ],
        )
        rels = StoryStateSvc.get_relations(row)
        assert rels[0]["tension"] == 1.0
        assert rels[1]["tension"] == -1.0

    def test_malformed_tension_is_ignored(self, svc: StoryStateSvc) -> None:
        row = self._seeded()
        svc.apply_relation_updates(
            row, [{"from": "su_wan", "to": "lin_jiu", "tension": "很紧张"}]
        )
        assert StoryStateSvc.get_relations(row)[0]["tension"] == 0.6  # 保持原值

    def test_missing_endpoint_update_is_dropped(self, svc: StoryStateSvc) -> None:
        row = self._seeded()
        svc.apply_relation_updates(row, [{"from": "su_wan", "kind": "宿敌"}, {"to": "", "tension": 1}])
        assert len(StoryStateSvc.get_relations(row)) == 2  # 两条残缺更新都被丢弃

    def test_non_dict_update_is_dropped(self, svc: StoryStateSvc) -> None:
        row = self._seeded()
        svc.apply_relation_updates(row, ["not-a-dict", 42])  # type: ignore[list-item]
        assert len(StoryStateSvc.get_relations(row)) == 2

    def test_relations_version_advances(self, svc: StoryStateSvc) -> None:
        row = self._seeded()
        svc.apply_relation_updates(
            row, [{"from": "su_wan", "to": "lin_jiu", "kind": "宿敌"}]
        )
        assert row.extensions["story"]["relations_version"] == 2

    def test_works_without_seed(self, svc: StoryStateSvc) -> None:
        row = _row(extensions={})
        rels = svc.apply_relation_updates(
            row, [{"from": "a", "to": "b", "kind": "初识", "tension": 0.1}]
        )
        assert rels == [{"from": "a", "to": "b", "kind": "初识", "tension": 0.1}]

    def test_other_extension_keys_preserved(self, svc: StoryStateSvc) -> None:
        row = self._seeded()
        row.extensions["rpg"] = {"keep": "me"}
        svc.apply_relation_updates(row, [{"from": "a", "to": "b"}])
        assert row.extensions["rpg"] == {"keep": "me"}
        assert row.extensions["story"]["relations_version"] == 2


# --------------------------------------------------------------------------- #
# cast 固化 / world 绑定
# --------------------------------------------------------------------------- #
class TestCastAndBindWorld:
    def test_set_cast_replaces_and_bumps_version(self, svc: StoryStateSvc) -> None:
        row = _row(extensions={"story": {"cast": [{"id": "old"}], "relations_version": 4}})
        cast = svc.set_cast(row, [{"id": "su_wan", "name": "苏晚"}])
        assert cast == [{"id": "su_wan", "name": "苏晚"}]
        assert StoryStateSvc.get_cast(row) == [{"id": "su_wan", "name": "苏晚"}]
        assert row.extensions["story"]["relations_version"] == 5

    def test_bind_world_freezes_copy(self, svc: StoryStateSvc) -> None:
        row = _row(extensions={})
        source_cast = [{"id": "su_wan", "name": "苏晚"}]
        svc.bind_world(
            row,
            world_id="w-001",
            cast=source_cast,
            relations=[{"from": "su_wan", "to": "lin_jiu", "tension": 0.5}],
        )
        # 改动源列表不应影响已固化副本（深拷贝）
        source_cast[0]["name"] = "被篡改"
        assert StoryStateSvc.extract_world_id(row) == "w-001"
        assert StoryStateSvc.get_cast(row)[0]["name"] == "苏晚"
        assert len(StoryStateSvc.get_relations(row)) == 1

    def test_bind_world_without_cast_keeps_existing(self, svc: StoryStateSvc) -> None:
        row = _row(extensions={"story": {"cast": [{"id": "keep"}]}})
        svc.bind_world(row, world_id="w-002")
        assert StoryStateSvc.get_cast(row) == [{"id": "keep"}]


# --------------------------------------------------------------------------- #
# scene 在场角色
# --------------------------------------------------------------------------- #
class TestSceneUpdate:
    def test_present_dedupes_but_keeps_order(self, svc: StoryStateSvc) -> None:
        row = _row(scene={})
        scene = svc.apply_scene_update(
            row, {"present": ["su_wan", "lin_jiu", "su_wan", "chen_bo"]}
        )
        assert scene["present"] == ["su_wan", "lin_jiu", "chen_bo"]

    def test_present_drops_empty_ids(self, svc: StoryStateSvc) -> None:
        row = _row(scene={})
        scene = svc.apply_scene_update(row, {"present": ["su_wan", "", None, "lin_jiu"]})
        assert scene["present"] == ["su_wan", "lin_jiu"]

    def test_other_scene_keys_untouched(self, svc: StoryStateSvc) -> None:
        row = _row(scene={"location": "老弄堂", "time": "深夜"})
        scene = svc.apply_scene_update(row, {"beat": "两人对质"})
        assert scene["location"] == "老弄堂"
        assert scene["time"] == "深夜"
        assert scene["beat"] == "两人对质"

    def test_get_present_defaults_empty(self) -> None:
        assert StoryStateSvc.get_present(_row(scene={})) == []

    def test_set_present_helper(self, svc: StoryStateSvc) -> None:
        row = _row(scene={})
        assert svc.set_present(row, ["a", "b", "a"]) == ["a", "b"]


# --------------------------------------------------------------------------- #
# 轮转
# --------------------------------------------------------------------------- #
class TestNextSpeaker:
    def test_cycles_through_present(self) -> None:
        row = _row(scene={"present": ["su_wan", "lin_jiu", "chen_bo"]})
        assert StoryStateSvc.next_speaker_after(row, "su_wan") == "lin_jiu"
        assert StoryStateSvc.next_speaker_after(row, "chen_bo") == "su_wan"  # 回环

    def test_unknown_speaker_falls_back_to_first(self) -> None:
        row = _row(scene={"present": ["su_wan", "lin_jiu"]})
        assert StoryStateSvc.next_speaker_after(row, "stranger") == "su_wan"

    def test_none_speaker_returns_first(self) -> None:
        row = _row(scene={"present": ["su_wan", "lin_jiu"]})
        assert StoryStateSvc.next_speaker_after(row, None) == "su_wan"

    def test_empty_present_returns_none(self) -> None:
        assert StoryStateSvc.next_speaker_after(_row(scene={}), "su_wan") is None


# --------------------------------------------------------------------------- #
# 行动建议持久化（S15-1）
# --------------------------------------------------------------------------- #
class TestSuggestions:
    """建议落库/读取的边界。

    这些用例守的是「刷新后建议区不空」这条验收 —— 一旦 getter 在缺省/脏数据上
    抛异常或漏键，玩家重开历史会话就会看到空芯片区（正是 S15-1 要修的 bug）。
    """

    SAMPLE = [
        {"id": "a1", "label": "翻看账册", "tone": "observe"},
        {"id": "a2", "label": "推门进去", "tone": "move"},
    ]

    def test_get_defaults_empty_on_fresh_row(self) -> None:
        """全新会话（无 suggestions 键）→ 空列表，不炸。"""
        assert StoryStateSvc.get_suggestions(_row(state_machine={"story": {}})) == []

    def test_get_defaults_empty_on_missing_story(self) -> None:
        assert StoryStateSvc.get_suggestions(_row(state_machine={})) == []

    def test_set_then_get_roundtrip(self, svc: StoryStateSvc) -> None:
        row = _row(state_machine={"story": {}})
        svc.set_suggestions(row, self.SAMPLE, turn=3)
        got = StoryStateSvc.get_suggestions(row)
        assert [s["id"] for s in got] == ["a1", "a2"]
        assert StoryStateSvc.get_story(row)["suggestions_turn"] == 3

    def test_set_replaces_not_appends(self, svc: StoryStateSvc) -> None:
        """整体替换：旧建议不该残留在库里（否则玩家看到过期方向）。"""
        row = _row(state_machine={"story": {"suggestions": self.SAMPLE}})
        svc.set_suggestions(row, [{"id": "b1", "label": "回头看"}], turn=4)
        assert [s["id"] for s in StoryStateSvc.get_suggestions(row)] == ["b1"]

    def test_set_empty_clears_previous(self, svc: StoryStateSvc) -> None:
        """本轮没生成建议 → 明确清空，而非保留上一轮。"""
        row = _row(state_machine={"story": {"suggestions": self.SAMPLE}})
        svc.set_suggestions(row, [], turn=5)
        assert StoryStateSvc.get_suggestions(row) == []

    def test_get_drops_non_dict_elements(self) -> None:
        """LLM 偶发吐裸字符串 → 丢弃，不能污染前端渲染。"""
        row = _row(state_machine={"story": {"suggestions": [{"id": "a1"}, "垃圾", 123, None]}})
        assert [s["id"] for s in StoryStateSvc.get_suggestions(row)] == ["a1"]

    def test_get_returns_deep_copy(self, svc: StoryStateSvc) -> None:
        """返回深拷贝：调用方改动不能回写进 row（否则脏染状态机）。"""
        row = _row(state_machine={"story": {"suggestions": self.SAMPLE}})
        got = StoryStateSvc.get_suggestions(row)
        got[0]["label"] = "被改了"
        assert StoryStateSvc.get_suggestions(row)[0]["label"] == "翻看账册"

    def test_set_tolerates_dirty_input(self, svc: StoryStateSvc) -> None:
        """传进来非 dict 元素 / None 都不该炸。"""
        row = _row(state_machine={"story": {}})
        svc.set_suggestions(row, [{"id": "a1"}, "垃圾", None], turn=1)  # type: ignore[list-item]
        assert [s["id"] for s in StoryStateSvc.get_suggestions(row)] == ["a1"]

    def test_suggestions_key_present_in_default(self) -> None:
        """DEFAULT_STORY 必须带该键，否则 get_story 合并后取到 KeyError。"""
        assert DEFAULT_STORY["suggestions"] == []
        assert DEFAULT_STORY["suggestions_turn"] is None
