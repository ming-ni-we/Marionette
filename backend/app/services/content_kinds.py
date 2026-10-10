"""内容资源类型注册表（cards / worldbooks / presets）。

把"每种资源的模型、Schema、`q` 命中字段、标签来源"集中在一处，
避免四个 list 端点各写一套（schemas.md §9 的收口要求）。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Text, cast, func

from app.core.config import SCHEMA_VERSIONS
from app.core.errors import BadRequestError
from app.models.base import Base
from app.models.card import Card
from app.models.preset import Preset
from app.models.worldbook import WorldBook
from app.schemas.content import (
    CardData,
    CardInput,
    PresetData,
    PresetInput,
    WorldBookData,
    WorldBookInput,
)
from app.services.content_search import ResourceSpec


def tags_from_card_data(data: dict[str, Any]) -> list[str]:
    return [str(t) for t in (data.get("tags") or []) if str(t).strip()]


def tags_from_worldbook_data(data: dict[str, Any]) -> list[str]:
    """世界书标签在 `data.extensions.rpg.tags`（schemas.md §4.1）；兼容 `data.tags`。"""
    if not isinstance(data, dict):
        return []
    rpg = ((data.get("extensions") or {}).get("rpg") or {})
    raw = rpg.get("tags") or data.get("tags") or []
    return [str(t) for t in raw if str(t).strip()]


def tags_none(_: dict[str, Any]) -> list[str]:
    return []


@dataclass(frozen=True)
class ContentKind:
    key: str
    model: type[Base]
    spec_name: str
    data_cls: type[BaseModel]
    input_cls: type[BaseModel]
    tags_from: Callable[[dict[str, Any]], list[str]]


KINDS: dict[str, ContentKind] = {
    "card": ContentKind(
        key="card",
        model=Card,
        spec_name="rpg_card",
        data_cls=CardData,
        input_cls=CardInput,
        tags_from=tags_from_card_data,
    ),
    "worldbook": ContentKind(
        key="worldbook",
        model=WorldBook,
        spec_name="rpg_worldbook",
        data_cls=WorldBookData,
        input_cls=WorldBookInput,
        tags_from=tags_from_worldbook_data,
    ),
    "preset": ContentKind(
        key="preset",
        model=Preset,
        spec_name="rpg_preset",
        data_cls=PresetData,
        input_cls=PresetInput,
        tags_from=tags_none,
    ),
}

Q_FIELD_NAMES: dict[str, list[str]] = {
    "card": ["name", "description", "personality", "scenario", "tags"],
    "worldbook": ["name", "description", "entries.keys", "entries.content", "entries.comment"],
    "preset": ["name", "description"],
    "asset": ["filename", "tags", "meta.prompt"],
}


def build_search_spec(kind: ContentKind) -> ResourceSpec:
    """按资源类型构建 `q`/`tags` 的 SQL 表达式集合。"""
    if kind.key == "card":
        return ResourceSpec(
            model=Card,
            name_column=Card.name,
            q_fields=lambda: (
                Card.name,
                Card.data["description"].astext,
                Card.data["personality"].astext,
                Card.data["scenario"].astext,
                func.array_to_string(Card.tags, " "),
            ),
            tags_column=Card.tags,
        )
    if kind.key == "worldbook":
        return ResourceSpec(
            model=WorldBook,
            name_column=WorldBook.name,
            q_fields=lambda: (
                WorldBook.name,
                WorldBook.data["description"].astext,
                # entries[].keys / content / comment 统一在本表达式的 JSON 文本上匹配
                cast(WorldBook.data["entries"], Text),
            ),
            tags_column=WorldBook.tags,
        )
    return ResourceSpec(
        model=Preset,
        name_column=Preset.name,
        q_fields=lambda: (Preset.name, Preset.data["description"].astext),
        tags_column=None,
    )


def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in str(value).split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def assert_supported_version(kind: ContentKind, version: str | None) -> None:
    """schemas.md §1 铁律 2：spec_version 高于本机支持版本时拒绝写入。"""
    if not version:
        return
    supported = SCHEMA_VERSIONS.get(kind.key, "1.0")
    if _version_tuple(version) > _version_tuple(supported):
        raise BadRequestError(
            f"{kind.spec_name} 的 spec_version={version} 高于本机支持的 {supported}，"
            "已拒绝写入以免丢字段。请升级服务端后再试。"
        )


def q_field_names(kind: str) -> list[str]:
    return list(Q_FIELD_NAMES.get(kind, []))


__all__ = [
    "KINDS",
    "ContentKind",
    "assert_supported_version",
    "build_search_spec",
    "q_field_names",
    "tags_from_card_data",
    "tags_from_worldbook_data",
]
