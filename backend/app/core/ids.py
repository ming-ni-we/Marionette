"""UUID 解析：把路径/查询参数里的字符串安全转成 UUID。

非法值必须是 400（参数错误）而不是 500。
"""

from __future__ import annotations

import uuid

from app.core.errors import BadRequestError


def parse_uuid(value: str | uuid.UUID | None, *, field: str = "id") -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    if value is None or value == "":
        raise BadRequestError(f"缺少必填参数 {field}。")
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise BadRequestError(f"参数 {field} 不是合法的 UUID：{value!r}。") from exc


def try_uuid(value: str | uuid.UUID | None) -> uuid.UUID | None:
    """宽松版：无法解析时返回 None（用于可选过滤器）。"""
    if value is None or value == "":
        return None
    return parse_uuid(value)
