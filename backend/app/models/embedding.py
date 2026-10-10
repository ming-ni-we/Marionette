"""向量表（SPEC §6 `content_embeddings`）。

v1 只建表 + 建 HNSW 索引，**不写入、不查询**（F14 向量检索默认关闭）。
维度锚定 1024（bge-large-zh-v1.5，架构 §3.13），二期开启时无需迁移。
"""

from __future__ import annotations

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, Integer, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey

EMBEDDING_DIM = 1024


class ContentEmbedding(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "content_embeddings"

    # card / worldbook_entry / message / memory_fact
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    chunk_idx: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    __table_args__ = (
        Index("ix_content_embeddings_entity", "entity_type", "entity_id"),
        Index(
            "ix_content_embeddings_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
