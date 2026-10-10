"""运行时 M1 的数据库级单测（sqlite + aiosqlite，无需真实 PostgreSQL）。

建表夹具 `db` 与工厂 `card_and_preset` 见 tests/conftest.py；
本文件只验证 SessionSvc / ConfigSvc 的真实 SQL 行为。
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


# --------------------------------------------------------------------------- #
# SessionSvc
# --------------------------------------------------------------------------- #
async def test_session_create_with_greeting(
    db: AsyncSession, card_and_preset: tuple
) -> None:
    from app.services.session import SessionSvc

    card_id, preset_id = card_and_preset
    svc = SessionSvc(db)
    data = await svc.create(
        {
            "character_card_id": str(card_id),
            "preset_id": str(preset_id),
            "worldbook_ids": [],
            "user_persona": {"name": "阿明"},
            "greeting_index": -1,
        }
    )
    assert data["status"] == "active"
    assert data["state_machine"]["current"] == "idle"
    assert data["messages"][0]["content"] == "风铃轻响。"
    assert data["messages"][0]["meta"]["greeting_index"] == -1


async def test_session_optimistic_lock_conflict(
    db: AsyncSession, card_and_preset: tuple
) -> None:
    from app.core.errors import ConflictError
    from app.services.session import SessionSvc

    card_id, preset_id = card_and_preset
    svc = SessionSvc(db)
    created = await svc.create(
        {"character_card_id": str(card_id), "preset_id": str(preset_id), "greeting_index": -1}
    )
    sid = created["id"]
    # 第一次更新：版本 0 -> 1
    await svc.update(str(sid), {"title": "改标题"})
    # 用陈旧版本号 0 再更新 -> 409
    with pytest.raises(ConflictError):
        await svc.update(str(sid), {"title": "并发改", "version": 0})


async def test_session_illegal_status_transition(
    db: AsyncSession, card_and_preset: tuple
) -> None:
    from app.core.errors import ConflictError
    from app.services.session import SessionSvc

    card_id, preset_id = card_and_preset
    svc = SessionSvc(db)
    created = await svc.create(
        {"character_card_id": str(card_id), "preset_id": str(preset_id), "greeting_index": -1}
    )
    sid = str(created["id"])
    await svc.update(sid, {"status": "archived"})
    with pytest.raises(ConflictError):
        await svc.update(sid, {"status": "paused"})


async def test_session_fork_copies_history_without_touching_source(
    db: AsyncSession, card_and_preset: tuple
) -> None:
    from app.services.session import SessionSvc

    card_id, preset_id = card_and_preset
    svc = SessionSvc(db)
    created = await svc.create(
        {"character_card_id": str(card_id), "preset_id": str(preset_id), "greeting_index": -1}
    )
    sid = created["id"]
    row = await svc.get_row(str(sid))
    await svc.append_message(row.id, role="user", content="第一句")
    await svc.append_message(row.id, role="assistant", content="第二句")

    forked = await svc.fork(str(sid), {"title": "分支A"})
    assert forked["id"] != sid
    assert forked["title"] == "分支A"
    assert [m["content"] for m in forked["messages"]][-2:] == ["第一句", "第二句"]
    source = await svc.get(str(sid))
    assert len(source["messages"]) == 3


async def test_session_fork_from_message_id(
    db: AsyncSession, card_and_preset: tuple
) -> None:
    from app.services.session import SessionSvc

    card_id, preset_id = card_and_preset
    svc = SessionSvc(db)
    created = await svc.create(
        {"character_card_id": str(card_id), "preset_id": str(preset_id), "greeting_index": -1}
    )
    row = await svc.get_row(created["id"])
    m1 = await svc.append_message(row.id, role="user", content="A")
    await svc.append_message(row.id, role="assistant", content="B")

    forked = await svc.fork(str(created["id"]), {"from_message_id": str(m1.id)})
    # 只复制到 m1（含）：开场白 + A
    assert [m["content"] for m in forked["messages"]] == ["风铃轻响。", "A"]


async def test_session_delete_removes_session(
    db: AsyncSession, card_and_preset: tuple
) -> None:
    from sqlalchemy import func, select

    from app.models.session import Session as SessionRow
    from app.services.session import SessionSvc

    card_id, preset_id = card_and_preset
    svc = SessionSvc(db)
    created = await svc.create(
        {"character_card_id": str(card_id), "preset_id": str(preset_id), "greeting_index": -1}
    )
    count_before = (
        await db.execute(select(func.count()).select_from(SessionRow))
    ).scalar_one()
    await svc.delete(str(created["id"]))
    count_after = (
        await db.execute(select(func.count()).select_from(SessionRow))
    ).scalar_one()
    assert count_after == count_before - 1


# --------------------------------------------------------------------------- #
# ConfigSvc
# --------------------------------------------------------------------------- #
async def test_config_llm_masks_and_persists(db: AsyncSession) -> None:
    from app.services.config import ConfigSvc

    svc = ConfigSvc(db)
    saved = await svc.set_llm(
        {
            "provider": "openai_compatible",
            "base_url": "https://api.example.com/v1",
            "api_key": "sk-abcdefghijk",
            "model": "gpt-x",
        }
    )
    assert saved["api_key"] == "sk-***ijk"  # 回写即脱敏

    raw = await svc.get_llm_raw()
    assert raw["api_key"] == "sk-abcdefghijk"

    public = await svc.get_llm()
    assert public["api_key"] == "sk-***ijk"


async def test_config_keeps_key_when_masked_placeholder_sent(db: AsyncSession) -> None:
    from app.services.config import ConfigSvc

    svc = ConfigSvc(db)
    await svc.set_llm({"base_url": "u", "api_key": "sk-realkeyvalue", "model": "m"})
    # 前端回传脱敏占位：保留旧明文，不把 *** 写进去
    await svc.set_llm({"base_url": "u2", "api_key": "sk-***lue", "model": "m"})
    raw = await svc.get_llm_raw()
    assert raw["api_key"] == "sk-realkeyvalue"
    assert raw["base_url"] == "u2"


async def test_config_moderation_defaults(db: AsyncSession) -> None:
    from app.services.config import ConfigSvc

    data = await ConfigSvc(db).get_moderation()
    assert data["enabled"] is True
    assert data["provider"] == "builtin_wordlist"


async def test_config_image_masks(db: AsyncSession) -> None:
    from app.services.config import ConfigSvc

    svc = ConfigSvc(db)
    saved = await svc.set_image({"provider": "cloud", "base_url": "u", "api_key": "abcdefghixyz"})
    assert saved["api_key"] == "abc***xyz"
