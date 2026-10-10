"""Config 路由：LLM 后端 / 审核层 / 出图配置 + LLM 连通性测试（F1 / F6 / F12）。

路由只做编排：解析入参 -> 调 ConfigSvc / LLMProvider -> 套统一信封。
业务逻辑一律在 services/；密钥脱敏在 services/config.py 内收口。
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Query

from app.adapters.registry import get_llm_provider
from app.api.v1.deps import DbSession
from app.schemas.common import Envelope
from app.schemas.config import (
    ComfyUIProbeRequest,
    ConnectionTestResult,
    ImageConfig,
    ImageConfigInput,
    LlmConfig,
    LlmConfigInput,
    ModerationConfig,
)
from app.services.config import ConfigSvc
from app.services.moderation import validate_moderation_update

router = APIRouter(tags=["Config"])


@router.get("/config/llm", response_model=Envelope[LlmConfig], summary="获取当前 LLM 后端配置")
async def get_llm_config(db: DbSession) -> Envelope[LlmConfig]:
    return Envelope(data=LlmConfig.model_validate(await ConfigSvc(db).get_llm()))


@router.put("/config/llm", response_model=Envelope[LlmConfig], summary="设置 LLM 后端")
async def set_llm_config(db: DbSession, payload: LlmConfigInput) -> Envelope[LlmConfig]:
    saved = await ConfigSvc(db).set_llm(payload.model_dump(mode="json"))
    return Envelope(data=LlmConfig.model_validate(saved))


@router.post(
    "/config/llm/test",
    response_model=Envelope[ConnectionTestResult],
    summary="测试 LLM 连接（3 秒内返回成败 + 错误分类）",
)
async def test_llm_connection(
    db: DbSession, payload: LlmConfigInput
) -> Envelope[ConnectionTestResult]:
    """真实调用 LLM 适配器做连通性测试；失败复用适配器的 7 类 error_class 归类。

    说明：连通性测试**不读库**，直接用手填的入参，符合「在保存前先试探」的交互。
    但若 payload 未带 api_key（前端传脱敏占位），则回落库中已存的明文密钥。
    """
    settings = payload.model_dump(mode="json")
    api_key = settings.get("api_key") or ""
    if not api_key or "***" in api_key:
        api_key = (await ConfigSvc(db).get_llm_raw()).get("api_key", "")
    health = await get_llm_provider().test_connection(
        base_url=settings.get("base_url") or "",
        api_key=api_key,
        model=settings.get("model") or "",
    )
    return Envelope(
        data=ConnectionTestResult(
            ok=health.reachable,
            latency_ms=health.latency_ms,
            error_class=health.error_class.value if health.error_class else None,
            message=health.message,
            model_seen=health.model_seen,
        )
    )


@router.get(
    "/config/moderation",
    response_model=Envelope[ModerationConfig],
    summary="获取内容审核层配置",
)
async def get_moderation_config(db: DbSession) -> Envelope[ModerationConfig]:
    return Envelope(data=ModerationConfig.model_validate(await ConfigSvc(db).get_moderation()))


@router.put(
    "/config/moderation",
    response_model=Envelope[ModerationConfig],
    summary="设置内容审核层（可开关 / 可配置规则）",
)
async def set_moderation_config(
    db: DbSession,
    payload: ModerationConfig,
    risk_ack: bool = Query(
        False,
        description="关闭审核层（enabled=false）时的风险确认标记；缺失且本次为「开->关」则 400。",
    ),
) -> Envelope[ModerationConfig]:
    """写入审核配置。整体关闭时**必须**携带风险确认（risk_ack=true 或配置内 risk_ack=true）。"""
    svc = ConfigSvc(db)
    existing = await svc.get_moderation()
    fields = payload.model_dump(mode="json")
    # payload 内的 risk_ack 优先，其次取查询参数；risk_ack 不落库
    inline_ack = bool(fields.pop("risk_ack", False))
    cleaned = validate_moderation_update(
        fields, existing=existing, risk_ack=(inline_ack or risk_ack)
    )
    saved = await svc.set_moderation(cleaned)
    return Envelope(data=ModerationConfig.model_validate(saved))


@router.get("/config/image", response_model=Envelope[ImageConfig], summary="获取出图后端配置")
async def get_image_config(db: DbSession) -> Envelope[ImageConfig]:
    return Envelope(data=ImageConfig.model_validate(await ConfigSvc(db).get_image()))


@router.put("/config/image", response_model=Envelope[ImageConfig], summary="设置出图后端")
async def set_image_config(db: DbSession, payload: ImageConfigInput) -> Envelope[ImageConfig]:
    saved = await ConfigSvc(db).set_image(payload.model_dump(mode="json"))
    return Envelope(data=ImageConfig.model_validate(saved))


@router.post(
    "/config/comfyui/probe",
    response_model=Envelope[dict],
    summary="探测本机 ComfyUI 是否可用",
)
async def probe_comfyui(payload: ComfyUIProbeRequest) -> Envelope[dict]:
    """探测 ComfyUI 可达性（GET /system_stats）。v1 云端部署通常不可达，属正常。"""
    url = f"{payload.base_url.rstrip('/')}/system_stats"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url)
        if resp.status_code >= 400:
            return Envelope(
                data={"reachable": False, "detail": f"HTTP {resp.status_code}"},
                message="ComfyUI 未按预期返回。",
            )
        stats = resp.json()
        devices = stats.get("devices") or []
        device = devices[0].get("name") if devices else None
        checkpoints = [
            item.get("model_name")
            for item in (stats.get("checkpoints") or [])
            if isinstance(item, dict) and item.get("model_name")
        ]
        return Envelope(data={"reachable": True, "device": device, "checkpoints": checkpoints})
    except Exception as exc:  # noqa: BLE001 —— 网络类异常统一按不可达处理
        return Envelope(
            data={"reachable": False, "detail": type(exc).__name__},
            message="无法连接 ComfyUI：本机未运行或网络不可达。",
        )
