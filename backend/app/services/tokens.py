"""Token 估算（保守近似，取大不取小）。

架构 §4.6 要求"估算器与所选模型一致"，但 v1 不绑定具体模型（BYOK，base_url/model 可换），
故先用与模型无关的保守折算：中文按 1 字符 1 token，其余字符按 3 字符 1 token
（真实约 4 字符/token，取 3 即刻意高估），每条再 +1 作为消息包装开销。

保守方向很重要：宁可把条目判为"被预算挤出"，也不要实际超限导致上游截断。
"""

from __future__ import annotations

import math

# 需要按"每字符 ≈ 1 token"计价的区段：CJK 统一表意文字、扩展 A、兼容表意、
# 中文标点、日文假名、韩文音节、全角字符
_WIDE_RANGES: tuple[tuple[int, int], ...] = (
    (0x3000, 0x303F),
    (0x3040, 0x30FF),
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xAC00, 0xD7AF),
    (0xF900, 0xFAFF),
    (0xFF00, 0xFFEF),
    (0x20000, 0x2FA1F),
)


def _is_wide(ch: str) -> bool:
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in _WIDE_RANGES)


def count_wide(text: str) -> int:
    return sum(1 for ch in text if _is_wide(ch))


def estimate_tokens(text: str | None) -> int:
    """保守估算 token 数。空串返回 0。"""
    if not text:
        return 0
    wide = count_wide(text)
    narrow = len(text) - wide
    return wide + math.ceil(narrow / 3) + 1


def estimate_tokens_many(texts: list[str] | tuple[str, ...]) -> int:
    return sum(estimate_tokens(t) for t in texts)
