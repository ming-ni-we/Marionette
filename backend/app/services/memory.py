"""记忆与摘要服务（架构 §4.5）。

本轮仅建立类与职责边界，完整实现见下一轮。
"""

from __future__ import annotations

from typing import Any


class MemorySvc:
    """滚动摘要（段 A）+ 关键事实（段 B）；段 C 向量召回 v1 默认关闭。

    职责（下一轮实现）：
      - 未摘要历史 token 超过历史预算阈值（默认 80%）时触发摘要压缩
      - 推进 summary_upto_message_id，写入 memory_snapshots 版本
      - LLM 抽取关键事实 + 正则兜底，按 key 去重合并
      - 提供长期记忆块给 ContextAssembler
    """

    def __init__(self, session: Any | None = None) -> None:
        self._session = session
