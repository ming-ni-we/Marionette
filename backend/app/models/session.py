"""会话表（SPEC §6 `sessions`）。

状态机、场景、记忆都以 JSONB 落在此表（权威状态在库，不在内存 —— 架构 §4.3）。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class Session(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "sessions"

    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, server_default="local")
    # 角色卡被删时会话保留（历史可导出），故 SET NULL
    card_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cards.id", ondelete="SET NULL"),
        nullable=True,
    )
    preset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("presets.id", ondelete="SET NULL"),
        nullable=True,
    )
    # 剧情模式下绑定的世界；世界观被删时会话保留（SET NULL），退化为只读历史
    world_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("worlds.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    # 挂载的世界书 id 列表（可含卡内书）
    worldbook_ids: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    user_persona: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    state_machine: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    scene: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    memory: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    triggered_entries: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    spec: Mapped[str] = mapped_column(String(32), nullable=False, server_default="rpg_session")
    spec_version: Mapped[str] = mapped_column(String(16), nullable=False, server_default="1.0")
    extensions: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    # 会话列表支持 sort=last_message_at
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_sessions_owner_updated", "owner_id", text("updated_at DESC")),
        Index("ix_sessions_card_id", "card_id"),
        Index("ix_sessions_world_id", "world_id"),
        Index("ix_sessions_owner_status", "owner_id", "status"),
    )
