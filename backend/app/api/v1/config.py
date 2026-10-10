"""Config 路由（LLM / 审核 / ComfyUI 探测）。本轮返回 501（下一轮实现）。"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.errors import UnimplementedError
from app.schemas.common import Envelope
from app.schemas.config import (
    ComfyUIProbeRequest,
    ConnectionTestResult,
    LlmConfig,
    LlmConfigInput,
    ModerationConfig,
)

router = APIRouter(tags=["Config"])


@router.get("/config/llm", response_model=Envelope[LlmConfig], summary="获取当前 LLM 后端配置")
async def get_llm_config() -> Envelope[LlmConfig]:
    raise UnimplementedError("读取 LLM 配置")


@router.put("/config/llm", response_model=Envelope[LlmConfig], summary="设置 LLM 后端")
async def set_llm_config(payload: LlmConfigInput) -> Envelope[LlmConfig]:
    raise UnimplementedError("保存 LLM 配置")


@router.post(
    "/config/llm/test",
    response_model=Envelope[ConnectionTestResult],
    summary="测试 LLM 连接（3 秒内返回成败 + 错误分类）",
)
async def test_llm_connection(payload: LlmConfigInput) -> Envelope[ConnectionTestResult]:
    raise UnimplementedError("LLM 连通性测试")


@router.get(
    "/config/moderation",
    response_model=Envelope[ModerationConfig],
    summary="获取内容审核层配置",
)
async def get_moderation_config() -> Envelope[ModerationConfig]:
    raise UnimplementedError("读取审核配置")


@router.put(
    "/config/moderation",
    response_model=Envelope[ModerationConfig],
    summary="设置内容审核层",
)
async def set_moderation_config(payload: ModerationConfig) -> Envelope[ModerationConfig]:
    raise UnimplementedError("保存审核配置")


@router.post(
    "/config/comfyui/probe",
    response_model=Envelope[dict],
    summary="探测本机 ComfyUI 是否可用",
)
async def probe_comfyui(payload: ComfyUIProbeRequest) -> Envelope[dict]:
    raise UnimplementedError("ComfyUI 探测")
