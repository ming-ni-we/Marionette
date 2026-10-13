"""worlds table + sessions.world_id (剧情引擎)

Revision ID: 0002_worlds
Revises: 0001_initial_schema
Create Date: 2026-10-12

剧情引擎（多角色 AI 导演）的数据基础：
  - 新建 `worlds` 表承载世界观 / 势力 / 角色群 / 关系图 / 剧情大纲
  - `sessions` 新增 `world_id` 外键（SET NULL，世界观删除后剧情会话保留）

兼容性：纯新增，不改动任何既有列；旧会话 `world_id` 为 NULL，走原有 1v1 路径。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_worlds"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
TEXT_ARRAY = postgresql.ARRAY(sa.Text())


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    # ------------------------------------------------------------------- worlds
    op.create_table(
        "worlds",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False, server_default=sa.text("'local'")),
        sa.Column("title", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("spec", sa.String(32), nullable=False, server_default=sa.text("'rpg_world'")),
        sa.Column("spec_version", sa.String(16), nullable=False, server_default=sa.text("'1.0'")),
        # 世界观核心设定
        sa.Column("setting", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        # 势力 / 角色群 / 关系图
        sa.Column("factions", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("cast", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("relations", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        # 剧情大纲 / 开场白
        sa.Column("outline", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("opening", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("extensions", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("tags", TEXT_ARRAY, nullable=False, server_default=sa.text("'{}'::text[]")),
        *_timestamps(),
    )
    # 中文子串检索（与 cards / worldbooks 同策略，ADR-005）
    op.execute("CREATE INDEX ix_worlds_title_trgm ON worlds USING gin (title gin_trgm_ops)")
    op.execute("CREATE INDEX ix_worlds_tags_gin ON worlds USING gin (tags)")
    op.execute("CREATE INDEX ix_worlds_owner_updated ON worlds (owner_id, updated_at DESC)")

    # -------------------------------------------- sessions.world_id（剧情会话关联）
    op.add_column("sessions", sa.Column("world_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_sessions_world_id_worlds",
        "sessions",
        "worlds",
        ["world_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_sessions_world_id", "sessions", ["world_id"])


def downgrade() -> None:
    op.drop_index("ix_sessions_world_id", table_name="sessions")
    op.drop_constraint("fk_sessions_world_id_worlds", "sessions", type_="foreignkey")
    op.drop_column("sessions", "world_id")

    op.drop_index("ix_worlds_owner_updated", table_name="worlds")
    op.drop_index("ix_worlds_tags_gin", table_name="worlds")
    op.drop_index("ix_worlds_title_trgm", table_name="worlds")
    op.drop_table("worlds")
