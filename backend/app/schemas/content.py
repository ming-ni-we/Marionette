"""内容对象 Schema：角色卡 / 世界书 / 预设（schemas.md §3–§5）。

铁律：未知字段不销毁（extra="allow"），保证 ST 双向兼容时的无损回写。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- #
# 角色卡
# --------------------------------------------------------------------------- #
class WorldBookEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: UUID | None = None
    keys: list[str] = Field(default_factory=list)
    secondary_keys: list[str] = Field(default_factory=list)
    content: str = ""
    comment: str = ""
    enabled: bool = True
    constant: bool = False
    selective: bool = False
    case_sensitive: bool = False
    match_whole_words: bool = False
    use_regex: bool = False
    regex_flags: str = "i"
    insertion_order: int = 100
    priority: int = 10
    position: Literal[
        "before_char", "after_char", "before_example", "after_example", "at_depth"
    ] = "before_char"
    depth: int = 4
    role: Literal["system", "user", "assistant"] = "system"
    vector_recall: bool = False
    vector_threshold: float = Field(default=0.75, ge=0, le=1)
    token_count: int | None = None  # 只读，服务端估算
    extensions: dict[str, Any] = Field(default_factory=dict)


class WorldBookData(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = ""
    description: str = ""
    scan_depth: int = 4
    token_budget: int = 1024
    recursive_scanning: bool = False
    max_recursion_depth: int = 3
    entries: list[WorldBookEntry] = Field(default_factory=list)
    extensions: dict[str, Any] = Field(default_factory=dict)


class WorldBookInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    spec: Literal["rpg_worldbook"] = "rpg_worldbook"
    spec_version: str = "1.0"
    data: WorldBookData
    extensions: dict[str, Any] = Field(default_factory=dict)


class WorldBook(WorldBookInput):
    id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CardData(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1)
    description: str = ""
    personality: str = ""
    scenario: str = ""
    first_mes: str = ""
    mes_example: str = ""
    creator_notes: str = ""
    system_prompt: str = ""
    post_history_instructions: str = ""
    alternate_greetings: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    creator: str = ""
    character_version: str = ""
    character_book: WorldBookData | None = None
    extensions: dict[str, Any] = Field(default_factory=dict)


class CardInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    spec: Literal["rpg_card"] = "rpg_card"
    spec_version: str = "1.0"
    data: CardData
    extensions: dict[str, Any] = Field(default_factory=dict)


class Card(CardInput):
    id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


# --------------------------------------------------------------------------- #
# 预设
# --------------------------------------------------------------------------- #
class SamplingParams(BaseModel):
    model_config = ConfigDict(extra="allow")

    temperature: float = 0.8
    top_p: float = 0.95
    top_k: int = 40
    min_p: float = 0.05
    repetition_penalty: float = 1.1
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    max_tokens: int = 1024
    seed: int = -1
    stop: list[str] = Field(default_factory=list)


class PromptTemplate(BaseModel):
    model_config = ConfigDict(extra="allow")

    system: str
    instruction: str = ""
    chat_separator: str = "\n"
    placeholders: dict[str, str] = Field(default_factory=dict)


class ContextBudget(BaseModel):
    model_config = ConfigDict(extra="allow")

    max_context_tokens: int = 8192
    reserve_for_output: int = 1024
    character_pct: int = 15
    world_info_pct: int = 25
    memory_pct: int = 15
    vector_recall_pct: int = 5
    history_pct: int = 35


class MemoryPolicy(BaseModel):
    model_config = ConfigDict(extra="allow")

    summarize_every_n_turns: int = 10
    summary_trigger_ratio: float = 0.8
    vector_top_k: int = 5
    extract_facts: bool = True


class ImageHookConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = False
    mode: Literal["manual", "every_n_turns", "on_scene_change"] = "manual"
    every_n_turns: int = 10
    workflow_template_id: str | None = None


class PresetData(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    description: str = ""
    sampling: SamplingParams = Field(default_factory=SamplingParams)
    prompt_template: PromptTemplate
    context_budget: ContextBudget = Field(default_factory=ContextBudget)
    memory: MemoryPolicy = Field(default_factory=MemoryPolicy)
    image_hook: ImageHookConfig = Field(default_factory=ImageHookConfig)
    extensions: dict[str, Any] = Field(default_factory=dict)


class PresetInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    spec: Literal["rpg_preset"] = "rpg_preset"
    spec_version: str = "1.0"
    data: PresetData
    extensions: dict[str, Any] = Field(default_factory=dict)


class Preset(PresetInput):
    id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


# --------------------------------------------------------------------------- #
# 世界书触发自测
# --------------------------------------------------------------------------- #
class WorldBookTestRequest(BaseModel):
    sample_text: str
    scan_depth: int | None = None


class WorldBookTestEntryResult(BaseModel):
    entry_id: str
    comment: str = ""
    matched: bool = False
    match_type: Literal["constant", "keyword", "regex", "vector", "none"] = "none"
    matched_key: str | None = None
    in_budget: bool = False
    token_count: int = 0
    final_position: str | None = None


class WorldBookTestResult(BaseModel):
    entries: list[WorldBookTestEntryResult] = Field(default_factory=list)
    total_tokens: int = 0
    token_budget: int = 1024
