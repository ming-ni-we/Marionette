"""图像适配器单测（`app/adapters/image.py`）。

守两处真实踩到的坑（2026-10-14 火山方舟接入实测）：

1. **MIME 不能硬编码 PNG** —— 火山 Seedream 返回 JPEG，旧代码写死
   `content_type="image/png"` 会让归档资产带错误 MIME、文件后缀也错。
2. **水印必须显式关闭** —— 火山默认给图加「AI 生成」角标，
   请求体不带 `watermark: false` 就会带上水印。
"""

from __future__ import annotations

import base64
import json

import httpx
import pytest

from app.adapters.image import CloudImageProvider
from app.core.errors import UpstreamError

# ---- 最小合法文件头（只需前若干字节，嗅探逻辑只看头部）----
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + b"\x00" * 64
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
GIF_BYTES = b"GIF89a" + b"\x00" * 64
WEBP_BYTES = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 64


def _provider() -> CloudImageProvider:
    return CloudImageProvider(
        base_url="https://ark.example.com/api/v3",
        api_key="test-key",
        model="doubao-seedream-4-0-20260415",
    )


def _mock_success(monkeypatch, payload_bytes: bytes) -> dict:
    """把 httpx.AsyncClient.post 换成返回给定字节的桩，并捕获请求体。"""
    captured: dict = {}

    class FakeResp:
        status_code = 200

        @staticmethod
        def json() -> dict:
            return {"data": [{"b64_json": base64.b64encode(payload_bytes).decode()}]}

    class FakeClient:
        def __init__(self, **_kw) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_a) -> bool:
            return False

        async def post(self, url, headers=None, json=None):  # noqa: A002
            captured["url"] = url
            captured["body"] = json
            return FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    return captured


@pytest.mark.asyncio
async def test_url_is_base_url_plus_images_generations(monkeypatch) -> None:
    captured = _mock_success(monkeypatch, PNG_BYTES)
    await _provider().generate("一只猫")
    assert captured["url"] == "https://ark.example.com/api/v3/images/generations"


@pytest.mark.asyncio
async def test_watermark_disabled_by_default(monkeypatch) -> None:
    """火山默认加水印，请求体必须显式带 watermark=false。"""
    captured = _mock_success(monkeypatch, PNG_BYTES)
    await _provider().generate("一只猫")
    assert captured["body"]["watermark"] is False


@pytest.mark.asyncio
async def test_size_uses_width_x_height(monkeypatch) -> None:
    captured = _mock_success(monkeypatch, PNG_BYTES)
    await _provider().generate("一只猫", params={"width": 1024, "height": 1024})
    assert captured["body"]["size"] == "1024x1024"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (JPEG_BYTES, "image/jpeg"),
        (PNG_BYTES, "image/png"),
        (GIF_BYTES, "image/gif"),
        (WEBP_BYTES, "image/webp"),
        (b"not-an-image-at-all", "application/octet-stream"),
    ],
)
@pytest.mark.asyncio
async def test_content_type_sniffed_from_bytes(monkeypatch, raw, expected) -> None:
    """核心回归守卫：content_type 必须按真实字节判断，不能写死 image/png。"""
    _mock_success(monkeypatch, raw)
    img = await _provider().generate("一只猫")
    assert img.content_type == expected


@pytest.mark.asyncio
async def test_jpeg_does_not_get_png_label(monkeypatch) -> None:
    """点名回归：火山回 JPEG 时，绝不能标成 image/png（旧缺陷）。"""
    _mock_success(monkeypatch, JPEG_BYTES)
    img = await _provider().generate("一只猫")
    assert img.content_type != "image/png"
    assert img.content_type == "image/jpeg"


@pytest.mark.asyncio
async def test_missing_data_raises_upstream_error(monkeypatch) -> None:
    class FakeResp:
        status_code = 200

        @staticmethod
        def json() -> dict:
            return {"data": []}

    class FakeClient:
        def __init__(self, **_kw) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_a) -> bool:
            return False

        async def post(self, *_a, **_kw):
            return FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    with pytest.raises(UpstreamError):
        await _provider().generate("一只猫")


@pytest.mark.asyncio
async def test_upstream_4xx_raises_upstream_error(monkeypatch) -> None:
    class FakeResp:
        status_code = 403

        @staticmethod
        def json() -> dict:
            return {"error": {"code": "AccountOverdueError"}}

    class FakeClient:
        def __init__(self, **_kw) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_a) -> bool:
            return False

        async def post(self, *_a, **_kw):
            return FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    with pytest.raises(UpstreamError):
        await _provider().generate("一只猫")


@pytest.mark.asyncio
async def test_unconfigured_provider_raises(monkeypatch) -> None:
    """未配置 base_url / api_key 时应抛 UpstreamError，而不是裸异常。"""
    with pytest.raises(UpstreamError):
        await CloudImageProvider(base_url="", api_key="", model="x").generate("一只猫")


@pytest.mark.asyncio
async def test_request_body_is_json_serialisable(monkeypatch) -> None:
    """请求体必须可 JSON 序列化（防手滑塞进不可序列化对象）。"""
    captured = _mock_success(monkeypatch, PNG_BYTES)
    await _provider().generate("一只猫")
    assert json.dumps(captured["body"])
