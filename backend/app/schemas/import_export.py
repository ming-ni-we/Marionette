"""导入导出 Schema。"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ImportResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_format: Literal["st_v1", "st_v2", "st_v3", "st_worldbook", "native"] = "native"
    object_id: UUID
    warnings: list[str] = Field(default_factory=list)
    preserved_unknown_keys: list[str] = Field(default_factory=list)


class ExportBundleRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    card_ids: list[UUID] = Field(default_factory=list)
    worldbook_ids: list[UUID] = Field(default_factory=list)
    preset_ids: list[UUID] = Field(default_factory=list)
    include_assets: bool = True


class OnboardingSamplesResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    card_ids: list[UUID] = Field(default_factory=list)
    worldbook_ids: list[UUID] = Field(default_factory=list)
    preset_ids: list[UUID] = Field(default_factory=list)
