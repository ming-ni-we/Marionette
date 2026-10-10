"""世界书表（SPEC §6 `worldbooks`）。

一条世界书 = 一本知识条目集，条目列表存在 `data.entries`。
一卡可绑多本（N:M 通过 card.data.extensions.rpg.default_worldbook_ids 与 session.worldbook_ids 表达），
故不建独立关联表。
"""

from __future__ import annotations

from sqlalchemy import Index, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class WorldBook(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "worldbooks"

    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, server_default="local")
    name: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    spec: Mapped[str] = mapped_column(String(32), nullable=False, server_default="rpg_worldbook")
    spec_version: Mapped[str] = mapped_column(String(16), nullable=False, server_default="1.0")
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    extensions: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )

    __table_args__ = (
        Index(
            "ix_worldbooks_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index("ix_worldbooks_tags_gin", "tags", postgresql_using="gin"),
        Index("ix_worldbooks_owner_updated", "owner_id", text("updated_at DESC")),
    )
