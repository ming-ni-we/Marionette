"""纯文本/文件名工具（无业务、无副作用，SPEC §4.2 的 utils 层）。"""

from __future__ import annotations

from urllib.parse import quote

_UNSAFE_CHARS = '<>:"/\\|?*'


def safe_filename(name: str, *, fallback: str = "file") -> str:
    """去掉文件系统敏感字符，保留中文与空格。"""
    cleaned = "".join(ch for ch in str(name or "") if ch.isalnum() or ch in "-_ ").strip()
    cleaned = cleaned.replace("  ", " ")
    return cleaned or fallback


def _ascii_filename(filename: str) -> str:
    """为 Content-Disposition 生成纯 ASCII 回退名（老客户端用）。

    HTTP 头值必须能通过 `latin-1` 编码（Starlette 会做 `value.encode("latin-1")`），
    所以这里必须剔除中文等非 ASCII 字符；真正的 UTF-8 名字交给 `filename*=UTF-8''...`。
    主干取自 `safe_filename`（去文件系统敏感字符），扩展名单独保留其 ASCII 字母数字部分。
    """
    raw = str(filename or "")
    dot = raw.rfind(".")
    stem_src, suffix_src = (raw[:dot], raw[dot:]) if dot > 0 else (raw, "")
    suffix = "".join(ch for ch in suffix_src if ord(ch) < 128 and ch.isalnum())
    ascii_suffix = f".{suffix}" if suffix else ""
    # safe_filename 之后再去掉非 ASCII / 引号 / 控制字符
    stem = safe_filename(stem_src, fallback="")
    stem = "".join(ch for ch in stem if ord(ch) < 128 and ch != '"' and ch.isprintable()).strip()
    if not stem:  # 全中文名 / 空名：回退名保留原（ASCII）扩展名，避免出现空文件名
        stem = "download"
    return f"{stem}{ascii_suffix}"


def content_disposition(filename: str, *, disposition: str = "attachment") -> str:
    """构造符合 RFC 6266 / RFC 5987 的 `Content-Disposition` 头值。

    **为什么不能直接用中文文件名**：`Starlette.Response.init_headers` 会对每个头值执行
    `value.encode("latin-1")`，中文会在这一步抛 `UnicodeEncodeError`，把导出的 2xx 变成 500。
    故这里给出双保险：
      - `filename="..."`：纯 ASCII 回退名（老客户端）；
      - `filename*=UTF-8''%XX%XX...`：原始名按 UTF-8 做百分号编码（现代客户端优先采用）。

    返回值整体只含 ASCII 可见字符，保证 `encode("latin-1")` 不抛异常。
    """
    raw = str(filename or "")
    fallback = _ascii_filename(raw)
    encoded = quote(raw, safe="")  # safe="" 确保 "/" 也被编码，杜绝头注入
    return f"{disposition}; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"


def stem(filename: str) -> str:
    """取文件名主干（去掉目录与扩展名）。"""
    return (filename or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1].rsplit(".", 1)[0]


def file_suffix(key: str) -> str:
    idx = (key or "").rfind(".")
    return key[idx:] if idx >= 0 else ""


__all__ = ["content_disposition", "file_suffix", "safe_filename", "stem"]
