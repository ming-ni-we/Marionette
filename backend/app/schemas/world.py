"""世界 Schema（剧情引擎）。

铁律同 content.py：未知字段不销毁（extra="allow"），保证扩展无损。

组织方式与角色卡/世界书一致：`spec` + `spec_version` + `data` + `extensions`，
但这里 data 的键直接摊平到表列（setting/factions/cast/relations/outline/opening），
因为剧情引擎需要按这些维度独立读写（如只更新 outline 而不动 cast）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
# 世界内部结构件
# --------------------------------------------------------------------------- #
class Faction(BaseModel):
    """势力。"""

    model_config = ConfigDict(extra="allow")

    id: str = ""
    name: str = ""
    stance: str = ""  # 立场（友好 / 中立 / 敌对 / 未知）
    description: str = ""


class CastMember(BaseModel):
    """角色群成员。

    `id` 是剧情内的稳定标识（用于 speaker_id / 关系图引用），
    `card_id` 可选：填了就关联到已有角色卡（复用其人设与头像）。
    """

    model_config = ConfigDict(extra="allow")

    id: str = ""
    name: str = ""
    role: str = ""  # 主角 / 配角 / 反派 / 路人
    voice: str = ""  # 说话风格（供导演写台词时对齐语气）
    goals: list[str] = Field(default_factory=list)
    description: str = ""
    card_id: str | None = None


class Relation(BaseModel):
    """角色关系图的一条边。

    `from` 是 Python 关键字，故字段名为 `from_` 并用 alias 映射为 JSON 的 `from`。
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    from_: str = Field(default="", alias="from")
    to: str = ""
    kind: str = ""  # 旧识 / 上下级 / 宿敌 / 血亲
    tension: float = Field(default=0.0, ge=-1.0, le=1.0)  # -1 敌对 .. 1 亲密
    note: str = ""


class OutlineNode(BaseModel):
    """剧情大纲的关键节点。"""

    model_config = ConfigDict(extra="allow")

    id: str = ""
    title: str = ""
    brief: str = ""
    trigger: str = ""  # 触发条件描述（由导演判断是否满足）


class Outline(BaseModel):
    """剧情大纲。"""

    model_config = ConfigDict(extra="allow")

    main_goal: str = ""
    nodes: list[OutlineNode] = Field(default_factory=list)
    endings: list[str] = Field(default_factory=list)  # 结局倾向（开放式描述）


class WorldSetting(BaseModel):
    """世界观核心设定。"""

    model_config = ConfigDict(extra="allow")

    era: str = ""  # 时代背景
    locations: list[str] = Field(default_factory=list)  # 核心地点
    rules: list[str] = Field(default_factory=list)  # 世界规则
    tone: str = ""  # 氛围基调
    summary: str = ""  # 一句话总览


# --------------------------------------------------------------------------- #
# 世界对象
# --------------------------------------------------------------------------- #
class WorldInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    spec: Literal["rpg_world"] = "rpg_world"
    spec_version: str = "1.0"
    title: str = Field(min_length=1)
    setting: WorldSetting = Field(default_factory=WorldSetting)
    factions: list[Faction] = Field(default_factory=list)
    cast: list[CastMember] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    outline: Outline = Field(default_factory=Outline)
    opening: str = ""
    extensions: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class World(WorldInput):
    id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorldPatch(BaseModel):
    """部分更新（PATCH）。全部可选，只改传入的键。"""

    model_config = ConfigDict(extra="allow")

    title: str | None = None
    setting: WorldSetting | None = None
    factions: list[Faction] | None = None
    cast: list[CastMember] | None = None
    relations: list[Relation] | None = None
    outline: Outline | None = None
    opening: str | None = None
    extensions: dict[str, Any] | None = None
    tags: list[str] | None = None


__all__ = [
    "CastMember",
    "Faction",
    "Outline",
    "OutlineNode",
    "Relation",
    "World",
    "WorldInput",
    "WorldPatch",
    "WorldSetting",
]
