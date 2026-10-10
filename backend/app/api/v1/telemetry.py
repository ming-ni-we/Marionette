"""Telemetry 路由（本地匿名埋点 + 诊断包导出）。本轮返回 501（下一轮实现）。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import UnimplementedError
from app.schemas.common import Envelope

router = APIRouter(tags=["Telemetry"])


class EventPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    properties: dict[str, Any] = Field(default_factory=dict)


@router.post(
    "/events",
    response_model=Envelope[dict],
    status_code=202,
    summary="上报本地匿名事件（仅落本地，不上报云端）",
)
async def record_event(payload: EventPayload) -> Envelope[dict]:
    raise UnimplementedError("记录事件")


@router.get(
    "/diagnostics/export",
    summary="导出诊断包（本地日志 + 自检结果 + 配置快照，脱敏）",
    responses={200: {"description": "zip 诊断包", "content": {"application/zip": {}}}},
)
async def export_diagnostics() -> None:
    raise UnimplementedError("导出诊断包")
