"""Sessions 路由（含 SSE 流式对话）。

路由只做编排：解析入参 -> 调 SessionSvc / ChatSvc -> 套统一信封或编码 SSE 帧。
业务逻辑一律在 services/。

SSE 事件序列严格按契约（openapi.yaml / frontend types/session.ts）：
  world_info -> start -> delta* -> usage -> (image?) -> done；失败发 error。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.v1.deps import (
    DbSession,
    LimitParam,
    OrderParam,
    PageParam,
    QParam,
    SortParam,
    StatusParam,
)
from app.core.envelope import deleted
from app.schemas.common import Envelope, Paged
from app.schemas.session import (
    ContextSnapshot,
    ForkRequest,
    Message,
    MessageInput,
    RegenerateRequest,
    SessionCreateRequest,
    SessionUpdateRequest,
    StreamRequest,
)
from app.schemas.session import (
    Session as SessionSchema,
)
from app.services.chat import ChatSvc, assert_not_generating
from app.services.session import SessionSvc
from app.services.tokens import estimate_tokens

_SSE_RESPONSES = {
    200: {
        "description": "SSE 流（world_info -> start -> delta* -> usage -> (image?) -> done；失败发 error）",
        "content": {"text/event-stream": {"schema": {"type": "string"}}},
    }
}

router = APIRouter(tags=["Sessions"])


def _encode_sse(event: str, data: dict[str, Any]) -> str:
    """编码一个 SSE 帧：`event: <name>\\ndata: <json>\\n\\n`。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/sessions", response_model=Envelope[Paged[SessionSchema]], summary="列出会话")
async def list_sessions(
    db: DbSession,
    q: QParam = None,
    status: StatusParam = None,
    sort: SortParam = "updated_at",
    order: OrderParam = "desc",
    page: PageParam = 1,
    limit: LimitParam = 20,
) -> Envelope[Paged[SessionSchema]]:
    items, meta = await SessionSvc(db).list(
        q=q, status=status, page=page, limit=limit
    )
    return Envelope(data=Paged[SessionSchema](items=items, **meta))


@router.post(
    "/sessions",
    response_model=Envelope[SessionSchema],
    status_code=201,
    summary="开启一场会话",
)
async def create_session(db: DbSession, payload: SessionCreateRequest) -> Envelope[SessionSchema]:
    row = await SessionSvc(db).create(payload.model_dump(mode="json"))
    return Envelope(data=SessionSchema.model_validate(row))


@router.get("/sessions/{sessionId}", response_model=Envelope[SessionSchema], summary="获取会话")
async def get_session(
    db: DbSession, sessionId: str, include_messages: bool = True
) -> Envelope[SessionSchema]:
    data = await SessionSvc(db).get(sessionId, include_messages=include_messages)
    return Envelope(data=SessionSchema.model_validate(data))


@router.patch(
    "/sessions/{sessionId}", response_model=Envelope[SessionSchema], summary="更新会话"
)
async def update_session(
    db: DbSession, sessionId: str, payload: SessionUpdateRequest
) -> Envelope[SessionSchema]:
    row = await SessionSvc(db).update(sessionId, payload.model_dump(mode="json", exclude_unset=True))
    return Envelope(data=SessionSchema.model_validate(row))


@router.delete("/sessions/{sessionId}", response_model=Envelope[dict], summary="删除会话")
async def delete_session(db: DbSession, sessionId: str) -> Envelope[dict]:
    return Envelope(data=deleted(await SessionSvc(db).delete(sessionId)))


@router.post(
    "/sessions/{sessionId}/messages",
    response_model=Envelope[Message],
    status_code=201,
    summary="追加一条消息（不触发生成）",
)
async def append_message(db: DbSession, sessionId: str, payload: MessageInput) -> Envelope[Message]:
    svc = SessionSvc(db)
    row = await svc.get_row(sessionId)
    message = await svc.append_message(
        row.id,
        role=payload.role,
        content=payload.content,
        token_count=estimate_tokens(payload.content),
    )
    return Envelope(data=Message.model_validate(svc._message_to_dict(message)))


@router.post(
    "/sessions/{sessionId}/stream",
    summary="发送玩家输入并流式接收回复（SSE）",
    responses=_SSE_RESPONSES,
)
async def stream_chat(db: DbSession, sessionId: str, payload: StreamRequest) -> StreamingResponse:
    svc = ChatSvc(db)
    # 请求阶段先做并发预检：非 idle 立即 409（此时响应头尚未发出，状态码可生效）
    assert_not_generating(await SessionSvc(db).get_row(sessionId))

    async def _gen() -> AsyncIterator[str]:
        async for event, data in svc.stream_reply(
            sessionId,
            input_text=payload.input,
            overrides=payload.overrides or None,
        ):
            yield _encode_sse(event, data)

    return StreamingResponse(_gen(), media_type="text/event-stream")


@router.post(
    "/sessions/{sessionId}/regenerate",
    summary="重新生成（swipe）",
    responses=_SSE_RESPONSES,
)
async def regenerate_message(
    db: DbSession, sessionId: str, payload: RegenerateRequest
) -> StreamingResponse:
    svc = ChatSvc(db)
    svc_session = SessionSvc(db)
    assert_not_generating(await svc_session.get_row(sessionId))

    async def _gen() -> AsyncIterator[str]:
        # 取被重新生成的位置作为输入语义：用其前一条 user 消息内容重跑
        row = await svc_session.get_row(sessionId)
        messages = await svc_session.list_messages(row.id)
        regenerating = payload.message_id
        seed = ""
        prev_user = ""
        for msg in messages:
            if msg.role == "user":
                prev_user = msg.content
            if regenerating and str(msg.id) == str(regenerating):
                break
        seed = prev_user
        async for event, data in svc.stream_reply(
            sessionId,
            input_text=seed,
            overrides=payload.overrides or None,
            regenerate_message_id=str(regenerating) if regenerating else None,
        ):
            yield _encode_sse(event, data)

    return StreamingResponse(_gen(), media_type="text/event-stream")


@router.post(
    "/sessions/{sessionId}/interrupt",
    response_model=Envelope[dict],
    summary="中断当前生成（幂等）",
)
async def interrupt_session(db: DbSession, sessionId: str) -> Envelope[dict]:
    return Envelope(data=await ChatSvc(db).interrupt(sessionId))


@router.post(
    "/sessions/{sessionId}/fork",
    response_model=Envelope[SessionSchema],
    status_code=201,
    summary="分支会话",
)
async def fork_session(db: DbSession, sessionId: str, payload: ForkRequest) -> Envelope[SessionSchema]:
    data = await SessionSvc(db).fork(sessionId, payload.model_dump(mode="json"))
    return Envelope(data=SessionSchema.model_validate(data))


@router.get(
    "/sessions/{sessionId}/last-context",
    response_model=Envelope[ContextSnapshot],
    summary="获取上一轮真实组装的上下文与触发轨迹",
)
async def get_last_context(db: DbSession, sessionId: str) -> Envelope[ContextSnapshot]:
    row = await SessionSvc(db).get_row(sessionId)
    snapshot = dict(row.context or {})
    return Envelope(data=ContextSnapshot.model_validate(snapshot))
