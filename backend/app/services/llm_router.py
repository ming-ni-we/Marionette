"""LLM 调度服务：把预设 + 上下文交给 LLMProvider，处理流式与错误归类（架构 §4.7）。

分层铁律（SPEC §4.2）：本服务**只依赖 LLMProvider 接口**，绝不 import 任何厂商 SDK。
v1 单后端：从 app_config（缺失则回落环境变量）解析 base_url / api_key / model。

对外两个能力：
  - resolve()：解析出可用后端参数（含明文密钥）；缺失时抛 UpstreamError(endpoint_invalid)。
  - stream()：流式产出 delta 文本；上游错误按 7 类 error_class 归类并抛 UpstreamError。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from typing import Any

from app.adapters.base import ChatMessage
from app.adapters.llm import UpstreamStreamError
from app.adapters.registry import get_llm_provider
from app.core.errors import ErrorClass, UpstreamError
from app.core.logging import get_logger
from app.services.config import ConfigSvc

logger = get_logger(__name__)


@dataclass(frozen=True)
class LLMBackend:
    """已解析的 LLM 后端参数（api_key 为明文，仅在本层内存中使用）。"""

    provider: str
    base_url: str
    api_key: str
    model: str
    context_window: int = 8192
    extra: dict[str, Any] | None = None


class LLMRouter:
    """LLM 调用编排（v1 单后端）。"""

    def __init__(self, db: Any | None = None) -> None:
        # db 为 AsyncSession（仅用于读取配置）；为 None 时纯用环境变量默认。
        self._db = db

    async def resolve(self, overrides: dict[str, Any] | None = None) -> LLMBackend:
        """解析后端参数：DB 配置优先，环境变量兜底；overrides 在最后覆盖。"""
        raw: dict[str, Any] = {}
        if self._db is not None:
            raw = await ConfigSvc(self._db).get_llm_raw()
        merged = {**raw, **(overrides or {})}
        backend = LLMBackend(
            provider=str(merged.get("provider") or "openai_compatible"),
            base_url=str(merged.get("base_url") or ""),
            api_key=str(merged.get("api_key") or ""),
            model=str(merged.get("model") or ""),
            context_window=int(merged.get("context_window") or 8192),
            extra=merged.get("extra") or {},
        )
        if not backend.base_url or not backend.model:
            raise UpstreamError(
                "尚未配置 LLM 后端：请在「设置」里填写 base_url（需带 /v1）与模型名。",
                error_class=ErrorClass.endpoint_invalid,
            )
        return backend

    async def stream(
        self,
        messages: Iterable[ChatMessage],
        *,
        params: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """流式产出 delta 文本；上游错误统一转为 UpstreamError（7 类归类）。"""
        backend = await self.resolve(overrides)
        provider = get_llm_provider()
        # 采样参数：extra 合并 preset 传来的 params（如 temperature/max_tokens）
        merged_params = {**(backend.extra or {}), **(params or {})}
        try:
            async for piece in provider.stream_chat(
                messages,
                base_url=backend.base_url,
                api_key=backend.api_key,
                model=backend.model,
                params=merged_params or None,
            ):
                yield piece
        except UpstreamStreamError as exc:
            logger.warning(
                "llm upstream stream error",
                extra={"error_class": exc.error_class.value, "model_seen": backend.model},
            )
            raise UpstreamError(
                exc.message, error_class=exc.error_class, model_seen=backend.model
            ) from exc
        except Exception as exc:  # noqa: BLE001 —— 兜底归类，避免 500 直冒
            logger.warning("llm stream failed: %s", type(exc).__name__)
            raise UpstreamError(
                f"LLM 调用失败（{type(exc).__name__}）：请检查后端配置与网络。",
                error_class=ErrorClass.network_unreachable,
                model_seen=backend.model,
            ) from exc


__all__ = ["LLMBackend", "LLMRouter"]
