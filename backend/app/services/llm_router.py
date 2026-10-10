"""LLM 调度服务：把预设 + 上下文交给 LLMProvider，处理流式与错误归类。

本轮仅建立类与职责边界，完整实现见下一轮。
"""

from __future__ import annotations

from typing import Any


class LLMRouter:
    """LLM 调用编排（v1 单后端）。

    职责（下一轮实现）：
      - 从配置解析 base_url / api_key / model，调用 LLMProvider.stream_chat
      - 流式产出的 delta 交给 SSE 层；usage 对账写回 context snapshot
      - 上游错误按 7 类 error_class 归类
      - 只依赖 LLMProvider 接口，禁止 import 任何厂商 SDK
    """

    def __init__(self, session: Any | None = None) -> None:
        self._session = session
