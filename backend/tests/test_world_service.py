"""世界观服务（WorldSvc）+ 剧情会话创建（SessionSvc.create_story_session）单测（sqlite）。

覆盖：
  - WorldSvc CRUD、部分更新白名单、标签、检索、serialize 字段完整性
  - `create` 分派：带 world_id → 剧情会话；不带 → 1v1（零回归）
  - 剧情会话把 cast/relations 固化进 extensions.story
  - 序幕落库：每段 meta.beat_role == "opening"，seq 单调
  - 世界不存在 → NotFoundError

注：中文子串检索依赖 pg_trgm，sqlite 下 `ilike` 仍可用（只是不走索引），
断言只看命中结果，不断言执行计划。
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.services.world import WorldSvc

WORLD_INPUT: dict[str, Any] = {
    "spec": "rpg_world",
    "spec_version": "1.0",
    "title": "雨巷旧案",
    "setting": {
        "summary": "1935 年的上海，雨连着下了半个月。",
        "era": "民国",
        "tone": "阴冷、克制",
        "locations": ["老弄堂", "码头"],
        "rules": ["没人愿意谈起那桩案子"],
    },
    "factions": [{"id": "f1", "name": "巡捕房", "stance": "中立", "description": ""}],
    "cast": [
        {"id": "su_wan", "name": "苏晚", "role": "主角", "voice": "克制、短句",
         "goals": ["查明旧案"], "description": "旧书店账房"},
        {"id": "lin_jiu", "name": "林九", "role": "配角", "voice": "油滑",
         "goals": [], "description": "码头掮客"},
    ],
    "relations": [
        {"from": "su_wan", "to": "lin_jiu", "kind": "旧识", "tension": 0.6, "note": ""}
    ],
    "outline": {
        "main_goal": "查明旧案",
        "nodes": [{"id": "n-003", "title": "旧案重启", "brief": "", "trigger": "出示账册"}],
        "endings": ["真相大白"],
    },
    "opening": "雨敲着铁皮棚。",
    "extensions": {},
    "tags": ["民国", "悬疑"],
}


# --------------------------------------------------------------------------- #
# WorldSvc CRUD
# --------------------------------------------------------------------------- #
class TestWorldCrud:
    @pytest.mark.asyncio
    async def test_create_and_get(self, db: AsyncSession) -> None:
        svc = WorldSvc(db)
        created = await svc.create(WORLD_INPUT)
        assert created["title"] == "雨巷旧案"
        assert created["spec"] == "rpg_world"
        assert len(created["cast"]) == 2
        assert len(created["relations"]) == 1
        assert created["outline"]["main_goal"] == "查明旧案"
        assert created["tags"] == ["民国", "悬疑"]
        assert created["id"]

        fetched = await svc.get(str(created["id"]))
        assert fetched["title"] == created["title"]
        assert fetched["setting"]["era"] == "民国"

    @pytest.mark.asyncio
    async def test_create_without_title_uses_default(self, db: AsyncSession) -> None:
        created = await WorldSvc(db).create({"title": "   "})
        assert created["title"] == "未命名世界"

    @pytest.mark.asyncio
    async def test_create_minimal(self, db: AsyncSession) -> None:
        created = await WorldSvc(db).create({"title": "极简世界"})
        assert created["cast"] == []
        assert created["relations"] == []
        assert created["setting"] == {}
        assert created["opening"] == ""

    @pytest.mark.asyncio
    async def test_get_missing_raises(self, db: AsyncSession) -> None:
        with pytest.raises(NotFoundError):
            await WorldSvc(db).get("00000000-0000-0000-0000-000000000000")

    @pytest.mark.asyncio
    async def test_serialize_round_trip(self, db: AsyncSession) -> None:
        svc = WorldSvc(db)
        created = await svc.create(WORLD_INPUT)
        row = await svc.get_row(str(created["id"]))
        assert WorldSvc.serialize(row) == created


# --------------------------------------------------------------------------- #
# 更新
# --------------------------------------------------------------------------- #
class TestWorldUpdate:
    @pytest.mark.asyncio
    async def test_partial_update_preserves_other_keys(self, db: AsyncSession) -> None:
        svc = WorldSvc(db)
        created = await svc.create(WORLD_INPUT)
        updated = await svc.update(str(created["id"]), {"opening": "改了开场。"})
        assert updated["opening"] == "改了开场。"
        assert updated["title"] == "雨巷旧案"  # 未传即保留
        assert len(updated["cast"]) == 2

    @pytest.mark.asyncio
    async def test_update_title(self, db: AsyncSession) -> None:
        svc = WorldSvc(db)
        created = await svc.create(WORLD_INPUT)
        updated = await svc.update(str(created["id"]), {"title": "新标题"})
        assert updated["title"] == "新标题"

    @pytest.mark.asyncio
    async def test_update_replaces_arrays(self, db: AsyncSession) -> None:
        svc = WorldSvc(db)
        created = await svc.create(WORLD_INPUT)
        updated = await svc.update(
            str(created["id"]), {"cast": [{"id": "only", "name": "唯一角色"}]}
        )
        assert len(updated["cast"]) == 1
        assert updated["cast"][0]["id"] == "only"

    @pytest.mark.asyncio
    async def test_unknown_keys_ignored(self, db: AsyncSession) -> None:
        """非白名单键（如 id/owner_id）不能被改写。"""
        svc = WorldSvc(db)
        created = await svc.create(WORLD_INPUT)
        updated = await svc.update(
            str(created["id"]), {"id": "hacked", "owner_id": "hacked", "title": "合法改动"}
        )
        assert updated["id"] == created["id"]
        assert updated["title"] == "合法改动"

    @pytest.mark.asyncio
    async def test_none_values_ignored(self, db: AsyncSession) -> None:
        svc = WorldSvc(db)
        created = await svc.create(WORLD_INPUT)
        updated = await svc.update(str(created["id"]), {"opening": None, "title": "留着"})
        assert updated["opening"] == "雨敲着铁皮棚。"
        assert updated["title"] == "留着"

    @pytest.mark.asyncio
    async def test_update_tags(self, db: AsyncSession) -> None:
        svc = WorldSvc(db)
        created = await svc.create(WORLD_INPUT)
        updated = await svc.update(str(created["id"]), {"tags": ["新标签", ""]})
        assert updated["tags"] == ["新标签"]

    @pytest.mark.asyncio
    async def test_update_missing_raises(self, db: AsyncSession) -> None:
        with pytest.raises(NotFoundError):
            await WorldSvc(db).update(
                "00000000-0000-0000-0000-000000000000", {"title": "x"}
            )


# --------------------------------------------------------------------------- #
# 列表 / 删除
# --------------------------------------------------------------------------- #
class TestWorldListDelete:
    @pytest.mark.asyncio
    async def test_list_returns_all(self, db: AsyncSession) -> None:
        svc = WorldSvc(db)
        await svc.create({**WORLD_INPUT, "title": "世界甲"})
        await svc.create({**WORLD_INPUT, "title": "世界乙"})
        items, meta = await svc.list()
        assert len(items) == 2
        assert meta["total"] == 2

    @pytest.mark.asyncio
    async def test_list_query_filters(self, db: AsyncSession) -> None:
        svc = WorldSvc(db)
        await svc.create({**WORLD_INPUT, "title": "雨巷旧案"})
        await svc.create({**WORLD_INPUT, "title": "雪原孤舟"})
        items, meta = await svc.list(q="雨巷")
        assert [i["title"] for i in items] == ["雨巷旧案"]
        assert meta["total"] == 1

    @pytest.mark.asyncio
    async def test_list_pagination(self, db: AsyncSession) -> None:
        svc = WorldSvc(db)
        for i in range(5):
            await svc.create({**WORLD_INPUT, "title": f"世界{i}"})
        items, meta = await svc.list(page=2, limit=2)
        assert len(items) == 2
        assert meta["total"] == 5

    @pytest.mark.asyncio
    async def test_delete(self, db: AsyncSession) -> None:
        svc = WorldSvc(db)
        created = await svc.create(WORLD_INPUT)
        deleted_id = await svc.delete(str(created["id"]))
        assert deleted_id == str(created["id"])
        with pytest.raises(NotFoundError):
            await svc.get(str(created["id"]))

    @pytest.mark.asyncio
    async def test_delete_missing_raises(self, db: AsyncSession) -> None:
        with pytest.raises(NotFoundError):
            await WorldSvc(db).delete("00000000-0000-0000-0000-000000000000")


# --------------------------------------------------------------------------- #
# 剧情会话创建（create 分派）
# --------------------------------------------------------------------------- #
class TestCreateDispatch:
    @pytest.mark.asyncio
    async def test_without_world_id_stays_rpg(
        self, db: AsyncSession, card_and_preset: tuple
    ) -> None:
        from app.services.session import SessionSvc

        card_id, preset_id = card_and_preset
        created = await SessionSvc(db).create(
            {"character_card_id": str(card_id), "preset_id": str(preset_id)}
        )
        assert created["spec"] == "rpg_session"
        assert created["world_id"] is None
        # 1v1 保留开场白（first_mes）
        assert created["messages"][0]["content"] == "风铃轻响。"

    @pytest.mark.asyncio
    async def test_with_world_id_creates_story_session(
        self, db: AsyncSession, card_and_preset: tuple
    ) -> None:
        from app.services.session import SessionSvc
        from app.services.story_state import STORY_SPEC, StoryStateSvc

        card_id, preset_id = card_and_preset
        world = await WorldSvc(db).create(WORLD_INPUT)

        created = await SessionSvc(db).create(
            {
                "character_card_id": str(card_id),
                "preset_id": str(preset_id),
                "world_id": world["id"],
            }
        )
        assert created["spec"] == STORY_SPEC
        assert str(created["world_id"]) == str(world["id"])
        assert created["title"] == "雨巷旧案"

        row = await SessionSvc(db).get_row(str(created["id"]))
        # cast / relations 必须已固化
        assert [c["id"] for c in StoryStateSvc.get_cast(row)] == ["su_wan", "lin_jiu"]
        assert StoryStateSvc.get_relations(row)[0]["kind"] == "旧识"
        assert StoryStateSvc.extract_world_id(row) == str(world["id"])

    @pytest.mark.asyncio
    async def test_story_session_scene_seeded_from_world(
        self, db: AsyncSession, card_and_preset: tuple
    ) -> None:
        from app.services.session import SessionSvc
        from app.services.story_state import StoryStateSvc

        card_id, preset_id = card_and_preset
        world = await WorldSvc(db).create(WORLD_INPUT)
        created = await SessionSvc(db).create(
            {"character_card_id": str(card_id), "preset_id": str(preset_id),
             "world_id": world["id"]}
        )
        row = await SessionSvc(db).get_row(str(created["id"]))
        scene = StoryStateSvc.get_scene_story(row)
        assert scene["mood"] == "阴冷、克制"
        # present 取 cast 前 3 位
        assert scene["present"] == ["su_wan", "lin_jiu"]

    @pytest.mark.asyncio
    async def test_story_opening_message_has_beat_role(
        self, db: AsyncSession, card_and_preset: tuple
    ) -> None:
        from app.services.session import SessionSvc

        card_id, preset_id = card_and_preset
        world = await WorldSvc(db).create(WORLD_INPUT)
        created = await SessionSvc(db).create(
            {"character_card_id": str(card_id), "preset_id": str(preset_id),
             "world_id": world["id"]}
        )
        messages = created["messages"]
        assert messages, "序幕必须至少落一条消息"
        assert all(m["meta"]["beat_role"] == "opening" for m in messages)
        assert all(m["role"] == "assistant" for m in messages)
        # 无 LLM（沙箱无上游）→ 走降级：world.opening + card.first_mes
        assert messages[0]["content"] == "雨敲着铁皮棚。"

    @pytest.mark.asyncio
    async def test_story_opening_seq_monotonic(
        self, db: AsyncSession, card_and_preset: tuple
    ) -> None:
        from app.services.session import SessionSvc

        card_id, preset_id = card_and_preset
        world = await WorldSvc(db).create(WORLD_INPUT)
        svc = SessionSvc(db)
        created = await svc.create(
            {"character_card_id": str(card_id), "preset_id": str(preset_id),
             "world_id": world["id"]}
        )
        import uuid as _uuid

        uid = created["id"] if isinstance(created["id"], _uuid.UUID) else _uuid.UUID(str(created["id"]))
        rows = await svc.list_messages(uid)
        seqs = [r.seq for r in rows]
        assert seqs == sorted(seqs)
        assert len(seqs) == len(set(seqs))

    @pytest.mark.asyncio
    async def test_missing_world_raises(
        self, db: AsyncSession, card_and_preset: tuple
    ) -> None:
        from app.services.session import SessionSvc

        card_id, preset_id = card_and_preset
        with pytest.raises(NotFoundError):
            await SessionSvc(db).create(
                {"character_card_id": str(card_id), "preset_id": str(preset_id),
                 "world_id": "00000000-0000-0000-0000-000000000000"}
            )

    @pytest.mark.asyncio
    async def test_world_deleted_mid_story_keeps_session(
        self, db: AsyncSession, card_and_preset: tuple
    ) -> None:
        """世界观被删后：会话保留（SET NULL 语义），固化副本仍可用。"""
        from app.services.session import SessionSvc
        from app.services.story_state import StoryStateSvc

        card_id, preset_id = card_and_preset
        world_svc = WorldSvc(db)
        world = await world_svc.create(WORLD_INPUT)
        created = await SessionSvc(db).create(
            {"character_card_id": str(card_id), "preset_id": str(preset_id),
             "world_id": world["id"]}
        )
        await world_svc.delete(world["id"])
        await db.flush()

        row = await SessionSvc(db).get_row(str(created["id"]))
        # 固化副本仍在，剧情可继续
        assert len(StoryStateSvc.get_cast(row)) == 2
        # extensions 里仍记得原 world_id（用于展示来源）
        assert StoryStateSvc.extract_world_id(row) == str(world["id"])
