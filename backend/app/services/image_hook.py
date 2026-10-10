"""图像出图钩子服务（架构 §4.8）。

本轮仅建立类与职责边界，完整实现见下一轮。
"""

from __future__ import annotations

from typing import Any


class ImageHook:
    """出图任务编排 + **服务端自动归档**。

    职责（下一轮实现）：
      - 触发（手动 / every_n_turns / on_scene_change）-> 入队 image_jobs
      - 后台 worker 调用 ImageProvider，不阻塞对话流
      - 完成时由服务端创建 kind=generated 的 assets 行，回填
        card_id / session_id / message_id / meta，置 archived=true，并登记进角色图集
      - 前端禁止自行拼装归档逻辑（schemas.md §10.2 铁律）
    """

    def __init__(self, session: Any | None = None) -> None:
        self._session = session
