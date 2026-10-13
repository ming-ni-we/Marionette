"""默认 LLMProvider：自研 OpenAI 兼容薄层。

刻意只依赖 httpx + 标准库，**不 import 任何厂商 SDK**（SPEC §4.1 / §4.2）。
ollama / openai_compatible / zhipu / dashscope / deepseek 都走同一套 OpenAI 协议，
差异仅在 base_url / api_key / model。
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Iterable
from typing import Any

import httpx

from app.adapters.base import ChatMessage, Completion, LLMHealth, LLMProvider
from app.core.errors import ErrorClass
from app.core.logging import get_logger

logger = get_logger(__name__)


def _classify_http(status: int, body: str, model: str) -> tuple[ErrorClass, str]:
    """把 HTTP 状态码 + 响应体归类到 7 类 error_class，并给出中文说明。"""
    lowered = (body or "").lower()
    if status in (401, 403):
        return ErrorClass.auth_failed, "API Key 无效或没有访问权限，请检查 LLM_API_KEY。"
    if status == 402 or "insufficient" in lowered or "quota" in lowered or "balance" in lowered:
        return ErrorClass.quota_exhausted, "账户余额不足或额度已用尽，请充值后重试。"
    if status == 404:
        if "model" in lowered:
            return (
                ErrorClass.model_not_found,
                f"模型「{model}」不存在或未开通，请核对 LLM_MODEL。",
            )
        return (
            ErrorClass.endpoint_invalid,
            "接口路径不存在：base_url 需要带 /v1（例如 https://api.example.com/v1）。",
        )
    if status == 400 and "model" in lowered:
        return ErrorClass.model_not_found, f"模型「{model}」不被接受，请核对 LLM_MODEL。"
    if status == 429:
        return ErrorClass.quota_exhausted, "请求过于频繁或已达配额上限，请稍后重试。"
    return ErrorClass.unknown, f"上游返回 HTTP {status}，未能归类，请查看 base_url / model 是否正确。"


def _extract_model_seen(payload: Any, fallback: str) -> str:
    if isinstance(payload, dict):
        model = payload.get("model")
        if isinstance(model, str) and model:
            return model
    return fallback


class OpenAICompatibleLLMProvider(LLMProvider):
    name = "openai_compatible"

    def __init__(self, timeout_seconds: float = 30.0, test_timeout_seconds: float = 3.0) -> None:
        self._timeout = timeout_seconds
        self._test_timeout = test_timeout_seconds

    @staticmethod
    def _headers(api_key: str) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    @staticmethod
    def _endpoint(base_url: str, path: str) -> str:
        return f"{base_url.rstrip('/')}/{path.lstrip('/')}"

    async def list_models(self, *, base_url: str, api_key: str) -> list[str]:
        if not base_url:
            return []
        url = self._endpoint(base_url, "models")
        async with httpx.AsyncClient(timeout=self._test_timeout) as client:
            resp = await client.get(url, headers=self._headers(api_key))
        if resp.status_code >= 400:
            return []
        try:
            payload = resp.json()
        except Exception:  # noqa: BLE001
            return []
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            return []
        return [str(item.get("id")) for item in data if isinstance(item, dict) and item.get("id")]

    async def test_connection(self, *, base_url: str, api_key: str, model: str) -> LLMHealth:
        if not base_url:
            return LLMHealth(
                reachable=False,
                error_class=ErrorClass.endpoint_invalid,
                message="未填写 base_url，请填写兼容 OpenAI 协议的接口地址（需带 /v1）。",
            )
        if not model:
            return LLMHealth(
                reachable=False,
                error_class=ErrorClass.model_not_found,
                message="未填写模型名，请填写 LLM_MODEL。",
            )
        url = self._endpoint(base_url, "chat/completions")
        body = {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "stream": False,
        }
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._test_timeout) as client:
                resp = await client.post(url, headers=self._headers(api_key), json=body)
        except httpx.TimeoutException:
            return LLMHealth(
                reachable=False,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error_class=ErrorClass.timeout,
                message="连接超时（3 秒）：端点不可达或网络受限，请检查网络与 base_url。",
            )
        except httpx.ConnectError:
            return LLMHealth(
                reachable=False,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error_class=ErrorClass.network_unreachable,
                message="无法建立连接：请检查 base_url 是否正确、服务是否在线。",
            )
        except httpx.HTTPError as exc:
            return LLMHealth(
                reachable=False,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error_class=ErrorClass.network_unreachable,
                message=f"网络异常（{type(exc).__name__}）：请检查 base_url 与网络策略。",
            )

        latency = int((time.perf_counter() - started) * 1000)
        text = resp.text or ""
        try:
            payload = resp.json()
        except Exception:  # noqa: BLE001
            payload = None
        model_seen = _extract_model_seen(payload, model)

        if resp.status_code >= 400:
            error_class, message = _classify_http(resp.status_code, text, model)
            return LLMHealth(
                reachable=False,
                latency_ms=latency,
                error_class=error_class,
                message=message,
                model_seen=model_seen,
            )
        return LLMHealth(
            reachable=True,
            latency_ms=latency,
            message="连接成功，已设为默认后端。",
            model_seen=model_seen,
        )

    async def stream_chat(
        self,
        messages: Iterable[ChatMessage],
        *,
        base_url: str,
        api_key: str,
        model: str,
        params: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """流式对话。解析 OpenAI SSE（`data: {json}` 行）。"""
        url = self._endpoint(base_url, "chat/completions")
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }
        body.update(params or {})
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST", url, headers=self._headers(api_key), json=body
            ) as resp:
                if resp.status_code >= 400:
                    raw = (await resp.aread()).decode("utf-8", errors="replace")
                    error_class, message = _classify_http(resp.status_code, raw, model)
                    raise UpstreamStreamError(message, error_class=error_class)
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line[len("data:") :].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        payload = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue
                    choices = payload.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    piece = delta.get("content")
                    if piece:
                        yield piece


    async def complete_chat(
        self,
        messages: Iterable[ChatMessage],
        *,
        base_url: str,
        api_key: str,
        model: str,
        params: dict[str, Any] | None = None,
    ) -> Completion:
        """非流式一次性补全（`stream=False`）。

        与 stream_chat 共用同一套错误归类；上游出错时抛
        UpstreamStreamError（由 llm_router 统一转为 UpstreamError）。
        """
        url = self._endpoint(base_url, "chat/completions")
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
        }
        body.update(params or {})
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, headers=self._headers(api_key), json=body)

        if resp.status_code >= 400:
            raw = resp.text or ""
            error_class, message = _classify_http(resp.status_code, raw, model)
            raise UpstreamStreamError(message, error_class=error_class)

        try:
            payload = resp.json()
        except Exception:  # noqa: BLE001 —— 上游返回非 JSON
            raise UpstreamStreamError(
                "上游返回的不是合法 JSON，无法解析补全结果。",
                error_class=ErrorClass.unknown,
            ) from None

        choices = payload.get("choices") if isinstance(payload, dict) else None
        choice = choices[0] if isinstance(choices, list) and choices else {}
        message_obj = choice.get("message") if isinstance(choice, dict) else None
        text = ""
        if isinstance(message_obj, dict):
            content = message_obj.get("content")
            if isinstance(content, str):
                text = content
        return Completion(
            text=text,
            finish_reason=choice.get("finish_reason") if isinstance(choice, dict) else None,
            model_seen=_extract_model_seen(payload, model),
        )


class UpstreamStreamError(RuntimeError):
    def __init__(self, message: str, *, error_class: ErrorClass) -> None:
        super().__init__(message)
        self.message = message
        self.error_class = error_class
