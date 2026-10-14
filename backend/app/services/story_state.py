"""剧情状态服务（剧情引擎 §3.2–3.5）。

职责（**纯状态读写，不碰 LLM / HTTP**）：
  - 模式判定：`spec == "story_session"` 即剧情会话（旧行天然走 1v1）
  - `state_machine.story` 子状态：幕/拍点/待触发节点/flags/导演失败计数
  - `scene` 扩展：在场角色 + 上一说话者 + 本拍描述
  - `extensions.story`：世界观 id + 角色群/关系图**固化副本**（避免每轮回查 worlds 表）

设计铁律：
  1. **所有键全可选、全带默认值** —— 老会话行（无 `story` 键）调用任何 getter 都不炸。
  2. **只改传入的键** —— 增量 PATCH 语义，绝不整体覆盖，避免并发写丢字段。
  3. **不 commit / 不 flush** —— 事务边界归调用方（ChatSvc / API 层）所有，
     保证「状态推进 + 消息落库」在同一事务内，要么全成功要么全回滚。
  4. 未知键不销毁 —— `extra` 一律保留透传。
"""

from __future__ import annotations

import copy
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #
#: 剧情会话的 spec 值；`rpg_session`（缺省）仍是 1v1，旧数据零迁移
STORY_SPEC = "story_session"
#: 1v1 会话 spec（显式写出，便于对照）
RPG_SPEC = "rpg_session"

#: `state_machine.story` 默认值。全可选 —— 缺任一键都能补齐。
DEFAULT_STORY: dict[str, Any] = {
    "arc_id": "act1",  # 当前幕
    "beat_index": 0,  # 当前拍点序号（会随轮次自增）
    "node_id": None,  # 已触发的最近剧情节点 id
    "pending_node": None,  # 待触发节点（导演判定满足 trigger 后写入）
    "flags": {},  # 剧情标记：{"saw_letter": true}
    "last_director_at_turn": -1,  # 上次成功调用导演的轮次（防重复决策）
    "director_failures": 0,  # 连续失败计数，≥3 触发熔断
    # ---- 剧情配图（S16 §4.6.3）----
    "image_count": 0,  # 本局已出图张数（配额用）
    "last_image_turn": None,  # 上次出图的轮次（最小间隔用）
    "image_nodes": [],  # 已配图的节点 id（去重：同一节点只画一次）
    "image_cast": [],  # 已配图的角色 id（去重：同一角色只画一次）
    # ---- 行动建议（S15-1）----
    # 每轮生成后落库，刷新/重开会话可恢复。**只存最近一轮**（数组整体替换），
    # 不做历史累积：建议是「此刻该做什么」的即时提示，攒旧建议只会干扰玩家。
    "suggestions": [],
    "suggestions_turn": None,  # 建议对应的轮次（前端可判断是否与当前进度同步）
}

#: `scene` 新增键的默认值（`location/time/mood/summary` 由旧字段复用）
DEFAULT_SCENE_STORY: dict[str, Any] = {
    "present": [],  # 在场角色 id（有序，用于轮转）
    "last_speaker_id": None,
    "beat": "",  # 本拍一句话描述
}

#: `extensions.story` 默认值
DEFAULT_EXT_STORY: dict[str, Any] = {
    "world_id": None,
    "relations": [],
    "cast": [],
    "relations_version": 0,
}

#: 连续失败多少次后熔断导演（跳过 LLM，直接 fallback）
DIRECTOR_FAILURE_THRESHOLD = 3


def is_story_session(row: Any) -> bool:
    """判断会话行是否剧情模式。

    容忍 `row` 为 `None`、缺 `spec` 属性、`spec` 为空串 —— 一律按 1v1 处理，
    这样旧行（server_default `rpg_session`）与测试假对象都不会误判。
    """
    spec = str(getattr(row, "spec", "") or RPG_SPEC)
    return spec == STORY_SPEC


