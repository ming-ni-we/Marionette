"""纯文本/文件名工具（无业务、无副作用，SPEC §4.2 的 utils 层）。"""

from __future__ import annotations

_UNSAFE_CHARS = '<>:"/\\|?*'


def safe_filename(name: str, *, fallback: str = "file") -> str:
    """去掉文件系统敏感字符，保留中文与空格。"""
    cleaned = "".join(ch for ch in str(name or "") if ch.isalnum() or ch in "-_ ").strip()
    cleaned = cleaned.replace("  ", " ")
    return cleaned or fallback


def stem(filename: str) -> str:
    """取文件名主干（去掉目录与扩展名）。"""
    return (filename or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1].rsplit(".", 1)[0]


def file_suffix(key: str) -> str:
    idx = (key or "").rfind(".")
    return key[idx:] if idx >= 0 else ""


__all__ = ["file_suffix", "safe_filename", "stem"]
