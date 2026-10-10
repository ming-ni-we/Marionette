"""单用户配置表（SPEC §6 `app_config`）：LLM 后端 / 审核层 / 出图配置。

密钥字段（api_key）只以密文或占位写入；读取时脱敏为 ***（ADR-010）。
"""

from __future__ import annotations

from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AppConfig(Base, TimestampMixin):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
