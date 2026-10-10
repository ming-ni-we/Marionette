"""记忆快照表（SPEC §6 `memory_snapshots`）：滚动摘要的版本化历史。"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, Integer, Text, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class MemorySnapshot(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "memory_snapshots"

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    up_to_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    facts: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))

    __table_args__ = (
        Index("ix_memory_snapshots_session_upto", "session_id", text("up_to_seq DESC")),
    )
