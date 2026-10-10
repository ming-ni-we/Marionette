"""SillyTavern 兼容适配器（导入导出，schemas.md §3.4 / §4.4）。

本轮仅建立类与职责边界，完整实现见下一轮。
"""

from __future__ import annotations

from typing import Any


class STCompatAdapter:
    """ST V1/V2/V3 <-> 平台 Schema 的双向转换。

    职责（下一轮实现）：
      - 载体解析：.json / .png(tEXt chara) / .webp；V3(ccv3) 优先于 V2(chara)
      - 同名字段一一映射；未知字段收进 extensions.st_unknown 并原样写回（不销毁）
      - key/keys、disable/enabled、order/insertion_order 归一
      - 导出可回导为 Tavern V2；可选产出 PNG 卡片
    """

    def __init__(self, session: Any | None = None) -> None:
        self._session = session
