"""System 路由：运行时信息与启动自检（公开，免鉴权）。"""

from __future__ import annotations

from fastapi import APIRouter

from app.adapters.registry import get_llm_provider
from app.core.config import SCHEMA_VERSIONS, get_settings
from app.core.db import check_database, check_pgvector
from app.schemas.common import Envelope
from app.schemas.system import (
    LlmReachability,
    SelfCheckItem,
    SelfCheckResult,
    SystemInfo,
)

router = APIRouter(tags=["System"])


@router.get(
    "/system/info",
    response_model=Envelope[SystemInfo],
    summary="运行时能力与版本信息",
)
async def get_system_info() -> Envelope[SystemInfo]:
    s = get_settings()
    return Envelope(
        data=SystemInfo(
            app_version=s.app_version,
            schema_versions=dict(SCHEMA_VERSIONS),
            llm_provider=s.llm_provider,
            llm_model=s.llm_model,
            embedding_model="BAAI/bge-large-zh-v1.5",
            gpu_available=False,  # 云端单实例无 GPU；本地推理为可选后端
            image_provider=s.image_provider,
        )
    )


@router.get(
    "/system/selfcheck",
    response_model=Envelope[SelfCheckResult],
    summary="启动自检（DB / pgvector / LLM 连通性）",
    description=(
        "首启链路第 1 步。返回逐项自检结果与中文修复指引。"
        "其中 db / pgvector / llm.reachable 三项为 SPEC §12 端到端验证的断言字段。"
    ),
)
async def system_selfcheck() -> Envelope[SelfCheckResult]:
    s = get_settings()
    checks: list[SelfCheckItem] = []

    db_ok, db_detail = await check_database()
    checks.append(
        SelfCheckItem(
            name="database",
            status="ok" if db_ok else "fail",
            detail=db_detail,
            fix_hint="" if db_ok else "docker compose ps 确认 db 容器 healthy；核对 .env 的 DB_PASSWORD。",
        )
    )

    vector_ok, vector_detail = await check_pgvector()
    checks.append(
        SelfCheckItem(
            name="pgvector",
            status="ok" if vector_ok else "fail",
            detail=vector_detail,
            fix_hint="" if vector_ok else "镜像必须为 pgvector/pgvector:pg18，并确认迁移已执行 CREATE EXTENSION vector。",
        )
    )

    if s.llm_configured:
        health = await get_llm_provider().test_connection(
            base_url=s.llm_base_url, api_key=s.llm_api_key, model=s.llm_model
        )
        llm = LlmReachability(
            reachable=health.reachable,
            error_class=health.error_class.value if health.error_class else None,
            message=health.message,
        )
        checks.append(
            SelfCheckItem(
                name="llm",
                status="ok" if health.reachable else "warn",
                detail=health.message,
                fix_hint="" if health.reachable else "在设置页填写可用的 LLM base_url / api_key / model。",
            )
        )
    else:
        llm = LlmReachability(
            reachable=False,
            error_class=None,
            message="尚未配置 LLM 后端（LLM_BASE_URL / LLM_MODEL 为空）。",
        )
        checks.append(
            SelfCheckItem(
                name="llm",
                status="warn",
                detail=llm.message,
                fix_hint="在首启向导中填写 LLM 后端后即可对话。",
            )
        )

    if not db_ok or not vector_ok:
        overall = "failed"
    elif not llm.reachable:
        overall = "degraded"
    else:
        overall = "ok"

    result = SelfCheckResult(
        db="ok" if db_ok else "fail",
        pgvector="ok" if vector_ok else "fail",
        llm=llm,
        overall=overall,
        checks=checks,
    )
    return Envelope(data=result)
