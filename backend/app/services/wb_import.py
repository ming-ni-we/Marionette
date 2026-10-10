"""世界书导入载体的归一化（SillyTavern World Info / 原生 rpg_worldbook）。

支持的载体形态：
  1. 平台原生：`{spec: "rpg_worldbook", data: {...}}`
  2. ST World Info：`{entries: [ {key|keys, content, disable, order, ...} ]}`
  3. ST lorebook v2 的字典形态：`{entries: {"0": {...}, "1": {...}}}`

出口统一为平台 WorldBookData（去掉信封）。
"""

from __future__ import annotations

from typing import Any

from app.core.errors import BadRequestError
from app.services.st_book import book_from_st


def worldbook_data_from_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """返回 (WorldBookData, source_format)。无法解析时抛 400。"""
    if payload.get("spec") == "rpg_worldbook":
        data = payload.get("data")
        if not isinstance(data, dict):
            raise BadRequestError("rpg_worldbook 缺少 data 节点，无法导入。")
        return data, "native"

    source = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    raw_entries = source.get("entries")
    if raw_entries is None:
        raise BadRequestError(
            "世界书文件里没有 entries 字段。请确认导出的是 SillyTavern World Info 或本平台世界书。"
        )
    if isinstance(raw_entries, dict):  # ST lorebook v2 有时把 entries 存成对象
        source = {**source, "entries": list(raw_entries.values())}

    normalized = book_from_st(source)
    if normalized is None:
        raise BadRequestError("世界书结构无法解析，导入中止。")
    return normalized, "st_worldbook"


__all__ = ["worldbook_data_from_payload"]
