"""对话编排服务：把「取卡/预设 -> 组装上下文 -> 流式生成 -> 落库」串起来（架构 §4.3/§4.6）。

对外只暴露一个异步生成器 `stream_reply()`，逐个产出 SSE 事件（event, data）。
路由层负责把事件编码成 text/event-stream 帧，本层不认识任何 HTTP 概念。

SSE 事件契约（openapi.yaml / frontend types/session.ts）：
  world_info -> start -> delta* -> usage -> (image?) -> done；失败发 error。

健壮性：
  - 生成期间同一会话再发起 -> ConflictError(409)：用 state_machine.current 抢占。
  - 客户端断开（GeneratorExit / CancelledError）-> 未完成 assistant 消息落 status=incomplete。
  - 上游错误 -> 发 error 事件，并把消息置 incomplete。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.ids import parse_uuid
from app.core.logging import get_logger
from app.models.card import Card
from app.models.preset import Preset
from app.models.worldbook import WorldBook
from app.services.context_assembler import ContextAssembler
from app.services.image_hook import ImageHook
from app.services.llm_router import LLMRouter
from app.services.moderation import ModerationSvc
from app.services.session import SessionSvc
from app.services.tokens import estimate_tokens

logger = get_logger(__name__)

# SSE 事件名（与前端 SseEventMap 严格一致）
EVT_WORLD_INFO = "world_info"
EVT_START = "start"
EVT_DELTA = "delta"
EVT_USAGE = "usage"
EVT_IMAGE = "image"
EVT_DONE = "done"
EVT_ERROR = "error"


def _round_tokens(tokens: int) -> int:
    return int(tokens)


class ChatSvc:
    """单会话的一轮流式生成编排。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._sessions = SessionSvc(db)
        self._assembler = ContextAssembler()
        self._router = LLMRouter(db)
        self._moderation = ModerationSvc(db)
        self._image = ImageHook(db)

    # ------------------------------------------------------------------ #
    async def _load_card_preset_worldbooks(
        self, session_row: Any
    ) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        card = (
            await self._db.execute(select(Card).where(Card.id == session_row.card_id))
        ).scalar_one_or_none()
        preset = (
            await self._db.execute(select(Preset).where(Preset.id == session_row.preset_id))
        ).scalar_one_or_none()
        if card is None:
            raise NotFoundError("会话绑定的角色卡已不存在，无法生成。")
        if preset is None:
            raise NotFoundError("会话绑定的预设已不存在，无法生成。")

        worldbooks: list[dict[str, Any]] = []
        wb_ids = [parse_uuid(w, field="worldbook_ids") for w in (session_row.worldbook_ids or [])]
        # 卡内世界书一并挂载
        embedded = (card.data or {}).get("character_book")
        if isinstance(embedded, dict):
            worldbooks.append(embedded)
        if wb_ids:
            rows = (
                await self._db.execute(select(WorldBook).where(WorldBook.id.in_(wb_ids)))
            ).scalars().all()
            worldbooks.extend([dict(r.data or {}) for r in rows])
        return dict(card.data or {}), dict(preset.data or {}), worldbooks

    # ------------------------------------------------------------------ #
    async def stream_reply(
        self,
        session_id: str,
        *,
        input_text: str,
        overrides: dict[str, Any] | None = None,
        regenerate_message_id: str | None = None,
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """产出 (event_name, payload) 事件流。"""
        session_row = await self._sessions.get_row(session_id)

        # 并发保护：仅 idle 可发起新的一轮；否则说明已有生成在进行 -> 409
        sm = {**(session_row.state_machine or {})}
        if sm.get("current") not in (None, "idle"):
            raise ConflictError(
                "当前会话正在生成中，请稍候或先中断。",
                data={"current": sm.get("current")},
            )

        # 输入侧审核（F11）：命中即 403（此刻响应头尚未发出，状态码可生效）。
        # regenerate 时以原始用户输入为审核对象（input_text 即前端回放的 seed）。
        if input_text:
            await self._moderation.check_input(input_text)

        self._sessions.transition_state(session_row, "assembling")
        session_row.status = "active" if session_row.status == "archived" else session_row.status
        await self._db.flush()

        assistant_row = None
        try:
            card, preset, worldbooks = await self._load_card_preset_worldbooks(session_row)

            # 落玩家输入（regenerate 时不重复落输入）
            if not regenerate_message_id:
                await self._sessions.append_message(
                    session_row.id, role="user", content=input_text,
                    token_count=estimate_tokens(input_text),
                )
            history = [
                {"id": str(m.id), "role": m.role, "content": m.content}
                for m in await self._sessions.list_messages(session_row.id)
                if m.status == "complete"
            ]

            # ---- 组装上下文 ----
            assembled = self._assembler.assemble(
                card=card,
                preset=preset,
                user_persona=dict(session_row.user_persona or {}),
                history=history,
                worldbooks=worldbooks,
                memory=dict(session_row.memory or {}),
                scan_text=input_text or "\n".join(m["content"] for m in history[-4:]),
            )

            # ---- world_info 事件 ----
            yield EVT_WORLD_INFO, {
                "triggered": [
                    {
                        "entry_id": d.get("entry_id"),
                        "match_type": d.get("match_type"),
                        "in_budget": bool(d.get("in_budget")),
                    }
                    for d in assembled.world_info_trace
                    if d.get("matched")
                ],
                "trace_id": str(uuid.uuid4()),
            }

            # ---- 落 assistant 占位（streaming）----
            assistant_row = await self._sessions.append_message(
                session_row.id,
                role="assistant",
                content="",
                status="streaming",
                token_count=0,
                meta={"triggered_entry_ids": assembled.triggered_entry_ids},
            )

            # 状态推进 generating
            self._sessions.transition_state(session_row, "generating")
            session_row.context = assembled.to_snapshot()
            await self._db.flush()

            # ---- start 事件 ----
            yield EVT_START, {
                "message_id": str(assistant_row.id),
                "estimated_prompt_tokens": assembled.estimated_prompt_tokens,
            }

            # ---- 流式 delta ----
            sampling = (preset.get("sampling") or {})
            params = {
                "temperature": sampling.get("temperature"),
                "top_p": sampling.get("top_p"),
                "max_tokens": sampling.get("max_tokens"),
                "stop": sampling.get("stop") or None,
            }
            params = {k: v for k, v in params.items() if v is not None}
            if overrides:
                params.update(overrides)

            collected: list[str] = []
            async for piece in self._router.stream(
                assembled.messages, params=params, overrides=overrides
            ):
                collected.append(piece)
                yield EVT_DELTA, {"text": piece}

            content = "".join(collected)
            completion_tokens = estimate_tokens(content)

            # 输出侧审核（F11）：命中即拦截（消息不落库为 complete，转 incomplete）
            await self._moderation.check_output(content)

            # ---- usage + 落库完成 ----
            await self._sessions.update_message(
                assistant_row,
                content=content,
                status="complete",
                token_count=completion_tokens,
            )
            self._sessions.transition_state(session_row, "post_processing")
            self._sessions.transition_state(session_row, "idle")
            sm = dict(session_row.state_machine or {})
            sm["turn"] = int(sm.get("turn", 0)) + 1
            session_row.state_machine = sm

            yield EVT_USAGE, {
                "prompt_tokens": _round_tokens(assembled.estimated_prompt_tokens),
                "completion_tokens": completion_tokens,
            }

            # ---- image 事件（F12 出图钩子）----
            # 出图请求可由 overrides.image 显式触发；失败不中断对话流（仅记录告警）。
            async for evt in self._maybe_image_events(
                overrides=overrides,
                session_row=session_row,
                assistant_row=assistant_row,
                content=content,
            ):
                yield evt

            yield EVT_DONE, {"message_id": str(assistant_row.id), "status": "complete"}

        except BaseException as exc:  # noqa: BLE001 —— 需覆盖 CancelledError/GeneratorExit
            # 客户端断开 / 上游失败：把未完成的 assistant 消息落为 incomplete，不留脏数据
            await self._finalize_incomplete(assistant_row, session_row, exc)
            if isinstance(exc, AppError):
                yield EVT_ERROR, {"code": exc.code, "message": exc.message}
            elif isinstance(exc, (GeneratorExit,)) or exc.__class__.__name__ in (
                "CancelledError",
                "GeneratorExit",
            ):
                # 客户端主动断开：连接已断，不发 error 事件，仅完成落库后向上抛
                raise
            else:
                logger.warning("chat stream failed: %s", type(exc).__name__)
                yield EVT_ERROR, {
                    "code": 5021,
                    "message": f"生成失败（{type(exc).__name__}）：请重试或检查后端配置。",
                }

    async def _maybe_image_events(
        self,
        *,
        overrides: dict[str, Any] | None,
        session_row: Any,
        assistant_row: Any,
        content: str,
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """若本轮显式请求出图（overrides.image），则出图 + **服务端自动归档** 并推送。

        - 归档由 ImageHook 完成（建 kind=generated 资产、回填 card/session/message、登记图集）
        - 出图失败不冒泡为对话失败：记 warning，不发 image 事件（对话仍正常 done）
        """
        spec = (overrides or {}).get("image")
        if spec is None or spec is False:
            return
        # spec 允许为 true（用本轮回复文本作提示词）或 {prompt, ...} 明细
        if spec is True or spec is None:
            spec = {}
        if not isinstance(spec, dict):
            return
        prompt = str(spec.get("prompt") or content).strip()
        if not prompt:
            return
        params = {
            k: spec[k]
            for k in ("negative_prompt", "width", "height", "seed", "steps")
            if k in spec
        }
        try:
            job = await self._image.generate_and_archive(
                prompt=prompt,
                params=params or None,
                card_id=session_row.card_id,
                session_id=session_row.id,
                message_id=assistant_row.id,
            )
        except Exception as exc:  # noqa: BLE001 —— 出图失败不影响对话主流程
            logger.warning("image hook failed: %s", type(exc).__name__)
            return
        if job.asset_id is not None:
            yield EVT_IMAGE, {"asset_id": str(job.asset_id), "job_id": str(job.id)}

    async def _finalize_incomplete(
        self, assistant_row: Any, session_row: Any, exc: BaseException
    ) -> None:
        try:
            if assistant_row is not None and assistant_row.status == "streaming":
                # 保留已生成的部分内容，只把状态置 incomplete
                await self._sessions.update_message(assistant_row, status="incomplete")
            sm = dict(session_row.state_machine or {})
            if sm.get("current") != "idle":
                error = None
                if isinstance(exc, AppError):
                    error = {"code": exc.code, "message": exc.message}
                self._sessions.transition_state(session_row, "idle", error=error)
            await self._db.flush()
        except Exception as inner:  # noqa: BLE001 —— 收尾失败不能掩盖主异常
            logger.warning("finalize incomplete failed: %s", type(inner).__name__)

    async def interrupt(self, session_id: str) -> dict[str, Any]:
        """中断当前生成（幂等）：把 streaming 消息置 incomplete，状态回 idle。"""
        session_row = await self._sessions.get_row(session_id)
        messages = await self._sessions.list_messages(session_row.id)
        interrupted = False
        for row in messages:
            if row.status == "streaming":
                await self._sessions.update_message(row, status="incomplete")
                interrupted = True
        sm = dict(session_row.state_machine or {})
        if sm.get("current") not in (None, "idle"):
            sm["current"] = "idle"
            sm["version"] = int(sm.get("version", 0)) + 1
            session_row.state_machine = sm
        await self._db.flush()
        return {"interrupted": interrupted}


def assert_not_generating(session_row: Any) -> None:
    """供路由在进入流式前做快速校验（真正抢占仍在 stream_reply 内）。"""
    sm = session_row.state_machine or {}
    if sm.get("current") not in (None, "idle"):
        raise ConflictError(
            "当前会话正在生成中，请稍候或先中断。", data={"current": sm.get("current")}
        )


__all__ = ["ChatSvc", "assert_not_generating"]
