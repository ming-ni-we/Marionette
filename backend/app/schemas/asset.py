"""资产与出图任务 Schema（schemas.md §10）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AssetKind = Literal["avatar", "gallery", "background", "generated"]
ImageJobStatus = Literal["queued", "running", "done", "failed"]


class Asset(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: UUID
    kind: AssetKind
    filename: str = ""
    content_type: str = ""
    size_bytes: int = 0
    card_id: UUID | None = None
    session_id: UUID | None = None
    message_id: UUID | None = None
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class ImageJobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt: str
    negative_prompt: str = ""
    width: int = 1024
    height: int = 1024
    seed: int = -1
    steps: int | None = None
    workflow_template_id: str | None = None
    card_id: UUID | None = None
    session_id: UUID | None = None
    message_id: UUID | None = None


class ImageJob(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: UUID
    status: ImageJobStatus = "queued"
    provider: str = "cloud"
    prompt_id: str | None = None
    card_id: UUID | None = None
    session_id: UUID | None = None
    message_id: UUID | None = None
    asset_id: UUID | None = None
    archived: bool = False
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
