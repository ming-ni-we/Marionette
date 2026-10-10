"""消息表（SPEC §6 `messages`）。

`UNIQUE(session_id, seq)` 是流式落库与恢复的基石：seq 会话内单调递增，
重复写入同一 seq 即为幂等检查点（架构 §4.3）。
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class Message(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "messages"

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user/assistant/system/tool
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    # streaming / complete / incomplete
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="complete")
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 命中条目 / 图资产 id / swipe 信息（schemas.md §6.4 meta）
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_messages_session_seq"),
    )
