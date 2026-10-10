"""适配层接口定义（可替换接缝）。

铁律（SPEC §4.2）：业务层**只能**依赖这些接口，禁止 import 任何具体厂商 SDK。
二期上云时只替换实现，业务代码不动（ADR-009）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass, field
from typing import Any

from app.core.errors import ErrorClass
from app.core.security import Principal


# --------------------------------------------------------------------------- #
# AuthProvider
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class LoginOutcome:
    ok: bool
    token: str | None = None
    retry_after: int | None = None


class AuthProvider(ABC):
    """访问控制。v1 = 单用户口令 + 签名令牌；上云期 = JWT/OIDC。"""

    @abstractmethod
    def authenticate(self, password: str, client_key: str) -> LoginOutcome: ...

    @abstractmethod
    def verify_token(self, token: str | None) -> Principal | None: ...

    @abstractmethod
    def is_locked(self, client_key: str) -> int | None:
        """已限流时返回剩余冷却秒数。"""

    @abstractmethod
    def logout(self, client_key: str) -> None: ...


# --------------------------------------------------------------------------- #
# LLMProvider
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ChatMessage:
    role: str  # system / user / assistant
    content: str


@dataclass
class LLMHealth:
    """连通性自检结果，error_class 取 7 类之一（AC-04）。"""

    reachable: bool
    latency_ms: int = 0
    error_class: ErrorClass | None = None
    message: str = ""
    model_seen: str | None = None


class LLMProvider(ABC):
    """LLM 调度接口。默认实现 = 自研 OpenAI 兼容薄层（不 import 厂商 SDK）。"""

    name: str = "base"

    @abstractmethod
    async def test_connection(self, *, base_url: str, api_key: str, model: str) -> LLMHealth: ...

    @abstractmethod
    async def list_models(self, *, base_url: str, api_key: str) -> list[str]: ...

    @abstractmethod
    def stream_chat(
        self,
        messages: Iterable[ChatMessage],
        *,
        base_url: str,
        api_key: str,
        model: str,
        params: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """逐块产出回复文本。实现为 async generator。"""


# --------------------------------------------------------------------------- #
# ImageProvider
# --------------------------------------------------------------------------- #
@dataclass
class GeneratedImage:
    data: bytes
    content_type: str
    meta: dict[str, Any] = field(default_factory=dict)


class ImageProvider(ABC):
    name: str = "base"

    @property
    def enabled(self) -> bool:
        """v1 默认关闭本地 ComfyUI 适配器（SPEC §4.3）。"""
        return True

    @abstractmethod
    async def generate(
        self, prompt: str, *, params: dict[str, Any] | None = None
    ) -> GeneratedImage: ...


# --------------------------------------------------------------------------- #
# AssetStore
# --------------------------------------------------------------------------- #
@dataclass
class StoredObject:
    storage_key: str
    size_bytes: int


class AssetStore(ABC):
    """资产存储。v1 = 服务器本地卷 ./data/assets；上云期 = 对象存储。"""

    @abstractmethod
    async def save(
        self,
        data: bytes,
        *,
        filename: str,
        content_type: str,
        kind: str = "gallery",
    ) -> StoredObject: ...

    @abstractmethod
    async def read(self, storage_key: str) -> bytes: ...

    @abstractmethod
    async def delete(self, storage_key: str) -> bool: ...

    @abstractmethod
    async def exists(self, storage_key: str) -> bool: ...


# --------------------------------------------------------------------------- #
# ModerationProvider
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ModerationVerdict:
    blocked: bool
    matched: tuple[str, ...] = ()
    message: str | None = None


class ModerationProvider(ABC):
    """内容审核。v1 = 基础词表（可配置、可整体关闭）。"""

    name: str = "base"

    @abstractmethod
    async def check_input(self, text: str) -> ModerationVerdict: ...

    @abstractmethod
    async def check_output(self, text: str) -> ModerationVerdict: ...
