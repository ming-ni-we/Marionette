"""会话相关 Schema（openapi.yaml + schemas.md §6）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["user", "assistant", "system", "tool"]
MessageStatus = Literal["streaming", "complete", "incomplete"]
SessionStatus = Literal["active", "paused", "archived"]
MachineState = Literal[
    "idle", "assembling", "generating", "post_processing", "interrupted", "error"
]


class StateMachineError(BaseModel):
    code: int
    message: str
    at: datetime | None = None


class StateMachine(BaseModel):
    model_config = ConfigDict(extra="allow")

    current: MachineState = "idle"
    turn: int = 0
    version: int = 0
    last_error: StateMachineError | None = None


class Scene(BaseModel):
    model_config = ConfigDict(extra="allow")

    location: str = ""
    time: str = ""
    mood: str = ""
    summary: str = ""
    bg_asset_id: str | None = None


class MessageMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    swipe_index: int | None = None
    swipe_group_id: str | None = None
    greeting_index: int | None = None
    triggered_entry_ids: list[str] = Field(default_factory=list)
    image_asset_id: str | None = None
    parent_id: str | None = None


class Message(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: UUID
    role: Role
    content: str = ""
    status: MessageStatus = "complete"
    token_count: int | None = None
    created_at: datetime | None = None
    meta: MessageMeta = Field(default_factory=MessageMeta)


class MemoryFact(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str
    value: str
    confidence: float = 1.0
    source_message_id: str | None = None
    updated_at: datetime | None = None


class Memory(BaseModel):
    model_config = ConfigDict(extra="allow")

    rolling_summary: str = ""
    summary_upto_message_id: str | None = None
    facts: list[MemoryFact] = Field(default_factory=list)


class UserPersona(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = "Player"
    description: str = ""


class Session(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: UUID
    spec: str = "rpg_session"
    spec_version: str = "1.0"
    character_card_id: UUID | None = None
    preset_id: UUID | None = None
    worldbook_ids: list[UUID] = Field(default_factory=list)
    user_persona: UserPersona = Field(default_factory=UserPersona)
    status: SessionStatus = "active"
    title: str | None = None
    state_machine: StateMachine = Field(default_factory=StateMachine)
    scene: Scene = Field(default_factory=Scene)
    messages: list[Message] = Field(default_factory=list)
    triggered_entries: dict[str, Any] = Field(default_factory=dict)
    memory: Memory = Field(default_factory=Memory)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    character_card_id: UUID
    preset_id: UUID
    worldbook_ids: list[UUID] = Field(default_factory=list)
    user_persona: UserPersona = Field(default_factory=UserPersona)
    greeting_index: int = -1


class SessionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    preset_id: UUID | None = None
    worldbook_ids: list[UUID] | None = None
    user_persona: dict[str, Any] | None = None
    status: SessionStatus | None = None
    scene: Scene | None = None


class MessageInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: Literal["user", "assistant", "system"]
    content: str


class StreamRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    input: str
    idempotency_key: str | None = None
    overrides: dict[str, Any] = Field(default_factory=dict)


class RegenerateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    message_id: UUID | None = None
    overrides: dict[str, Any] = Field(default_factory=dict)


class ForkRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    from_message_id: UUID | None = None
    title: str | None = None


class ContextSegment(BaseModel):
    name: str
    token_count: int = 0


class ContextSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt_text: str = ""
    segments: list[ContextSegment] = Field(default_factory=list)
    world_info_trace: list[dict[str, Any]] = Field(default_factory=list)
    budget: dict[str, Any] = Field(default_factory=dict)
    estimated_prompt_tokens: int = 0
    actual_prompt_tokens: int | None = None
    assembled_at: datetime | None = None
