"""角色卡表（SPEC §6 `cards`）。

索引：
  - GIN(name gin_trgm_ops)   中文子串/模糊检索（ADR-005）
  - GIN(tags)                标签多值筛选
  - (owner_id, updated_at DESC)  工作台默认排序
"""

from __future__ import annotations

from sqlalchemy import Index, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class Card(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "cards"

    owner_id: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="local"
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    spec: Mapped[str] = mapped_column(String(32), nullable=False, server_default="rpg_card")
    spec_version: Mapped[str] = mapped_column(String(16), nullable=False, server_default="1.0")
    # 内容主体（schemas.md §3 的 data 节点，含 ST V2 同名字段）
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    # 未知字段保全（ST 兼容）
    extensions: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    # data.tags 的反规范化副本，专供 GIN 索引与筛选
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )

    __table_args__ = (
        Index(
            "ix_cards_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index("ix_cards_tags_gin", "tags", postgresql_using="gin"),
        Index("ix_cards_owner_updated", "owner_id", text("updated_at DESC")),
    )
