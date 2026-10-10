"""预设表（SPEC §6 `presets`）：采样参数 + 提示词模板 + 预算。"""

from __future__ import annotations

from sqlalchemy import Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class Preset(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "presets"

    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, server_default="local")
    name: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    spec: Mapped[str] = mapped_column(String(32), nullable=False, server_default="rpg_preset")
    spec_version: Mapped[str] = mapped_column(String(16), nullable=False, server_default="1.0")
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    extensions: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        Index(
            "ix_presets_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index("ix_presets_owner_updated", "owner_id", text("updated_at DESC")),
    )
