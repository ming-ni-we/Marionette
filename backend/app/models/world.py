"""世界表（剧情引擎）。

一条世界 = 一套完整的世界观设定 + 剧情大纲 + 角色群 + 关系图，
是「AI 导演驱动的多角色剧情引擎」的创作单元。

字段组织（对齐 WorldBook 的 spec/spec_version/data 模式）：
  - setting   时代背景 / 核心地点 / 世界规则 / 氛围基调
  - factions  势力列表（名称 / 立场 / 描述）
  - cast      角色群（id / name / role / voice / goals / card_id）
  - relations 角色关系图（from / to / kind / tension / note）
  - outline   剧情大纲（主线目标 / 关键节点 / 结局倾向）
  - opening   世界观开场白（手工填写；AI 生成留待三期）

一张世界可派生多个剧情会话（sessions.world_id 关联），
会话把 cast/relations/outline **固化副本**进自身 extensions，
避免每轮 LLM 调用都回查本表。
"""

from __future__ import annotations

from sqlalchemy import Index, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class World(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "worlds"

    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, server_default="local")
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    spec: Mapped[str] = mapped_column(String(32), nullable=False, server_default="rpg_world")
    spec_version: Mapped[str] = mapped_column(String(16), nullable=False, server_default="1.0")

    # 世界观核心设定：{era, locations[], rules[], tone, summary}
    setting: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    # 势力列表：[{id, name, stance, description}]
    factions: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    # 角色群：[{id, name, role, voice, goals[], card_id?}]
    cast: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    # 关系图：[{from, to, kind, tension, note}]
    relations: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    # 剧情大纲：{main_goal, nodes:[{id,title,brief,trigger}], endings[]}
    outline: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    # 开场白（世界观介绍正文）
    opening: Mapped[str] = mapped_column(Text, nullable=False, server_default="")

    extensions: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )

    __table_args__ = (
        # 中文子串检索（与 cards/worldbooks 同策略，ADR-005）
        Index(
            "ix_worlds_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index("ix_worlds_tags_gin", "tags", postgresql_using="gin"),
        Index("ix_worlds_owner_updated", "owner_id", text("updated_at DESC")),
    )
