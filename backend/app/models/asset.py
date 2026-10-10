"""资产表（SPEC §6 `assets`）。

资产要么归属角色（card_id），要么归属会话（session_id），也可都为空（游离资产）。
`storage_key` 是 AssetStore 的键（不是绝对路径），便于将来切对象存储。
"""

from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text, Uuid, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class Asset(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "assets"

    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, server_default="local")
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # avatar/gallery/background/generated
    filename: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    content_type: Mapped[str] = mapped_column(String(128), nullable=False, server_default="")
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    card_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cards.id", ondelete="SET NULL"), nullable=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    __table_args__ = (
        Index("ix_assets_card_id_created", "card_id", text("created_at DESC")),
        Index("ix_assets_tags_gin", "tags", postgresql_using="gin"),
        Index("ix_assets_session_id", "session_id"),
    )
