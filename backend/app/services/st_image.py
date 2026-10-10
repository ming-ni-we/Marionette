"""SillyTavern 卡片载体读写（PNG/WEBP 的 tEXt / 自定义 chunk）。

只处理"字节 <-> JSON 载体"这一层，不关心卡片语义（语义在 st_compat.py）。
ST 生态约定：PNG 的 `tEXt` chunk，keyword = `chara`（V2）或 `ccv3`（V3），值为 JSON 的 base64。

注意：写 PNG 卡片时，base64 是纯 ASCII，可安全写入 latin-1 的 tEXt；
而 JSON 本体含中文，故必须先 base64 再写入（否则 Latin-1 编码会抛错）。
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import re
from typing import Any

from app.core.errors import BadRequestError
from app.core.logging import get_logger

logger = get_logger(__name__)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
RIFF_MAGIC = b"RIFF"
WEBP_TAG = b"WEBP"

# 优先级：V3 优先于 V2（schemas.md §3.4 第 2 条）
CARD_KEYWORDS = ("ccv3", "chara")
_B64_RE = re.compile(rb"[A-Za-z0-9+/=]{64,}")


def sniff_container(raw: bytes) -> str:
    """返回 png / webp / json。"""
    if raw[:8] == PNG_MAGIC:
        return "png"
    if raw[:4] == RIFF_MAGIC and raw[8:12] == WEBP_TAG:
        return "webp"
    return "json"


def _decode_b64_json(token: bytes | str, *, source: str) -> dict[str, Any]:
    if isinstance(token, str):
        token = token.strip().encode("ascii", "ignore")
    try:
        decoded = base64.b64decode(token, validate=False)
        payload = json.loads(decoded.decode("utf-8"))
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise BadRequestError(
            f"卡片载体的 {source} 数据不是合法的 base64 JSON，文件可能已损坏。"
        ) from exc
    if not isinstance(payload, dict):
        raise BadRequestError(f"卡片载体的 {source} 解析结果不是 JSON 对象，无法导入。")
    return payload


def _pick_text(img_text: dict[str, Any]) -> tuple[str | None, str | None]:
    lowered = {str(k).lower(): v for k, v in (img_text or {}).items()}
    for keyword in CARD_KEYWORDS:
        if keyword in lowered:
            value = lowered[keyword]
            if isinstance(value, bytes):
                value = value.decode("utf-8", "ignore")
            if value:
                return keyword, str(value)
    return None, None


def read_card_payload(raw: bytes) -> tuple[dict[str, Any], str]:
    """从 PNG/WEBP 字节读出卡片 JSON。返回 (payload, 载体关键字)。

    找不到内嵌数据时抛 400（中文明确错误），**不抛 500**。
    """
    container = sniff_container(raw)
    if container == "json":
        try:
            payload = json.loads(raw.decode("utf-8-sig"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise BadRequestError("文件既不是 PNG/WEBP 图片，也不是合法的 UTF-8 JSON。") from exc
        if not isinstance(payload, dict):
            raise BadRequestError("JSON 顶层必须是对象，无法作为角色卡导入。")
        return payload, "json"

    from PIL import Image  # 延迟导入：非图片导入路径不付 Pillow 启动成本

    try:
        with Image.open(io.BytesIO(raw)) as img:
            img_text = dict(getattr(img, "text", {}) or {})
            info_text = {k: v for k, v in (img.info or {}).items() if isinstance(v, (str, bytes))}
    except Exception as exc:  # noqa: BLE001 —— 非法图片统一转 400
        raise BadRequestError("图片无法解析，文件可能已损坏或不是有效的图片格式。") from exc

    keyword, token = _pick_text({**info_text, **img_text})
    if keyword is not None and token is not None:
        return _decode_b64_json(token, source=keyword), keyword

    # WEBP 兜底：ST 生态把 JSON 直接塞在自定义 chunk 的 base64 里，Pillow 不暴露该 chunk。
    if container == "webp":
        for candidate in _B64_RE.findall(raw):
            try:
                payload = json.loads(base64.b64decode(candidate, validate=False).decode("utf-8"))
            except Exception:  # noqa: BLE001 —— 试探性解析，失败即继续
                continue
            if isinstance(payload, dict) and ("spec" in payload or "name" in payload):
                logger.info("webp card payload recovered from raw chunk scan")
                return payload, "webp_chunk"

    raise BadRequestError(
        "图片中没有找到角色卡数据（PNG 需包含 tEXt 关键字 chara 或 ccv3）。"
        "请确认这是由 SillyTavern 导出的角色卡，或改用 .json 文件导入。"
    )


def _placeholder_image(seed_text: str) -> Any:
    """无头像时生成一张纯色占位图（不使用 emoji / 文字）。"""
    from PIL import Image

    digest = hashlib.sha256(seed_text.encode("utf-8")).digest()
    base = tuple(40 + (digest[i] % 120) for i in range(3))
    return Image.new("RGB", (512, 768), base)


def build_png_card(payload: dict[str, Any], *, base_image: bytes | None = None, seed: str = "") -> bytes:
    """把卡片 JSON base64 写入 PNG 的 tEXt(chara)，可回导（AC-06）。"""
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo

    if base_image:
        try:
            image = Image.open(io.BytesIO(base_image)).convert("RGB")
        except Exception:  # noqa: BLE001 —— 头像损坏时回落占位图，不阻断导出
            image = _placeholder_image(seed)
    else:
        image = _placeholder_image(seed or str(payload.get("name", "")))

    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    token = base64.b64encode(serialized).decode("ascii")
    meta = PngInfo()
    meta.add_text("chara", token)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", pnginfo=meta)
    return buffer.getvalue()


__all__ = ["CARD_KEYWORDS", "build_png_card", "read_card_payload", "sniff_container"]
