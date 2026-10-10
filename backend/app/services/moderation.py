"""审核层编排服务（ADR-011 / SPEC §4.9 / F11）。

职责：
  - 从 config 读审核配置（app/services/config.py 的 ConfigSvc），组装 ModerationSettings
  - 输入/输出**双端**审核：命中即抛 ModerationBlockedError（4031 / HTTP 403）
  - **审核层可整体关闭**，但关闭时必须携带风险确认标记（risk_ack=true），
    否则拒绝保存（防止误关导致合规缺口）。该判定由 `assert_disable_allowed` 收口。

分层铁律：本服务只依赖 ModerationProvider 接口，绝不 import 厂商 SDK。
"""

from __future__ import annotations

from typing import Any

from app.adapters.base import ModerationVerdict
from app.adapters.moderation import BuiltinWordlistModerationProvider, ModerationSettings
from app.core.errors import BadRequestError, ModerationBlockedError
from app.core.logging import get_logger
from app.services.config import ConfigSvc

logger = get_logger(__name__)

# 关闭审核层所必须携带的风险确认标记（写入配置或请求时的键名）
RISK_ACK_KEY = "risk_ack"


def build_settings(config: dict[str, Any]) -> ModerationSettings:
    """把 /config/moderation 的配置 dict 转成适配器所需设置。"""
    rules = config.get("rules") or {}
    blocked = rules.get("blocked_words") or []
    words = tuple(str(w) for w in blocked if str(w).strip())
    return ModerationSettings(
        enabled=bool(config.get("enabled", True)),
        check_input=bool(config.get("check_input", True)),
        check_output=bool(config.get("check_output", True)),
        provider=str(config.get("provider") or "builtin_wordlist"),
        # 配置未提供词表时回落适配器内置最小词表
        blocked_words=words if words else ModerationSettings().blocked_words,
        block_on_match=bool(rules.get("block_on_match", True)),
        label_ai_generated=bool(rules.get("label_ai_generated", True)),
    )


def assert_disable_allowed(new_config: dict[str, Any], *, existing: dict[str, Any]) -> None:
    """校验「整体关闭审核」是否携带了风险确认标记。

    规则：仅当本次写入把 enabled 从「开」变「关」时要求风险确认；
    若本就关闭（幂等重复写）则放行。标记可随配置一起提交（risk_ack=true），
    也可由调用方以独立参数合并进来（见 validate_moderation_update）。
    """
    turning_off = not bool(new_config.get("enabled", True)) and bool(existing.get("enabled", True))
    if turning_off and not bool(new_config.get(RISK_ACK_KEY)):
        raise BadRequestError(
            "关闭内容审核层存在合规风险：请携带风险确认标记（risk_ack=true）后再提交。"
        )


def validate_moderation_update(
    payload: dict[str, Any], *, existing: dict[str, Any], risk_ack: bool | None = None
) -> dict[str, Any]:
    """校验并规整审核配置写入。

    - 关闭审核需风险确认（payload 内 risk_ack 或独立参数 risk_ack 任一为真即可）
    - risk_ack 仅用于校验，不落库（避免污染配置快照）
    返回可写入的配置 dict（已剔除 risk_ack）。
    """
    merged = dict(payload)
    if risk_ack is not None and not merged.get(RISK_ACK_KEY):
        merged[RISK_ACK_KEY] = risk_ack
    assert_disable_allowed(merged, existing=existing)
    merged.pop(RISK_ACK_KEY, None)
    return merged


class ModerationSvc:
    """输入/输出双端审核编排。"""

    def __init__(self, db: Any | None = None) -> None:
        self._db = db

    async def _provider(self, config: dict[str, Any]) -> BuiltinWordlistModerationProvider:
        return BuiltinWordlistModerationProvider(build_settings(config))

    async def load_config(self) -> dict[str, Any]:
        if self._db is None:
            return {
                "enabled": True,
                "check_input": True,
                "check_output": True,
                "provider": "builtin_wordlist",
                "rules": {},
            }
        return await ConfigSvc(self._db).get_moderation()

    async def check_input(self, text: str) -> ModerationVerdict:
        """输入侧审核：命中即抛 ModerationBlockedError（403）。"""
        config = await self.load_config()
        verdict = await (await self._provider(config)).check_input(text)
        self._enforce(verdict, side="input")
        return verdict

    async def check_output(self, text: str) -> ModerationVerdict:
        """输出侧审核：命中即抛 ModerationBlockedError（403）。"""
        config = await self.load_config()
        verdict = await (await self._provider(config)).check_output(text)
        self._enforce(verdict, side="output")
        return verdict

    @staticmethod
    def _enforce(verdict: ModerationVerdict, *, side: str) -> None:
        if not verdict.blocked:
            return
        default = (
            "输入内容未通过内容审核，请调整后再试。"
            if side == "input"
            else "生成内容未通过内容审核，已拦截。请调整输入或稍后重试。"
        )
        logger.info("moderation blocked", extra={"side": side, "matched": len(verdict.matched)})
        raise ModerationBlockedError(
            verdict.message or default,
            data={"side": side, "matched": list(verdict.matched)},
        )


__all__ = [
    "RISK_ACK_KEY",
    "ModerationSvc",
    "assert_disable_allowed",
    "build_settings",
    "validate_moderation_update",
]
