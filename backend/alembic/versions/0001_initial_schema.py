"""initial schema: 10 tables + pg_trgm/vector extensions + all indexes

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-09

对应 SPEC §6 与 docs/spec/schemas.md。禁用 create_all，一切走本迁移。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1024
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
    # ---- 扩展：pg_trgm（中文子串/模糊检索，ADR-005）+ vector（pgvector，ADR-004）----
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ------------------------------------------------------------------ cards
    op.create_table(
        "cards",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False, server_default=sa.text("'local'")),
        sa.Column("name", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("spec", sa.String(32), nullable=False, server_default=sa.text("'rpg_card'")),
        sa.Column("spec_version", sa.String(16), nullable=False, server_default=sa.text("'1.0'")),
        sa.Column("data", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("extensions", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("tags", TEXT_ARRAY, nullable=False, server_default=sa.text("'{}'::text[]")),
        *_timestamps(),
    )
    op.execute(
        "CREATE INDEX ix_cards_name_trgm ON cards USING gin (name gin_trgm_ops)"
    )
    op.execute("CREATE INDEX ix_cards_tags_gin ON cards USING gin (tags)")
    op.execute("CREATE INDEX ix_cards_owner_updated ON cards (owner_id, updated_at DESC)")

    # -------------------------------------------------------------- worldbooks
    op.create_table(
        "worldbooks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False, server_default=sa.text("'local'")),
        sa.Column("name", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("spec", sa.String(32), nullable=False, server_default=sa.text("'rpg_worldbook'")),
        sa.Column("spec_version", sa.String(16), nullable=False, server_default=sa.text("'1.0'")),
        sa.Column("data", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("extensions", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("tags", TEXT_ARRAY, nullable=False, server_default=sa.text("'{}'::text[]")),
        *_timestamps(),
    )
    op.execute(
        "CREATE INDEX ix_worldbooks_name_trgm ON worldbooks USING gin (name gin_trgm_ops)"
    )
    op.execute("CREATE INDEX ix_worldbooks_tags_gin ON worldbooks USING gin (tags)")
    op.execute(
        "CREATE INDEX ix_worldbooks_owner_updated ON worldbooks (owner_id, updated_at DESC)"
    )

    # ----------------------------------------------------------------- presets
    op.create_table(
        "presets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False, server_default=sa.text("'local'")),
        sa.Column("name", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("spec", sa.String(32), nullable=False, server_default=sa.text("'rpg_preset'")),
        sa.Column("spec_version", sa.String(16), nullable=False, server_default=sa.text("'1.0'")),
        sa.Column("data", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("extensions", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
    )
    op.execute(
        "CREATE INDEX ix_presets_name_trgm ON presets USING gin (name gin_trgm_ops)"
    )
    op.execute("CREATE INDEX ix_presets_owner_updated ON presets (owner_id, updated_at DESC)")

    # ---------------------------------------------------------------- sessions
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False, server_default=sa.text("'local'")),
        sa.Column("card_id", sa.Uuid(), sa.ForeignKey("cards.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "preset_id", sa.Uuid(), sa.ForeignKey("presets.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("worldbook_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("user_persona", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("state_machine", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("scene", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("memory", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("triggered_entries", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("context", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("spec", sa.String(32), nullable=False, server_default=sa.text("'rpg_session'")),
        sa.Column("spec_version", sa.String(16), nullable=False, server_default=sa.text("'1.0'")),
        sa.Column("extensions", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.execute("CREATE INDEX ix_sessions_owner_updated ON sessions (owner_id, updated_at DESC)")
    op.execute("CREATE INDEX ix_sessions_card_id ON sessions (card_id)")
    op.execute("CREATE INDEX ix_sessions_owner_status ON sessions (owner_id, status)")

    # ---------------------------------------------------------------- messages
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'complete'")),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("meta", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
        sa.UniqueConstraint("session_id", "seq", name="uq_messages_session_seq"),
    )

    # -------------------------------------------------------- memory_snapshots
    op.create_table(
        "memory_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("up_to_seq", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("facts", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        *_timestamps(),
    )
    op.execute(
        "CREATE INDEX ix_memory_snapshots_session_upto "
        "ON memory_snapshots (session_id, up_to_seq DESC)"
    )

    # ------------------------------------------------------ content_embeddings
    # v1 只建表 + HNSW 索引，不写入不查询（F14 默认关闭）
    op.create_table(
        "content_embeddings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_idx", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("content", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        *_timestamps(),
    )
    op.execute(
        "CREATE INDEX ix_content_embeddings_entity ON content_embeddings (entity_type, entity_id)"
    )
    op.execute(
        "CREATE INDEX ix_content_embeddings_embedding_hnsw "
        "ON content_embeddings USING hnsw (embedding vector_cosine_ops)"
    )

    # -------------------------------------------------------------- image_jobs
    op.create_table(
        "image_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "session_id", sa.Uuid(), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "card_id", sa.Uuid(), sa.ForeignKey("cards.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("provider", sa.String(32), nullable=False, server_default=sa.text("'cloud'")),
        sa.Column("prompt_id", sa.String(128), nullable=True),
        sa.Column("asset_id", sa.Uuid(), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("error", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.execute("CREATE INDEX ix_image_jobs_status ON image_jobs (status)")
    op.execute("CREATE INDEX ix_image_jobs_session_id ON image_jobs (session_id)")

    # ------------------------------------------------------------------ assets
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False, server_default=sa.text("'local'")),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("content_type", sa.String(128), nullable=False, server_default=sa.text("''")),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column(
            "card_id", sa.Uuid(), sa.ForeignKey("cards.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "session_id", sa.Uuid(), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("tags", TEXT_ARRAY, nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("meta", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
    )
    op.execute("CREATE INDEX ix_assets_card_id_created ON assets (card_id, created_at DESC)")
    op.execute("CREATE INDEX ix_assets_tags_gin ON assets USING gin (tags)")
    op.execute("CREATE INDEX ix_assets_session_id ON assets (session_id)")

    # -------------------------------------------------------------- app_config
    op.create_table(
        "app_config",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
    )


def downgrade() -> None:
    op.drop_table("app_config")
    op.drop_table("assets")
    op.drop_table("image_jobs")
    op.drop_table("content_embeddings")
    op.drop_table("memory_snapshots")
    op.drop_table("messages")
    op.drop_table("sessions")
    op.drop_table("presets")
    op.drop_table("worldbooks")
    op.drop_table("cards")
    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
