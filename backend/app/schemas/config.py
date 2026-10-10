"""配置类 Schema：LLM 后端 / 审核层 / 连通性测试（openapi.yaml）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LlmConfigInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: Literal["ollama", "openai_compatible", "zhipu", "dashscope", "deepseek"] = (
        "openai_compatible"
    )
    base_url: str
    api_key: str = ""
    model: str
    context_window: int = 8192
    extra: dict[str, Any] = Field(default_factory=dict)


class LlmConfig(LlmConfigInput):
    active: bool = True
    updated_at: datetime | None = None


class ConnectionTestResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    ok: bool = False
    latency_ms: int = 0
    error_class: (
        Literal[
            "model_not_found",
            "endpoint_invalid",
            "auth_failed",
            "quota_exhausted",
            "network_unreachable",
            "timeout",
            "unknown",
        ]
        | None
    ) = None
    message: str = ""
    model_seen: str | None = None


class ModerationRules(BaseModel):
    model_config = ConfigDict(extra="allow")

    blocked_words: list[str] = Field(default_factory=list)
    block_on_match: bool = True
    label_ai_generated: bool = True


class ModerationConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = True
    check_input: bool = True
    check_output: bool = True
    provider: Literal["builtin_wordlist", "cloud"] = "builtin_wordlist"
    rules: ModerationRules = Field(default_factory=ModerationRules)
    updated_at: datetime | None = None


class ComfyUIProbeRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    base_url: str = "http://host.docker.internal:8188"


class ComfyUIProbeResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    reachable: bool = False
    device: str | None = None
    checkpoints: list[str] = Field(default_factory=list)
