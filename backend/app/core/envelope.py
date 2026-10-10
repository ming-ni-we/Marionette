"""统一响应信封（openapi.yaml components.schemas.Envelope）。

成功：{"code": 0, "data": ..., "message": ""}
失败：{"code": <非0>, "data": null, "message": "<中文>", "error_class": "<7类之一>", "model_seen": <str|null>}
"""

from __future__ import annotations

from typing import Any

from app.core.errors import ErrorClass


def success(data: Any = None, message: str = "") -> dict[str, Any]:
    return {"code": 0, "data": data, "message": message}


def deleted(obj_id: Any) -> dict[str, Any]:
    """删除类端点的统一 data 体：{id, deleted}。"""
    return {"id": str(obj_id), "deleted": True}


def failure(
    code: int,
    message: str,
    *,
    error_class: ErrorClass | str = ErrorClass.unknown,
    model_seen: str | None = None,
    data: Any = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "data": data,
        "message": message,
        "error_class": error_class.value if isinstance(error_class, ErrorClass) else error_class,
        "model_seen": model_seen,
    }
