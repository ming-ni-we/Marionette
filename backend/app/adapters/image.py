"""图像生成适配器。

- `CloudImageProvider`：默认实现，走兼容 OpenAI 的 images 接口（BYOK）。
- `LocalComfyUIProvider`：占位实现，**v1 默认关闭**（enabled=False），代码保留备将来启用。
"""

from __future__ import annotations

import base64
from typing import Any

import httpx

from app.adapters.base import GeneratedImage, ImageProvider
from app.core.errors import ErrorClass, UpstreamError
from app.core.logging import get_logger

logger = get_logger(__name__)


class CloudImageProvider(ImageProvider):
    name = "cloud"

    def __init__(
        self,
        *,
        base_url: str = "",
        api_key: str = "",
        model: str = "",
        timeout_seconds: float = 120.0,
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self._base_url and self._api_key)

    async def generate(
        self, prompt: str, *, params: dict[str, Any] | None = None
    ) -> GeneratedImage:
        if not self.enabled:
            raise UpstreamError(
                "未配置图像后端：请在设置里填写图像 API 的 base_url 与 api_key。",
                error_class=ErrorClass.endpoint_invalid,
            )
        opts = params or {}
        width = int(opts.get("width", 1024))
        height = int(opts.get("height", 1024))
        body: dict[str, Any] = {
            "model": self._model or "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": f"{width}x{height}",
            "response_format": "b64_json",
        }
        if opts.get("negative_prompt"):
            body["negative_prompt"] = opts["negative_prompt"]
        url = f"{self._base_url.rstrip('/')}/images/generations"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, headers=headers, json=body)
        except httpx.TimeoutException as exc:
            raise UpstreamError(
                "图像生成超时：上游服务响应过慢，请稍后重试。",
                error_class=ErrorClass.timeout,
            ) from exc
        except httpx.HTTPError as exc:
            raise UpstreamError(
                f"无法连接图像服务（{type(exc).__name__}）：请检查图像 base_url。",
                error_class=ErrorClass.network_unreachable,
            ) from exc

        if resp.status_code >= 400:
            raise UpstreamError(
                f"图像服务返回 HTTP {resp.status_code}：请检查图像 api_key / model。",
                error_class=ErrorClass.quota_exhausted
                if resp.status_code in (402, 429)
                else ErrorClass.unknown,
            )

        payload = resp.json()
        items = payload.get("data") or []
        if not items:
            raise UpstreamError("图像服务未返回结果。", error_class=ErrorClass.unknown)
        first = items[0]
        if first.get("b64_json"):
            data = base64.b64decode(first["b64_json"])
        elif first.get("url"):
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                fetched = await client.get(first["url"])
            data = fetched.content
        else:
            raise UpstreamError("图像服务返回了未知格式。", error_class=ErrorClass.unknown)

        return GeneratedImage(
            data=data,
            content_type="image/png",
            meta={"prompt": prompt, "width": width, "height": height, "model": body["model"]},
        )


class LocalComfyUIProvider(ImageProvider):
    """本机 ComfyUI 适配器占位实现。

    v1 部署在云端（无本机 GPU / ComfyUI），故 `enabled` 恒为 False；
    保留类与接口，便于将来在带 GPU 的机器上启用。
    """

    name = "local_comfyui"

    def __init__(self, base_url: str = "http://host.docker.internal:8188") -> None:
        self.base_url = base_url

    @property
    def enabled(self) -> bool:
        return False

    async def generate(
        self, prompt: str, *, params: dict[str, Any] | None = None
    ) -> GeneratedImage:
        raise UpstreamError(
            "本机 ComfyUI 出图在 v1 默认关闭（云端部署无本机 GPU）。"
            "请在设置中改用云端图像 API。",
            error_class=ErrorClass.endpoint_invalid,
        )
