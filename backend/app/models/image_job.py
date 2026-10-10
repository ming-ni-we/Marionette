"""出图任务表（SPEC §6 `image_jobs`）。

完成（status=done）时，**服务端**负责创建 kind=generated 的资产并登记进角色图集
（schemas.md §10.2 铁律；前端不得自行拼装）。
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class ImageJob(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "image_jobs"

    session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )
    card_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cards.id", ondelete="SET NULL"), nullable=True
    )
    # 关联消息（出图对话位置）。messages 与 image_jobs 无强依赖，故不设 FK。
    message_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="queued")
    provider: Mapped[str] = mapped_column(String(32), nullable=False, server_default="cloud")
    prompt_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_image_jobs_status", "status"),
        Index("ix_image_jobs_session_id", "session_id"),
    )