class StoryStateSvc:
    """剧情状态读写。所有方法同步（不 await），由调用方统一 flush。"""

    def __init__(self, db: AsyncSession | None = None) -> None:
        # db 目前用不到（状态全在 row 的 JSONB 列里），保留入参是为
        # 与其它 Svc 的构造签名一致，也为将来可能的关系表查询留口子。
        self._db = db

    # ------------------------------------------------------------------ #
    # 读：带默认值的只读视图（返回深拷贝，调用方可安全改）
    # ------------------------------------------------------------------ #
    @staticmethod
    def get_story(row: Any) -> dict[str, Any]:
        """取 `state_machine.story`，缺省/脏数据自动补齐默认值。"""
        sm = getattr(row, "state_machine", None) or {}
        raw = sm.get("story") if isinstance(sm, dict) else None
        merged = {**DEFAULT_STORY, **(raw if isinstance(raw, dict) else {})}
        # flags 是嵌套 dict，也要与默认合并而不是整体替换
        flags = merged.get("flags")
        merged["flags"] = dict(flags) if isinstance(flags, dict) else {}
        return copy.deepcopy(merged)

    @staticmethod
    def get_relations(row: Any) -> list[dict[str, Any]]:
        """取固化的关系图副本（不查 worlds 表）。"""
        ext = getattr(row, "extensions", None) or {}
        story = ext.get("story") if isinstance(ext, dict) else None
        rels = story.get("relations") if isinstance(story, dict) else None
        if not isinstance(rels, list):
            return []
        return copy.deepcopy([r for r in rels if isinstance(r, dict)])

    @staticmethod
    def get_cast(row: Any) -> list[dict[str, Any]]:
        """取固化的角色群副本。"""
        ext = getattr(row, "extensions", None) or {}
        story = ext.get("story") if isinstance(ext, dict) else None
        cast = story.get("cast") if isinstance(story, dict) else None
        if not isinstance(cast, list):
            return []
        return copy.deepcopy([c for c in cast if isinstance(c, dict)])

    @staticmethod
    def get_cast_map(row: Any) -> dict[str, dict[str, Any]]:
        """角色 id → 角色对象。id 为空的行被丢弃（无法被引用）。"""
        out: dict[str, dict[str, Any]] = {}
        for member in StoryStateSvc.get_cast(row):
            cid = str(member.get("id") or "")
            if cid:
                out[cid] = member
        return out

    @staticmethod
    def get_scene_story(row: Any) -> dict[str, Any]:
        """取 `scene` 的剧情扩展键（present / last_speaker_id / beat）。"""
        scene = getattr(row, "scene", None) or {}
        base = scene if isinstance(scene, dict) else {}
        merged = {**DEFAULT_SCENE_STORY, **base}
        present = merged.get("present")
        merged["present"] = list(present) if isinstance(present, list) else []
        return copy.deepcopy(merged)

    @staticmethod
    def get_present(row: Any) -> list[str]:
        """在场角色 id 列表（字符串化，剔除空值）。"""
        return [str(x) for x in StoryStateSvc.get_scene_story(row)["present"] if str(x or "")]

    @staticmethod
    def get_suggestions(row: Any) -> list[dict[str, Any]]:
        """取上一轮落库的行动建议（S15-1）。

        老会话行没有这个键 —— 返回空列表，前端建议区自然隐藏，不报错。
        只保留 dict 元素（LLM 偶发吐出的裸字符串会污染前端渲染）。
        """
        raw = StoryStateSvc.get_story(row).get("suggestions")
        if not isinstance(raw, list):
            return []
        return copy.deepcopy([s for s in raw if isinstance(s, dict)])

    def set_suggestions(self, row: Any, suggestions: list[dict[str, Any]], *, turn: int | None = None) -> None:
        """把本轮建议写进 `state_machine.story`（S15-1）。

        **整体替换而非追加**：建议只对"当前这一刻"有意义，攒历史会让芯片区越堆越乱。
        空列表也要写入 —— 否则上一轮的建议会残留在库里，玩家重新打开会话会看到
        早已过期的方向。
        """
        cleaned = [s for s in (suggestions or []) if isinstance(s, dict)]
        self.set_story(row, {"suggestions": cleaned, "suggestions_turn": turn})

    @staticmethod
    def extract_world_id(row: Any) -> str | None:
        """会话绑定的世界观 id：优先 `extensions.story.world_id`，回退 `row.world_id`。"""
        ext = getattr(row, "extensions", None) or {}
        story = ext.get("story") if isinstance(ext, dict) else None
        wid = story.get("world_id") if isinstance(story, dict) else None
        if wid:
            return str(wid)
        col = getattr(row, "world_id", None)
        return str(col) if col else None

    # ------------------------------------------------------------------ #
    # 写：增量 PATCH（只改传入键，保持未知键）
    # ------------------------------------------------------------------ #
    def set_story(self, row: Any, patch: dict[str, Any]) -> dict[str, Any]:
        """增量更新 `state_machine.story`（浅合并）。返回更新后的完整 story。"""
        story = self.get_story(row)  # get_story 已返回深拷贝
        for key, value in (patch or {}).items():
            if key == "flags" and isinstance(value, dict):
                story["flags"] = {**story.get("flags", {}), **value}
            else:
                story[key] = value
        sm = dict(getattr(row, "state_machine", None) or {})
        sm["story"] = story
        row.state_machine = sm
        return story

    def set_story_many(self, row: Any, **patch: Any) -> dict[str, Any]:
        """`set_story` 的关键字语法糖。"""
        return self.set_story(row, patch)

    def bump_turn(self, row: Any) -> dict[str, Any]:
        """一轮结束：`beat_index` +1、清 `pending_node`、记录导演失败清零。

        注意：`state_machine.turn`（会话总轮次）由 ChatSvc 现有骨架维护，
        这里只推进剧情自己的拍点，两者刻意解耦。
        """
        story = self.get_story(row)
        story["beat_index"] = int(story.get("beat_index") or 0) + 1
        story["pending_node"] = None
        story["director_failures"] = 0
        sm = dict(getattr(row, "state_machine", None) or {})
        sm["story"] = story
        row.state_machine = sm
        return story

    def apply_flags(self, row: Any, flags: dict[str, Any]) -> dict[str, Any]:
        """合并剧情标记（增量）。空入参为 no-op。"""
        if not flags:
            return self.get_story(row)
        story = self.get_story(row)
        merged = {**story.get("flags", {}), **flags}
        sm = dict(getattr(row, "state_machine", None) or {})
        story["flags"] = merged
        sm["story"] = story
        row.state_machine = sm
        return story

    def mark_director_success(self, row: Any, turn: int) -> dict[str, Any]:
        """导演调用成功：记录轮次、失败计数清零。"""
        return self.set_story(
            row, {"last_director_at_turn": int(turn), "director_failures": 0}
        )

    def mark_director_failure(self, row: Any) -> int:
        """导演调用失败：失败计数 +1。返回累计失败次数（供熔断判断）。"""
        story = self.get_story(row)
        failures = int(story.get("director_failures") or 0) + 1
        self.set_story(row, {"director_failures": failures})
        return failures

    def is_director_circuit_open(self, row: Any) -> bool:
        """熔断是否已打开（连续失败达阈值）。"""
        return int(self.get_story(row).get("director_failures") or 0) >= DIRECTOR_FAILURE_THRESHOLD

    def reset_director_circuit(self, row: Any) -> None:
        self.set_story(row, {"director_failures": 0})

    # ------------------------------------------------------------------ #
    # 写：关系图 / 角色群 / 场景
    # ------------------------------------------------------------------ #
    def apply_relation_updates(self, row: Any, updates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按 `(from,to)` 增量 PATCH 关系图。

        - 边已存在 → 只覆盖传入的字段（`kind/tension/note`）；
        - 边不存在 → 追加新边（这是导演「新结仇/新结盟」的表达方式）；
        - `tension` 夹到 [-1, 1]，脏值不写入；
        - 逐条丢弃畸形项（缺 from/to），不影响其它更新。
        返回更新后的完整关系图。
        """
        if not updates:
            return self.get_relations(row)

        relations = self.get_relations(row)
        # 索引：归一化后的 (from,to) -> 列表下标（同一对可能有多条不同 kind 的边）
        index: dict[tuple[str, str], int] = {}
        for i, rel in enumerate(relations):
            index[(str(rel.get("from") or ""), str(rel.get("to") or ""))] = i

        for upd in updates:
            if not isinstance(upd, dict):
                continue
            src = str(upd.get("from") or "")
            dst = str(upd.get("to") or "")
            if not src or not dst:
                continue  # 缺端点无法定位边，丢弃

            patch = self._clean_relation_patch(upd)
            key = (src, dst)
            if key in index:
                merged = {**relations[index[key]], **patch}
                # 万一原始边缺端点（历史脏数据），补上归一化后的值
                merged["from"], merged["to"] = src, dst
                relations[index[key]] = merged
            else:
                index[key] = len(relations)
                relations.append({"from": src, "to": dst, **patch})

        self._write_relations(row, relations)
        return relations

    @staticmethod
    def _clean_relation_patch(upd: dict[str, Any]) -> dict[str, Any]:
        """把一条 relation_update 洗成可写入的 patch（含 tension 夹取）。"""
        patch: dict[str, Any] = {}
        for field in ("kind", "note"):
            if field in upd:
                patch[field] = str(upd.get(field) or "")
        if "tension" in upd:
            try:
                value = float(upd["tension"])
            except (TypeError, ValueError):
                value = None
            if value is not None:
                patch["tension"] = max(-1.0, min(1.0, value))
        return patch

    def _write_relations(self, row: Any, relations: list[dict[str, Any]]) -> None:
        ext = dict(getattr(row, "extensions", None) or {})
        story = dict(ext.get("story") or {})
        story["relations"] = [copy.deepcopy(r) for r in relations]
        story["relations_version"] = int(story.get("relations_version") or 0) + 1
        ext["story"] = story
        row.extensions = ext

    def set_cast(self, row: Any, cast: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """整体替换角色群副本，并把 relations_version 前进（供前端缓存失效）。"""
        cleaned = [copy.deepcopy(c) for c in (cast or []) if isinstance(c, dict)]
        ext = dict(getattr(row, "extensions", None) or {})
        story = dict(ext.get("story") or {})
        story["cast"] = cleaned
        story["relations_version"] = int(story.get("relations_version") or 0) + 1
        ext["story"] = story
        row.extensions = ext
        return cleaned

    def bind_world(
        self,
        row: Any,
        *,
        world_id: str | None,
        cast: list[dict[str, Any]] | None = None,
        relations: list[dict[str, Any]] | None = None,
    ) -> None:
        """剧情会话创建时：把世界 id + 角色群 + 关系图**固化副本**进 extensions。

        固化而非每轮回查 worlds 表，是因为世界可能在会话进行中被编辑/删除，
        而剧情一旦开演，其内部事实应保持一致（世界观被删则旁白与已固化设定仍可用）。
        """
        ext = dict(getattr(row, "extensions", None) or {})
        story = dict(ext.get("story") or {})
        story["world_id"] = str(world_id) if world_id else None
        if cast is not None:
            story["cast"] = [copy.deepcopy(c) for c in cast if isinstance(c, dict)]
        if relations is not None:
            story["relations"] = [copy.deepcopy(r) for r in relations if isinstance(r, dict)]
        story["relations_version"] = int(story.get("relations_version") or 0) + 1
        ext["story"] = story
        row.extensions = ext

    def apply_scene_update(self, row: Any, patch: dict[str, Any]) -> dict[str, Any]:
        """增量更新 `scene`（含剧情扩展键）。返回更新后的完整 scene。"""
        scene = dict(getattr(row, "scene", None) or {})
        for key, value in (patch or {}).items():
            if key == "present" and isinstance(value, list):
                # 去重但**保序**（顺序即轮转顺序，不可用 set）
                seen: set[str] = set()
                ordered: list[str] = []
                for item in value:
                    sid = str(item or "")
                    if sid and sid not in seen:
                        seen.add(sid)
                        ordered.append(sid)
                scene["present"] = ordered
            else:
                scene[key] = value
        row.scene = scene
        return copy.deepcopy(scene)

    def set_present(self, row: Any, present: list[str]) -> list[str]:
        """单独设置在场角色（保序去重）。"""
        return list(self.apply_scene_update(row, {"present": present})["present"])

    # ------------------------------------------------------------------ #
    # 便捷：轮转下一说话者
    # ------------------------------------------------------------------ #
    @staticmethod
    def next_speaker_after(row: Any, speaker_id: str | None) -> str | None:
        """按 `scene.present` 顺序取 `speaker_id` 的下一位（环形）。

        导演未指定顺序时用于兜底轮转；`present` 为空或找不到当前说话者则取首位。
        """
        present = StoryStateSvc.get_present(row)
        if not present:
            return None
        if not speaker_id or speaker_id not in present:
            return present[0]
        idx = present.index(speaker_id)
        return present[(idx + 1) % len(present)]


__all__ = [
    "DEFAULT_EXT_STORY",
    "DEFAULT_SCENE_STORY",
    "DEFAULT_STORY",
    "DIRECTOR_FAILURE_THRESHOLD",
    "RPG_SPEC",
    "STORY_SPEC",
    "StoryStateSvc",
    "is_story_session",
]
