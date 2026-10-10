"""首启向导：安装内置示例内容（F1 / AC-16 的"有内容可看"）。

顺序：先建世界书（拿到真实 id）-> 再建卡片并把世界书 id 写进 default_worldbook_ids -> 最后建预设。
示例内容来自 builtin_content，全部为真实可玩的「现代日常向」角色。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.services.builtin_content import sample_cards, sample_presets, sample_worldbooks
from app.services.content import content_service

logger = get_logger(__name__)


async def install_samples(db: AsyncSession) -> dict[str, Any]:
    worldbooks = content_service(db, "worldbook")
    cards = content_service(db, "card")
    presets = content_service(db, "preset")

    worldbook_ids: list[str] = []
    for payload in sample_worldbooks():
        row = await worldbooks.create(payload)
        worldbook_ids.append(str(row.id))

    card_ids: list[str] = []
    for payload in sample_cards(worldbook_ids):
        row = await cards.create(payload)
        card_ids.append(str(row.id))

    preset_ids: list[str] = []
    for payload in sample_presets():
        row = await presets.create(payload)
        preset_ids.append(str(row.id))

    logger.info(
        "onboarding samples installed",
        extra={
            "cards": len(card_ids),
            "worldbooks": len(worldbook_ids),
            "presets": len(preset_ids),
        },
    )
    return {
        "card_ids": card_ids,
        "worldbook_ids": worldbook_ids,
        "preset_ids": preset_ids,
    }


__all__ = ["install_samples"]
