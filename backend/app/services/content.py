"""内容仓库服务（角色卡 / 世界书 / 预设的 CRUD 与检索）。

本轮仅建立类与职责边界，完整实现见下一轮。
"""

from __future__ import annotations

from typing import Any


class ContentSvc:
    """内容对象的读写编排。

    职责（下一轮实现）：
      - cards / worldbooks / presets 的增删改查与分页
      - 关键词检索走 SearchProvider（pg_trgm + ILIKE，ADR-005）
      - 写入时维护 tags 反规范化列与 name 字段
      - spec_version 高于支持版本时拒绝写入（schemas.md §1 铁律 2）
    """

    def __init__(self, session: Any | None = None) -> None:
        self._session = session
