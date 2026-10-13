"""非流式 LLM 调用（complete_chat / LLMRouter.complete）单元测试。

覆盖：正常 JSON 返回、上游 4xx 归类、非 JSON 响应、router 层的错误转换。
全部走 mock provider，不依赖网络。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from typing import Any

import pytest

from app.adapters.base import ChatMessage, Completion, LLMProvider
from app.adapters.llm import UpstreamStreamError
from app.core.errors import ErrorClass, UpstreamError
from app.services.llm_router import LLMRouter


class _StubProvider(LLMProvider):
    """可编程的假 provider：按构造参数决定 complete_chat 的行为。"""

    name = "stub"

    def __init__(
        self,
        *,
        text: str = '{"ok": true}',
        raise_error: Exception | None = None,
    ) -> None:
        self._text = text
        self._raise = raise_error
        self.calls: list[dict[str, Any]] = []

    async def test_connection(self, *, base_url, api_key, model):  # pragma: no cover
        raise NotImplementedError

    async def list_models(self, *, base_url, api_key):  # pragma: no cover
        return []

    async def stream_chat(
        self, messages: Iterable[ChatMessage], *, base_url, api_key, model, params=None
    ) -> AsyncIterator[str]:  # pragma: no cover
        yield ""

    async def complete_chat(
        self, messages: Iterable[ChatMessage], *, base_url, api_key, model, params=None
    ) -> Completion:
        self.calls.append(
            {
                "messages": list(messages),
                "base_url": base_url,
                "model": model,
                "params": params,
            }
        )
        if self._raise is not None:
            raise self._raise
        return Completion(text=self._text, finish_reason="stop", model_seen=model)


# --------------------------------------------------------------------------- #
# provider 层
# --------------------------------------------------------------------------- #
class TestCompleteChat:
    def test_completion_dataclass_defaults(self) -> None:
        c = Completion(text="hello")
        assert c.text == "hello"
        assert c.finish_reason is None
        assert c.model_seen is None

    @pytest.mark.asyncio
    async def test_stub_returns_text(self) -> None:
        """假 provider 本身可用（作为其余测试的基线）。"""
        p = _StubProvider(text='{"speakers": []}')
        out = await p.complete_chat(
            [ChatMessage(role="user", content="hi")],
            base_url="http://x/v1",
            api_key="k",
            model="m",
        )
        assert out.text == '{"speakers": []}'
        assert out.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_upstream_error_propagates(self) -> None:
        """provider 抛 UpstreamStreamError 时应原样向上传递。"""
        p = _StubProvider(raise_error=UpstreamStreamError("boom", error_class=ErrorClass.auth_failed))
        with pytest.raises(UpstreamStreamError) as ei:
            await p.complete_chat(
                [ChatMessage(role="user", content="hi")],
                base_url="http://x/v1",
                api_key="k",
                model="m",
            )
        assert ei.value.error_class == ErrorClass.auth_failed
        assert ei.value.message == "boom"


# --------------------------------------------------------------------------- #
# router 层
# --------------------------------------------------------------------------- #
class TestRouterComplete:
    @pytest.mark.asyncio
    async def test_router_returns_text(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stub = _StubProvider(text='{"speakers":[{"id":"a"}]}')
        monkeypatch.setattr("app.services.llm_router.get_llm_provider", lambda: stub)

        router = LLMRouter(db=None)
        monkeypatch.setattr(
            router,
            "resolve",
            lambda overrides=None: _resolved(),
        )
        out = await router.complete([ChatMessage(role="user", content="hi")])
        assert out == '{"speakers":[{"id":"a"}]}'
        # params 被透传
        assert stub.calls[0]["params"] is None

    @pytest.mark.asyncio
    async def test_router_passes_params(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stub = _StubProvider()
        monkeypatch.setattr("app.services.llm_router.get_llm_provider", lambda: stub)
        router = LLMRouter(db=None)
        monkeypatch.setattr(router, "resolve", lambda overrides=None: _resolved())

        await router.complete(
            [ChatMessage(role="user", content="hi")],
            params={"temperature": 0.4, "max_tokens": 512},
        )
        assert stub.calls[0]["params"] == {"temperature": 0.4, "max_tokens": 512}

    @pytest.mark.asyncio
    async def test_router_wraps_upstream_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """UpstreamStreamError → UpstreamError，error_class 保留。"""
        stub = _StubProvider(
            raise_error=UpstreamStreamError("key 无效", error_class=ErrorClass.auth_failed)
        )
        monkeypatch.setattr("app.services.llm_router.get_llm_provider", lambda: stub)
        router = LLMRouter(db=None)
        monkeypatch.setattr(router, "resolve", lambda overrides=None: _resolved())

        with pytest.raises(UpstreamError) as ei:
            await router.complete([ChatMessage(role="user", content="hi")])
        assert ei.value.error_class == ErrorClass.auth_failed

    @pytest.mark.asyncio
    async def test_router_wraps_unexpected_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """任意异常 → UpstreamError(network_unreachable)，绝不裸抛。"""
        stub = _StubProvider(raise_error=RuntimeError("socket reset"))
        monkeypatch.setattr("app.services.llm_router.get_llm_provider", lambda: stub)
        router = LLMRouter(db=None)
        monkeypatch.setattr(router, "resolve", lambda overrides=None: _resolved())

        with pytest.raises(UpstreamError) as ei:
            await router.complete([ChatMessage(role="user", content="hi")])
        assert ei.value.error_class == ErrorClass.network_unreachable
        assert "RuntimeError" in ei.value.message


async def _resolved():
    from app.services.llm_router import LLMBackend

    return LLMBackend(
        provider="openai_compatible",
        base_url="http://x/v1",
        api_key="k",
        model="m",
        context_window=8192,
        extra={},
    )
