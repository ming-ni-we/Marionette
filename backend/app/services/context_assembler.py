"""上下文组装器（Context Engineering，架构 §4.6）。

本轮仅建立类与职责边界，完整实现见下一轮。
"""

from __future__ import annotations

from typing import Any


class ContextAssembler:
    """把角色卡 / 世界书命中 / 记忆 / 历史装配成最终 prompt。

    职责（下一轮实现）：
      - 严格按 §4.6 的 11 段顺序组装，占位符单遍替换（未知占位符原样保留 + 告警）
      - 按 preset.context_budget 分配各段 token 预算，超限按 §4.5 裁剪顺序处理
      - 组装结果全量落库（prompt 全文 + 各段 token + 世界书 trace + 预算占用）
      - 用固定夹具跑黄金 prompt 快照测试，守住「沉默逻辑错误」
    """

    def __init__(self, session: Any | None = None) -> None:
        self._session = session
