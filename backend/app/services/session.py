"""会话引擎服务：状态机 + 消息流 + 中断恢复（架构 §4.3 / schemas.md §6）。

职责：
  - 会话创建 / 获取 / 列表 / 归档 / 删除 / 分支（fork）
  - 显式状态迁移表：非法迁移抛 ConflictError（HTTP 409）
  - 乐观锁：state_machine.version 不匹配时拒绝写入并返回 409（防并发双击）
  - 消息落库与 seq 单调递增（UNIQUE(session_id, seq) 是流式恢复基石）
  - 服务重启回收滞留的 streaming 消息（主入口 lifespan 已调用）

分层铁律：本服务只依赖 ORM 模型与 Schema，不 import FastAPI req/res，也不 import 厂商 SDK。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.core.ids import parse_uuid
from app.core.logging import get_logger
from app.models.card import Card
from app.models.message import Message as MessageRow
from app.models.preset import Preset
from app.models.session import Session as SessionRow
from app.services.tokens import estimate_tokens

logger = get_logger(__name__)

# 会话生命周期状态（schemas.md §6.1）
SESSION_STATUSES: frozenset[str] = frozenset({"active", "paused", "archived"})

# 会话级状态迁移表（schemas.md §6.2「合法迁移」）。键为源状态，值为允许的目标集合。
# 注意：这与 state_machine.current 的运行时迁移是**两套**语义：
#   本节管的是会话外壳的 status（active/paused/archived）；
#   state_machine.current 管的是单轮生成的状态流转（见 STATE_MACHINE_TRANSITIONS）。
SESSION_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "active": frozenset({"paused", "archived"}),
    "paused": frozenset({"active", "archived"}),
    "archived": frozenset({"active"}),  # 归档后允许「恢复」
}

# 单轮生成状态机迁移表（schemas.md §6.2）
STATE_MACHINE_TRANSITIONS: dict[str, frozenset[str]] = {
    "idle": frozenset({"assembling"}),
    "assembling": frozenset({"generating", "error", "idle"}),
    "generating": frozenset({"post_processing", "interrupted", "error"}),
    "post_processing": frozenset({"idle", "error"}),
    "interrupted": frozenset({"idle", "assembling"}),
    "error": frozenset({"idle", "assembling"}),
}

# 默认的 state_machine 初值
_DEFAULT_STATE_MACHINE: dict[str, Any] = {
    "current": "idle",
    "turn": 0,
    "version": 0,
    "last_error": None,
}


def _now() -> datetime:
    return datetime.now(UTC)


class SessionSvc:
    """会话生命周期与状态机编排（架构 §4.3）。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------ #
    # 序列化
    # ------------------------------------------------------------------ #
    @staticmethod
    def _message_to_dict(row: MessageRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "role": row.role,
            "content": row.content,
            "status": row.status,
            "token_count": row.token_count,
            "created_at": row.created_at,
            "meta": row.meta or {},
        }

    def serialize(self, row: SessionRow, *, messages: list[MessageRow] | None = None) -> dict[str, Any]:
        """把 ORM 行转成 Session schema 可消费的 dict。messages 由调用方按需传入。"""
        return {
            "id": row.id,
            "spec": row.spec,
            "spec_version": row.spec_version,
            "character_card_id": row.card_id,
            "preset_id": row.preset_id,
            "world_id": row.world_id,
            "worldbook_ids": list(row.worldbook_ids or []),
            "user_persona": row.user_persona or {},
            "status": row.status,
            "title": row.title,
            "state_machine": {**_DEFAULT_STATE_MACHINE, **(row.state_machine or {})},
            "scene": row.scene or {},
            "messages": [self._message_to_dict(m) for m in (messages or [])],
            "triggered_entries": row.triggered_entries or {},
            "memory": row.memory or {"rolling_summary": "", "summary_upto_message_id": None, "facts": []},
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    # ------------------------------------------------------------------ #
    # 读
    # ------------------------------------------------------------------ #
    async def get_row(self, session_id: str | uuid.UUID) -> SessionRow:
        uid = parse_uuid(session_id, field="sessionId")
        row = (
            await self._db.execute(select(SessionRow).where(SessionRow.id == uid))
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError(f"会话（id={uid}）不存在或已被删除。")
        return row

    async def list_messages(self, session_id: uuid.UUID) -> list[MessageRow]:
        rows = (
            await self._db.execute(
                select(MessageRow)
                .where(MessageRow.session_id == session_id)
                .order_by(MessageRow.seq.asc())
            )
        ).scalars().all()
        return list(rows)

    async def get(self, session_id: str, *, include_messages: bool = True) -> dict[str, Any]:
        row = await self.get_row(session_id)
        messages = await self.list_messages(row.id) if include_messages else None
        return self.serialize(row, messages=messages)

    async def list(
        self, *, q: str | None, status: str | None, page: int, limit: int
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """会话列表（不返回 messages，避免列表接口过重）。"""
        from app.services.search import build_page

        stmt = select(SessionRow)
        if status:
            stmt = stmt.where(SessionRow.status == status)
        if q:
            stmt = stmt.where(SessionRow.title.ilike(f"%{q}%"))
        total = int(
            (await self._db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
            or 0
        )
        page, limit = max(1, page), max(1, min(100, limit))
        rows = (
            await self._db.execute(
                stmt.order_by(SessionRow.updated_at.desc(), SessionRow.id.asc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).scalars().all()
        return [self.serialize(r) for r in rows], build_page(page, limit, total)

    # ------------------------------------------------------------------ #
    # 写：创建
    # ------------------------------------------------------------------ #
    async def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        """创建会话。

        `payload["world_id"]` 存在 → 走**剧情模式**（`spec="story_session"`，
        由 `create_story_session` 接管：固化世界观、生成序幕）；
        缺省 → 原有 1v1 行为，**一字节未改**。
        """
        if payload.get("world_id"):
            return await self.create_story_session(payload)
        return await self._create_rpg_session(payload)

    async def _create_rpg_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        card_id = parse_uuid(payload.get("character_card_id"), field="character_card_id")
        preset_id = parse_uuid(payload.get("preset_id"), field="preset_id")

        card = (
            await self._db.execute(select(Card).where(Card.id == card_id))
        ).scalar_one_or_none()
        if card is None:
            raise NotFoundError("角色卡不存在，无法开启会话。")
        preset = (
            await self._db.execute(select(Preset).where(Preset.id == preset_id))
        ).scalar_one_or_none()
        if preset is None:
            raise NotFoundError("预设不存在，无法开启会话。")

        worldbook_ids = [str(w) for w in (payload.get("worldbook_ids") or [])]
        persona = payload.get("user_persona") or {}
        title = payload.get("title") or (card.data or {}).get("name") or "未命名会话"

        row = SessionRow(
            owner_id="local",
            card_id=card_id,
            preset_id=preset_id,
            title=title,
            status="active",
            worldbook_ids=worldbook_ids,
            user_persona=persona,
            state_machine=dict(_DEFAULT_STATE_MACHINE),
            scene={},
            memory={"rolling_summary": "", "summary_upto_message_id": None, "facts": []},
            triggered_entries={},
            context={},
            spec="rpg_session",
            spec_version="1.0",
            extensions={},
        )
        self._db.add(row)
        await self._db.flush()
        await self._db.refresh(row)

        # 开场白：按 greeting_index 取 first_mes（-1）或 alternate_greetings[i]
        greeting = self._pick_greeting(card.data or {}, int(payload.get("greeting_index", -1)))
        messages: list[MessageRow] = []
        if greeting:
            messages.append(
                await self.append_message(
                    row.id,
                    role="assistant",
                    content=greeting,
                    meta={"greeting_index": int(payload.get("greeting_index", -1))},
                    touch=False,
                )
            )
        logger.info("session created", extra={"session": str(row.id), "card": str(card_id)})
        return self.serialize(row, messages=messages or None)

    @staticmethod
    def _pick_greeting(card_data: dict[str, Any], index: int) -> str:
        if index == -1:
            return str(card_data.get("first_mes") or "")
        greetings = card_data.get("alternate_greetings") or []
        if 0 <= index < len(greetings):
            return str(greetings[index])
        return str(card_data.get("first_mes") or "")

    # ------------------------------------------------------------------ #
    # 写：创建剧情会话（剧情引擎）
    # ------------------------------------------------------------------ #
    async def create_story_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        """创建剧情会话：绑定世界观 + 固化 cast/relations + 生成序幕。

        与 1v1 创建的三点差异：
          1. `spec = "story_session"`（模式开关，ChatSvc 据此分派）
          2. `world_id` 落列，并把世界的 cast/relations **固化副本**写进
             `extensions.story`（避免每轮回查 worlds 表，也让世界观被改/删后剧情自洽）
          3. 序幕由 `OpeningSvc` 生成（LLM 或降级文案），逐段落库为 assistant 消息

        序幕落库放在**这里**而不是 OpeningSvc 内，是为了让 `seq` 单调递增的
        唯一维护者仍是本服务（流式恢复的基石）。
        """
        from app.models.world import World
        from app.services.opening import OpeningSvc

        card_id = parse_uuid(payload.get("character_card_id"), field="character_card_id")
        preset_id = parse_uuid(payload.get("preset_id"), field="preset_id")
        world_id = parse_uuid(payload.get("world_id"), field="world_id")

        card = (
            await self._db.execute(select(Card).where(Card.id == card_id))
        ).scalar_one_or_none()
        if card is None:
            raise NotFoundError("角色卡不存在，无法开启剧情。")
        preset = (
            await self._db.execute(select(Preset).where(Preset.id == preset_id))
        ).scalar_one_or_none()
        if preset is None:
            raise NotFoundError("预设不存在，无法开启剧情。")
        world = (
            await self._db.execute(select(World).where(World.id == world_id))
        ).scalar_one_or_none()
        if world is None:
            raise NotFoundError("世界观不存在，无法开启剧情。")

        cast = list(world.cast or [])
        relations = list(world.relations or [])
        scene = {
            "location": "",
            "time": "",
            "mood": str((world.setting or {}).get("tone") or ""),
            "summary": str((world.setting or {}).get("summary") or ""),
            "present": [str(c.get("id")) for c in cast[:3] if isinstance(c, dict) and c.get("id")],
        }

        row = SessionRow(
            owner_id="local",
            card_id=card_id,
            preset_id=preset_id,
            world_id=world_id,
            title=payload.get("title") or world.title or "未命名剧情",
            status="active",
            worldbook_ids=[str(w) for w in (payload.get("worldbook_ids") or [])],
            user_persona=payload.get("user_persona") or {},
            state_machine=dict(_DEFAULT_STATE_MACHINE),
            scene=scene,
            memory={"rolling_summary": "", "summary_upto_message_id": None, "facts": []},
            triggered_entries={},
            context={},
            spec="story_session",
            spec_version="1.0",
            extensions={},
        )
        # 固化世界观副本（cast / relations 深拷贝进 extensions.story）
        from app.services.story_state import StoryStateSvc

        StoryStateSvc(self._db).bind_world(
            row, world_id=str(world.id), cast=cast, relations=relations
        )
        self._db.add(row)
        await self._db.flush()
        await self._db.refresh(row)

        # ---- 序幕：生成草稿 -> 逐段落库 ----
        opening_svc = OpeningSvc(self._db)
        drafts = await opening_svc.generate(
            world={
                "id": str(world.id),
                "title": world.title,
                "setting": dict(world.setting or {}),
                "factions": list(world.factions or []),
                "outline": dict(world.outline or {}),
                "opening": world.opening or "",
            },
            card=dict(card.data or {}),
            preset=dict(preset.data or {}),
            cast=cast,
            user_persona=dict(row.user_persona or {}),
            overrides=(payload.get("overrides") or None),
        )

        messages: list[MessageRow] = []
        for draft in drafts:
            messages.append(
                await self.append_message(
                    row.id,
                    role=str(draft.get("role") or "assistant"),
                    content=str(draft.get("content") or ""),
                    token_count=estimate_tokens(str(draft.get("content") or "")),
                    meta=dict(draft.get("meta") or {}),
                    touch=False,
                )
            )
        # 序幕落完统一刷一次 last_message_at（避免每段都查一次会话行）
        row.last_message_at = _now()
        await self._db.flush()
        # 必须 refresh：flush() 会把 row 上已加载的属性标记为 expired，
        # 而 serialize() 要读 updated_at 等列。async 环境下访问 expired 属性会在
        # greenlet 之外触发懒加载 IO -> MissingGreenlet（线上实测 500）。
        # _create_rpg_session 在 flush() 后同样有 refresh(row)，此处对齐。
        await self._db.refresh(row)
        logger.info(
            "story session created",
            extra={"session": str(row.id), "world": str(world_id), "opening_parts": len(messages)},
        )
        return self.serialize(row, messages=messages or None)

    # ------------------------------------------------------------------ #
    # 写：更新（含乐观锁 + 状态迁移校验）
    # ------------------------------------------------------------------ #
    async def update(self, session_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        row = await self.get_row(session_id)

        # 1) 会话外壳状态迁移校验
        new_status = patch.get("status")
        if new_status is not None and new_status != row.status:
            self.assert_session_transition(row.status, new_status)

        # 2) 乐观锁：若入参带 version 且与当前不符 -> 409
        sm = {**_DEFAULT_STATE_MACHINE, **(row.state_machine or {})}
        incoming_version = patch.get("version")
        if incoming_version is not None and int(incoming_version) != int(sm["version"]):
            raise ConflictError(
                "会话已被并发修改（版本号不匹配），请刷新后重试。",
                data={"expected_version": int(sm["version"])},
            )

        # 3) 应用变更
        if new_status is not None:
            row.status = new_status
        if patch.get("preset_id") is not None:
            row.preset_id = parse_uuid(patch["preset_id"], field="preset_id")
        if patch.get("worldbook_ids") is not None:
            row.worldbook_ids = [str(w) for w in patch["worldbook_ids"]]
        if patch.get("user_persona") is not None:
            row.user_persona = {**(row.user_persona or {}), **patch["user_persona"]}
        if patch.get("scene") is not None:
            row.scene = {**(row.scene or {}), **patch["scene"]}
        if patch.get("title") is not None:
            row.title = patch["title"]

        # 版本号前进一步（任何写入都使旧版本失效）
        sm["version"] = int(sm["version"]) + 1
        row.state_machine = sm

        await self._db.flush()
        await self._db.refresh(row)
        logger.info("session updated", extra={"session": str(row.id)})
        return self.serialize(row)

    async def archive(self, session_id: str) -> dict[str, Any]:
        """归档会话（active/paused -> archived）。"""
        return await self.update(session_id, {"status": "archived"})

    async def delete(self, session_id: str) -> str:
        row = await self.get_row(session_id)
        deleted_id = str(row.id)
        await self._db.delete(row)  # messages 由外键 ON DELETE CASCADE 级联
        await self._db.flush()
        logger.info("session deleted", extra={"session": deleted_id})
        return deleted_id

    # ------------------------------------------------------------------ #
    # 状态迁移
    # ------------------------------------------------------------------ #
    @staticmethod
    def assert_session_transition(current: str, target: str) -> None:
        if target not in SESSION_STATUSES:
            raise BadRequestError(f"未知的会话状态：{target}。")
        allowed = SESSION_STATUS_TRANSITIONS.get(current, frozenset())
        if target not in allowed and target != current:
            raise ConflictError(
                f"会话状态不允许从 {current} 迁移到 {target}。",
                data={"current": current, "target": target, "allowed": sorted(allowed)},
            )

    def transition_state(self, row: SessionRow, target: str, *, error: dict[str, Any] | None = None) -> None:
        """推进单轮状态机（state_machine.current），非法迁移抛 409。版本号 +1。"""
        sm = {**_DEFAULT_STATE_MACHINE, **(row.state_machine or {})}
        current = str(sm["current"])
        allowed = STATE_MACHINE_TRANSITIONS.get(current, frozenset())
        if target != current and target not in allowed:
            raise ConflictError(
                f"生成状态不允许从 {current} 迁移到 {target}。",
                data={"current": current, "target": target, "allowed": sorted(allowed)},
            )
        sm["current"] = target
        sm["version"] = int(sm["version"]) + 1
        sm["last_error"] = error
        row.state_machine = sm

    # ------------------------------------------------------------------ #
    # 消息
    # ------------------------------------------------------------------ #
    async def next_seq(self, session_id: uuid.UUID) -> int:
        current = (
            await self._db.execute(
                select(func.max(MessageRow.seq)).where(MessageRow.session_id == session_id)
            )
        ).scalar_one()
        return int(current or 0) + 1

    async def append_message(
        self,
        session_id: uuid.UUID,
        *,
        role: str,
        content: str,
        status: str = "complete",
        token_count: int | None = None,
        meta: dict[str, Any] | None = None,
        touch: bool = True,
    ) -> MessageRow:
        """追加一条消息。seq 会话内单调递增。"""
        seq = await self.next_seq(session_id)
        row = MessageRow(
            session_id=session_id,
            seq=seq,
            role=role,
            content=content,
            status=status,
            token_count=token_count,
            meta=meta or {},
        )
        self._db.add(row)
        if touch:
            await self._touch_session(session_id)
        await self._db.flush()
        await self._db.refresh(row)
        return row

    async def _touch_session(self, session_id: uuid.UUID) -> None:
        """更新会话的 last_message_at，便于列表按最近活跃排序。"""
        row = (
            await self._db.execute(select(SessionRow).where(SessionRow.id == session_id))
        ).scalar_one_or_none()
        if row is not None:
            row.last_message_at = _now()

    async def get_message(self, session_id: uuid.UUID, message_id: str) -> MessageRow:
        mid = parse_uuid(message_id, field="messageId")
        row = (
            await self._db.execute(
                select(MessageRow).where(
                    MessageRow.session_id == session_id, MessageRow.id == mid
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("消息不存在或不属于该会话。")
        return row

    async def update_message(
        self,
        row: MessageRow,
        *,
        content: str | None = None,
        status: str | None = None,
        token_count: int | None = None,
        meta: dict[str, Any] | None = None,
    ) -> MessageRow:
        if content is not None:
            row.content = content
        if status is not None:
            row.status = status
        if token_count is not None:
            row.token_count = token_count
        if meta is not None:
            row.meta = {**(row.meta or {}), **meta}
        await self._db.flush()
        await self._db.refresh(row)
        return row

    # ------------------------------------------------------------------ #
    # fork
    # ------------------------------------------------------------------ #
    async def fork(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """从指定消息（含）复制历史到一条新会话；原会话不动。"""
        source = await self.get_row(session_id)
        messages = await self.list_messages(source.id)

        from_message_id = payload.get("from_message_id")
        cutoff_seq: int | None = None
        if from_message_id:
            target = await self.get_message(source.id, str(from_message_id))
            cutoff_seq = target.seq
        copied = [m for m in messages if cutoff_seq is None or m.seq <= cutoff_seq]

        new_row = SessionRow(
            owner_id=source.owner_id,
            card_id=source.card_id,
            preset_id=source.preset_id,
            title=payload.get("title") or (source.title or "会话") + "（分支）",
            status="active",
            worldbook_ids=list(source.worldbook_ids or []),
            user_persona=dict(source.user_persona or {}),
            state_machine=dict(_DEFAULT_STATE_MACHINE),
            scene=dict(source.scene or {}),
            memory={"rolling_summary": "", "summary_upto_message_id": None, "facts": []},
            triggered_entries={},
            context={},
            spec=source.spec,
            spec_version=source.spec_version,
            extensions={"rpg": {"forked_from": str(source.id)}},
        )
        self._db.add(new_row)
        await self._db.flush()
        await self._db.refresh(new_row)

        for src in copied:
            self._db.add(
                MessageRow(
                    session_id=new_row.id,
                    seq=src.seq,
                    role=src.role,
                    content=src.content,
                    status=src.status if src.status != "streaming" else "complete",
                    token_count=src.token_count,
                    meta=dict(src.meta or {}),
                )
            )
        await self._db.flush()
        # 同 create_story_session：flush() 会 expire new_row，serialize() 读列属性
        # 会在 greenlet 之外触发懒加载 -> MissingGreenlet。这里必须先 refresh。
        await self._db.refresh(new_row)
        logger.info(
            "session forked", extra={"source": str(source.id), "fork": str(new_row.id)}
        )
        return self.serialize(new_row, messages=await self.list_messages(new_row.id))


__all__ = [
    "SESSION_STATUSES",
    "SESSION_STATUS_TRANSITIONS",
    "STATE_MACHINE_TRANSITIONS",
    "SessionSvc",
]
