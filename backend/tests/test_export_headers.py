"""`Content-Disposition` 头构造（纯单元测试，不需数据库）。

回归背景：导出/下载接口遇到中文文件名时，Starlette 的
`Response.init_headers` 会对头值执行 `value.encode("latin-1")`，
中文直接抛 `UnicodeEncodeError` 把响应打成 500。修复后统一走
`app.core.text.content_disposition`，按 RFC 6266 / RFC 5987 给出
ASCII 回退名 + `filename*=UTF-8''...`。
"""

from __future__ import annotations

from app.core.text import content_disposition


def _fallback_of(header: str) -> str:
    """从 `filename="..."` 段取出 ASCII 回退名。"""
    return header.split('filename="', 1)[1].split('"', 1)[0]


def test_chinese_filename_is_latin1_encodable() -> None:
    header = content_disposition("卡片.json")
    assert "filename*=UTF-8''" in header
    assert header.encode("latin-1")  # 硬要求：不得抛 UnicodeEncodeError


def test_chinese_filename_percent_encoded() -> None:
    header = content_disposition("卡片.json")
    assert "%E5%8D%A1%E7%89%87.json" in header


def test_chinese_filename_ascii_fallback_has_no_non_ascii() -> None:
    header = content_disposition("卡片.json")
    fallback = _fallback_of(header)
    assert fallback.isascii()
    assert fallback == "download.json"


def test_pure_ascii_filename_fallback_is_original() -> None:
    header = content_disposition("card.json")
    assert 'filename="card.json"' in header
    assert "filename*=UTF-8''card.json" in header


def test_all_chinese_no_extension_fallback_non_empty() -> None:
    header = content_disposition("卡片")
    assert _fallback_of(header) == "download"


def test_empty_filename_fallback_non_empty() -> None:
    header = content_disposition("")
    assert _fallback_of(header) != ""
    assert header.encode("latin-1")


def test_inline_disposition_prefix() -> None:
    header = content_disposition("封面 图.png", disposition="inline")
    assert header.startswith("inline; ")
    assert _fallback_of(header).isascii()
    assert header.encode("latin-1")


def test_header_injection_chars_are_neutralized() -> None:
    # 引号 / CRLF 绝不能以字面形式进入头值
    header = content_disposition('evil".json\r\nX-Injected: 1')
    assert "\r" not in header and "\n" not in header
    fallback = _fallback_of(header)
    assert '"' not in fallback
    assert header.encode("latin-1")
