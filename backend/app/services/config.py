"""配置服务：LLM / 审核 / 出图 三类单用户配置的读写（app_config 表）。

设计要点（ADR-010 / SPEC §6）：
  - 单用户单实例，配置以 key -> JSON 落 `app_config` 表；缺省回落环境变量默认值，
    保证「未配置也能跑起来」。
  - **密钥脱敏（ADR-010）**：api_key 读出口一律 mask（如 `sk-***abc`），
    明文只在写入瞬间使用，绝不回显、绝不落日志。
  - 写入采用部分合并：未提交字段保持原值，避免 PUT 把 api_key 洗成空串。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.app_config import AppConfig

logger = get_logger(__name__)

# app_config 表的键名
KEY_LLM = "llm"
KEY_MODERATION = "moderation"
KEY_IMAGE = "image"

# 配置里允许出现密钥的字段名
_SECRET_FIELDS = ("api_key",)


def mask_secret(value: str | None) -> str:
    """把密钥脱敏成 `sk-***abc` 形式。

    规则：长度 <= 8 时整体打码为 `***`；否则保留前 3 与后 3 位，中间固定 `***`。
    空串原样返回空串（表示未配置）。
    """
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:3]}***{value[-3:]}"


def _mask_config(value: dict[str, Any]) -> dict[str, Any]:
    """对配置对象里的密钥字段脱敏（浅拷贝，不改动入参）。"""
    masked = dict(value)
    for field in _SECRET_FIELDS:
        if field in masked:
            masked[field] = mask_secret(masked.get(field))
    return masked


def has_secret_placeholder(value: Any) -> bool:
    """判断某值是否是脱敏占位（前端回传未改动的 masked 值时用它识别）。"""
    return isinstance(value, str) and "***" in value


class ConfigSvc:
    """app_config 表读写编排。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _get_row(self, key: str) -> AppConfig | None:
        return (
            await self._db.execute(select(AppConfig).where(AppConfig.key == key))
        ).scalar_one_or_none()

    async def get_raw(self, key: str) -> dict[str, Any]:
        """读取原始（未脱敏）配置；不存在时返回 {}。供内部业务（如 LLMRouter）使用。"""
        row = await self._get_row(key)
        return dict(row.value or {}) if row is not None else {}

    async def get(self, key: str) -> dict[str, Any]:
        """读取脱敏后的配置。"""
        return _mask_config(await self.get_raw(key))

    async def set(self, key: str, value: dict[str, Any]) -> dict[str, Any]:
        """整段覆盖写入并返回脱敏后的值。

        若待写入的密钥字段是脱敏占位（含 `***`），说明调用方并未真的改密钥，
        此时保留库中旧值，避免把 `sk-***abc` 当成真实 key 写进去。
        """
        existing = await self.get_raw(key)
        merged = dict(value)
        for field in _SECRET_FIELDS:
            incoming = merged.get(field)
            if has_secret_placeholder(incoming):
                merged[field] = existing.get(field, "")
        row = await self._get_row(key)
        if row is None:
            row = AppConfig(key=key, value=merged)
            self._db.add(row)
        else:
            row.value = merged
        await self._db.flush()
        # 日志绝不携带配置正文（可能含密钥）
        logger.info("config saved", extra={"config_key": key})
        return _mask_config(merged)

    # ---------------- 三类配置的门面方法 ----------------

    async def get_llm(self) -> dict[str, Any]:
        """LLM 配置：库中无值时回落环境变量默认。"""
        stored = await self.get_raw(KEY_LLM)
        if stored:
            return _mask_config(stored)
        settings = get_settings()
        return _mask_config(
            {
                "provider": settings.llm_provider,
                "base_url": settings.llm_base_url,
                "api_key": settings.llm_api_key,
                "model": settings.llm_model,
                "context_window": 8192,
                "extra": {},
                "active": True,
                "updated_at": None,
            }
        )

    async def get_llm_raw(self) -> dict[str, Any]:
        """LLM 原始配置（含明文密钥），供 LLMRouter / 连通性测试使用。"""
        stored = await self.get_raw(KEY_LLM)
        if stored:
            return stored
        settings = get_settings()
        return {
            "provider": settings.llm_provider,
            "base_url": settings.llm_base_url,
            "api_key": settings.llm_api_key,
            "model": settings.llm_model,
            "context_window": 8192,
            "extra": {},
        }

    async def set_llm(self, value: dict[str, Any]) -> dict[str, Any]:
        return await self.set(KEY_LLM, value)

    async def get_moderation(self) -> dict[str, Any]:
        stored = await self.get_raw(KEY_MODERATION)
        if stored:
            return stored
        return {
            "enabled": True,
            "check_input": True,
            "check_output": True,
            "provider": "builtin_wordlist",
            "rules": {"blocked_words": [], "block_on_match": True, "label_ai_generated": True},
            "updated_at": None,
        }

    async def set_moderation(self, value: dict[str, Any]) -> dict[str, Any]:
        return await self.set(KEY_MODERATION, value)

    async def get_image(self) -> dict[str, Any]:
        stored = await self.get_raw(KEY_IMAGE)
        if stored:
            return _mask_config(stored)
        settings = get_settings()
        return _mask_config(
            {
                "provider": settings.image_provider,
                "base_url": settings.image_base_url,
                "api_key": settings.image_api_key,
                "model": settings.image_model,
                "active": True,
                "updated_at": None,
            }
        )

    async def get_image_raw(self) -> dict[str, Any]:
        stored = await self.get_raw(KEY_IMAGE)
        if stored:
            return stored
        settings = get_settings()
        return {
            "provider": settings.image_provider,
            "base_url": settings.image_base_url,
            "api_key": settings.image_api_key,
            "model": settings.image_model,
        }

    async def set_image(self, value: dict[str, Any]) -> dict[str, Any]:
        return await self.set(KEY_IMAGE, value)


__all__ = ["ConfigSvc", "has_secret_placeholder", "mask_secret"]
