"""Telemetry 路由（本地匿名埋点 + 诊断包导出，F10）。

路由只做编排：解析入参 -> 调 TelemetrySvc -> 套统一信封 / 返回 zip。
隐私铁律：事件仅落本地，不上报云端；诊断包导出前对配置做脱敏。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.deps import DbSession
from app.core.text import content_disposition
from app.schemas.common import Envelope
from app.services.telemetry import TelemetrySvc

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
    """记录一条本地事件（JSONL 追加）。返回落库后的条目（含服务端时间戳）。"""
    entry = TelemetrySvc().record(payload.name, payload.properties)
    return Envelope(data=entry)


@router.get(
    "/diagnostics/export",
    summary="导出诊断包（本地日志 + 自检结果 + 配置快照，脱敏）",
    responses={200: {"description": "zip 诊断包", "content": {"application/zip": {}}}},
)
async def export_diagnostics(db: DbSession) -> Response:
    """导出诊断 zip：自检结果 + 脱敏配置快照 + 近期事件 + 本地日志。

    自检复用系统自检逻辑（DB / pgvector / LLM），失败不阻断导出（仅记 warn）。
    """
    checks = await _collect_checks(db)
    blob = await TelemetrySvc().build_diagnostics(checks=checks)
    return Response(
        content=blob,
        media_type="application/zip",
        headers={
            "Content-Disposition": content_disposition(
                "marionette-diagnostics.zip", disposition="attachment"
            )
        },
    )


async def _collect_checks(db: Any) -> list[dict[str, Any]]:
    """采集轻量自检项（DB / pgvector），异常时降级为空列表，不影响导出。"""
    checks: list[dict[str, Any]] = []
    try:
        from app.core.db import check_database, check_pgvector

        db_ok, db_detail = await check_database()
        checks.append({"name": "database", "status": "ok" if db_ok else "fail", "detail": db_detail})
        vector_ok, vector_detail = await check_pgvector()
        checks.append(
            {"name": "pgvector", "status": "ok" if vector_ok else "fail", "detail": vector_detail}
        )
    except Exception as exc:  # noqa: BLE001 —— 诊断包必须尽量产出，不因自检失败中断
        checks.append({"name": "selfcheck", "status": "warn", "detail": type(exc).__name__})
    return checks
