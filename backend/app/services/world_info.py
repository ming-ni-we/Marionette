"""世界书触发引擎（产品护城河，架构 §4.4）。

本轮仅建立类与职责边界，完整实现见下一轮。
"""

from __future__ import annotations

from typing import Any


class WorldInfoEngine:
    """关键词 / 正则 / 向量 / 递归 触发裁决。

    职责（下一轮实现）：
      - constant 无条件入选；其余按 scan_depth 扫描文本匹配
      - selective 需主/次关键词同时命中；match_whole_words / case_sensitive 控制
      - use_regex 编译失败降级为字面匹配并告警
      - 递归扫描受 max_recursion_depth 硬上限约束（防环）
      - insertion_order 升序排序；token 预算不足按 priority 降序保留
      - 输出逐条裁决 trace，供 /worldbooks/{id}/test 与 /sessions/{id}/last-context 消费
    """

    def __init__(self, session: Any | None = None) -> None:
        self._session = session
