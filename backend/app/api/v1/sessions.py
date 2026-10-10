"""Sessions 路由（含 SSE 流式对话）。本轮返回 501（下一轮实现）。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.deps import (
    LimitParam,
    OrderParam,
    PageParam,
    QParam,
    SortParam,
    StatusParam,
)
from app.core.errors import UnimplementedError
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

_SSE_RESPONSES = {
    200: {
        "description": "SSE 流（world_info -> start -> delta* -> usage -> (image?) -> done；失败发 error）",
        "content": {"text/event-stream": {"schema": {"type": "string"}}},
    }
}

router = APIRouter(tags=["Sessions"])


@router.get("/sessions", response_model=Envelope[Paged[SessionSchema]], summary="列出会话")
async def list_sessions(
    q: QParam = None,
    status: StatusParam = None,
    sort: SortParam = "updated_at",
    order: OrderParam = "desc",
    page: PageParam = 1,
    limit: LimitParam = 20,
) -> Envelope[Paged[SessionSchema]]:
    raise UnimplementedError("会话列表")


@router.post(
    "/sessions",
    response_model=Envelope[SessionSchema],
    status_code=201,
    summary="开启一场会话",
)
async def create_session(payload: SessionCreateRequest) -> Envelope[SessionSchema]:
    raise UnimplementedError("开启会话")


@router.get("/sessions/{sessionId}", response_model=Envelope[SessionSchema], summary="获取会话")
async def get_session(
    sessionId: str, include_messages: bool = True
) -> Envelope[SessionSchema]:
    raise UnimplementedError("获取会话")


@router.patch(
    "/sessions/{sessionId}", response_model=Envelope[SessionSchema], summary="更新会话"
)
async def update_session(
    sessionId: str, payload: SessionUpdateRequest
) -> Envelope[SessionSchema]:
    raise UnimplementedError("更新会话")


@router.delete("/sessions/{sessionId}", response_model=Envelope[dict], summary="删除会话")
async def delete_session(sessionId: str) -> Envelope[dict]:
    raise UnimplementedError("删除会话")


@router.post(
    "/sessions/{sessionId}/messages",
    response_model=Envelope[Message],
    status_code=201,
    summary="追加一条消息（不触发生成）",
)
async def append_message(sessionId: str, payload: MessageInput) -> Envelope[Message]:
    raise UnimplementedError("追加消息")


@router.post(
    "/sessions/{sessionId}/stream",
    summary="发送玩家输入并流式接收回复（SSE）",
    responses=_SSE_RESPONSES,
)
async def stream_chat(sessionId: str, payload: StreamRequest) -> None:
    raise UnimplementedError("流式对话")


@router.post(
    "/sessions/{sessionId}/interrupt",
    response_model=Envelope[dict],
    summary="中断当前生成（幂等）",
)
async def interrupt_session(sessionId: str) -> Envelope[dict]:
    raise UnimplementedError("中断生成")


@router.post(
    "/sessions/{sessionId}/regenerate",
    summary="重新生成（swipe）",
    responses=_SSE_RESPONSES,
)
async def regenerate_message(sessionId: str, payload: RegenerateRequest) -> None:
    raise UnimplementedError("重新生成")


@router.post(
    "/sessions/{sessionId}/fork",
    response_model=Envelope[SessionSchema],
    status_code=201,
    summary="分支会话",
)
async def fork_session(sessionId: str, payload: ForkRequest) -> Envelope[SessionSchema]:
    raise UnimplementedError("分支会话")


@router.get(
    "/sessions/{sessionId}/last-context",
    response_model=Envelope[ContextSnapshot],
    summary="获取上一轮真实组装的上下文与触发轨迹",
)
async def get_last_context(sessionId: str) -> Envelope[ContextSnapshot]:
    raise UnimplementedError("上下文检视")
