"""系统信息与自检 Schema。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SystemInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    app_version: str = "0.1.0"
    schema_versions: dict[str, str] = Field(default_factory=dict)
    llm_provider: str = ""
    llm_model: str = ""
    embedding_model: str = ""
    gpu_available: bool = False
    image_provider: str = ""


class SelfCheckItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    status: Literal["ok", "warn", "fail"] = "ok"
    detail: str = ""
    fix_hint: str = ""


class LlmReachability(BaseModel):
    model_config = ConfigDict(extra="allow")

    reachable: bool = False
    error_class: str | None = None
    message: str = ""


class SelfCheckResult(BaseModel):
    """同时满足 SPEC §12（db / pgvector / llm.reachable）与 openapi SelfCheckResult。"""

    model_config = ConfigDict(extra="allow")

    # SPEC §12 断言所需的三项
    db: Literal["ok", "fail"] = "fail"
    pgvector: Literal["ok", "fail"] = "fail"
    llm: LlmReachability = Field(default_factory=LlmReachability)
    # openapi 的富结构
    overall: Literal["ok", "degraded", "failed"] = "failed"
    checks: list[SelfCheckItem] = Field(default_factory=list)
    port_in_use: bool = False
    suggested_port: int = 8000
    extra: dict[str, Any] = Field(default_factory=dict)
