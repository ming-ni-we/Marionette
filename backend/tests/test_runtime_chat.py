"""ChatSvc 流式编排单测（sqlite + mock LLMRouter，无需真实上游）。

验证：
  - 事件序列 world_info -> start -> delta* -> usage -> done
  - assistant 消息落库 status=complete，内容拼接正确
  - 上游失败 -> 发 error 事件且消息置 incomplete（不留脏数据）
  - 并发发起 -> ConflictError(409)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError


class _FakeRouter:
    """可控的 LLMRouter 替身：按脚本产出 delta 或抛错。"""

    def __init__(self, pieces: list[str] | None = None, error: Exception | None = None) -> None:
        self._pieces = pieces or []
        self._error = error

    async def stream(self, messages: Any, **kwargs: Any) -> AsyncIterator[str]:
        if self._error is not None:
            raise self._error
        for piece in self._pieces:
            yield piece


@pytest.mark.asyncio
async def test_stream_event_sequence(
    db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.chat import ChatSvc
    from app.services.session import SessionSvc

    card_id, preset_id = card_and_preset
    svc = SessionSvc(db)
    created = await svc.create(
        {"character_card_id": str(card_id), "preset_id": str(preset_id), "greeting_index": -1}
    )
    sid = str(created["id"])

    chat = ChatSvc(db)
    monkeypatch.setattr(chat, "_router", _FakeRouter(pieces=["她", "笑了", "。"]))

    events: list[tuple[str, dict[str, Any]]] = []
    async for event, data in chat.stream_reply(sid, input_text="你好"):
        events.append((event, data))

    names = [e for e, _ in events]
    assert names[0] == "world_info"
    assert names[1] == "start"
    assert names[-2] == "usage"
    assert names[-1] == "done"
    assert names.count("delta") == 3

    # assistant 消息落库完整
    messages = await svc.list_messages(__import__("uuid").UUID(sid))
    assistant = [m for m in messages if m.role == "assistant"]
    last = assistant[-1]
    assert last.content == "她笑了。"
    assert last.status == "complete"


@pytest.mark.asyncio
async def test_stream_upstream_error_marks_incomplete(
    db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.errors import ErrorClass, UpstreamError
    from app.services.chat import ChatSvc
    from app.services.session import SessionSvc

    card_id, preset_id = card_and_preset
    svc = SessionSvc(db)
    created = await svc.create(
        {"character_card_id": str(card_id), "preset_id": str(preset_id), "greeting_index": -1}
    )
    sid = str(created["id"])

    chat = ChatSvc(db)
    monkeypatch.setattr(
        chat,
        "_router",
        _FakeRouter(error=UpstreamError("上游挂了", error_class=ErrorClass.network_unreachable)),
    )

    events = [e async for e, _ in chat.stream_reply(sid, input_text="你好")]
    assert "error" in events
    assert "done" not in events

    import uuid

    messages = await svc.list_messages(uuid.UUID(sid))
    assistant = [m for m in messages if m.role == "assistant"][-1]
    assert assistant.status == "incomplete"


@pytest.mark.asyncio
async def test_concurrent_stream_conflicts(
    db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.chat import ChatSvc
    from app.services.session import SessionSvc

    card_id, preset_id = card_and_preset
    svc = SessionSvc(db)
    created = await svc.create(
        {"character_card_id": str(card_id), "preset_id": str(preset_id), "greeting_index": -1}
    )
    sid = str(created["id"])

    chat = ChatSvc(db)
    monkeypatch.setattr(chat, "_router", _FakeRouter(pieces=["x"]))

    agen = chat.stream_reply(sid, input_text="第一次")
    await agen.__anext__()  # 推进到 world_info（状态已切到 assembling/generating 之间）

    # 第二次并发发起：抢占失败 -> 409
    with pytest.raises(ConflictError):
        async for _ in chat.stream_reply(sid, input_text="第二次"):
            pass

    await agen.aclose()
