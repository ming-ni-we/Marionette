"""会话引擎服务：状态机 + 消息流 + 中断恢复。

本轮仅建立类与职责边界，完整实现见下一轮。
"""

from __future__ import annotations

from typing import Any


class SessionSvc:
    """会话生命周期与状态机编排（架构 §4.3）。

    职责（下一轮实现）：
      - 会话创建 / 分支（fork）/ 删除
      - 状态机显式迁移表，非法迁移必须拒绝
      - 乐观锁（state_machine.version）防并发双击；并发生成返回 409
      - 流式检查点：assistant 消息先落 status=streaming，结束转 complete / interrupted 转 incomplete
      - 服务重启回收滞留的 streaming 消息
    """

    def __init__(self, session: Any | None = None) -> None:
        self._session = session
