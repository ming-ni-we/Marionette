"""内置示例内容聚合入口（首启向导 `POST /api/v1/onboarding/samples`）。

铁律：示例内容必须**真实可用**（禁止占位文案）。
数据按类型分文件，避免单文件过长：
  - builtin_cards.py      4 张「现代日常向」角色卡
  - builtin_worldbooks.py 2 本世界书（城南街区 / 日常基调）
  - builtin_presets.py    1 个默认预设

全部为 rpg_card / rpg_worldbook / rpg_preset v1.0 原生信封，不含 emoji 图标字段。
"""

from __future__ import annotations

from app.services.builtin_cards import sample_cards
from app.services.builtin_presets import sample_presets
from app.services.builtin_worldbooks import sample_worldbooks

__all__ = ["sample_cards", "sample_presets", "sample_worldbooks"]
