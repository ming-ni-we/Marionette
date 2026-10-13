"""对话编排服务：把「取卡/预设 -> 组装上下文 -> 流式生成 -> 落库」串起来（架构 §4.3/§4.6）。

对外只暴露一个异步生成器 `stream_reply()`，逐个产出 SSE 事件（event, data）。
路由层负责把事件编码成 text/event-stream 帧，本层不认识任何 HTTP 概念。

**双模式分派**（剧情引擎开关，零迁移）：
  - `session.spec == "rpg_session"`（缺省）→ 原 1v1 单角色管线，**一字节未改**
  - `session.spec == "story_session"`     → `_stream_story_round()` 多角色导演管线
  分派点在 `stream_reply()` 内部，路由零改动；老行天然走老路径。

SSE 事件契约（openapi.yaml / frontend types/session.ts）：
  1v1 ： world_info -> start -> delta* -> usage -> (image?) -> done；失败发 error。
  剧情： world_info -> director -> start -> (delta* | speaker_switch -> delta*)*
         -> node? -> usage -> (image?) -> actions -> done；失败发 error。
  超集特性：老前端 `KNOWN_EVENTS` 白名单**天然丢弃**未知事件 → 零破坏。

健壮性：
  - 生成期间同一会话再发起 -> ConflictError(409)：用 state_machine.current 抢占。
  - 客户端断开（GeneratorExit / CancelledError）-> 未完成 assistant 消息落 status=incomplete。
  - **多角色模式下本轮可能落多条 assistant 消息**，收尾必须遍历全部（见 `_finalize_incomplete`）。
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
from app.services.action_suggester import ActionSuggesterSvc
from app.services.context_assembler import ContextAssembler
from app.services.director import DirectorSvc
from app.services.image_hook import ImageHook
from app.services.llm_router import LLMRouter
from app.services.moderation import ModerationSvc
from app.services.session import SessionSvc
from app.services.story_state import StoryStateSvc, is_story_session
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

# 剧情模式新增事件（前端 SseEventMap 需同步扩 4 个键）
EVT_DIRECTOR = "director"
EVT_SPEAKER_SWITCH = "speaker_switch"
EVT_NODE = "node"
EVT_ACTIONS = "actions"

#: 单轮最多演出的角色数（与 DirectorDecision.MAX_SPEAKERS 对齐的上限保护）
_MAX_ROUND_SPEAKERS = 3


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
        # 剧情引擎（仅 spec=story_session 时使用；1v1 路径不触碰）
        self._story_state = StoryStateSvc(db)
        self._director = DirectorSvc(db)
        self._suggester = ActionSuggesterSvc(db)

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

        # ---- 模式分派：剧情会话走多角色导演管线，1v1 走原有管线 ----
        # 分派点放在此处（而非路由），是为了复用上面的并发抢占与输入审核；
        # 也保证两条管线共享同一个 `assembling` 起始状态与收尾契约。
        if is_story_session(session_row):
            async for event in self._stream_story_round(
                session_row,
                input_text=input_text,
                overrides=overrides,
                regenerate_message_id=regenerate_message_id,
            ):
                yield event
            return

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

    # ------------------------------------------------------------------ #
    # 剧情模式：多角色导演管线（S6）
    # ------------------------------------------------------------------ #
    async def _stream_story_round(
        self,
        session_row: Any,
        *,
        input_text: str,
        overrides: dict[str, Any] | None = None,
        regenerate_message_id: str | None = None,
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """剧情模式单轮：导演裁决 → 逐角色演出 → 收尾建议。

        事件序列：
          world_info → director → start → (delta* | speaker_switch → delta*)*
          → node? → usage → (image?) → actions → done

        **不抛异常**：导演与建议都有降级；只有「角色演出」的 LLM 流式失败会走
        统一的 error 事件（与 1v1 同口径）。任何中断路径都会调用
        `_finalize_incomplete(assistant_rows=...)` 收干净本轮全部消息。
        """
        assistant_rows: list[Any] = []
        try:
            card, preset, worldbooks = await self._load_card_preset_worldbooks(session_row)
            world = await self._load_world(session_row)

            # 落玩家输入（regenerate 时不重复落输入）
            if not regenerate_message_id:
                await self._sessions.append_message(
                    session_row.id,
                    role="user",
                    content=input_text,
                    token_count=estimate_tokens(input_text),
                )

            history = await self._story_history(session_row)

            # ---- 导演裁决（永不抛异常）----
            story = self._story_state.get_story(session_row)
            cast = self._story_state.get_cast(session_row)
            relations = self._story_state.get_relations(session_row)
            scene = self._story_state.get_scene_story(session_row)
            turn = int((session_row.state_machine or {}).get("turn") or 0)

            fallback_speaker = self._pick_fallback_speaker(session_row, scene)
            decision = await self._director.decide(
                card=card,
                preset=preset,
                story=story,
                cast=cast,
                relations=relations,
                scene=scene,
                history=history,
                user_input=input_text,
                outline=(world.get("outline") if isinstance(world, dict) else None),
                fallback_speaker=fallback_speaker,
                circuit_open=self._story_state.is_director_circuit_open(session_row),
                overrides=overrides,
            )
            if decision.degraded:
                self._story_state.mark_director_failure(session_row)
            else:
                self._story_state.mark_director_success(session_row, turn)

            # ---- 应用裁决中的世界状态变更（同一事务内）----
            if decision.scene_patch:
                self._story_state.apply_scene_update(session_row, decision.scene_patch)
            if decision.flags:
                self._story_state.apply_flags(session_row, decision.flags)
            if decision.relation_updates:
                self._story_state.apply_relation_updates(session_row, decision.relation_updates)

            # ---- world_info 事件（与 1v1 同结构，前端零改动）----
            assembled = self._assembler.assemble(
                card=card,
                preset=preset,
                user_persona=dict(session_row.user_persona or {}),
                history=history,
                worldbooks=worldbooks,
                memory=dict(session_row.memory or {}),
                scan_text=input_text or "\n".join(str(m.get("content") or "") for m in history[-4:]),
            )
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

            # ---- director 事件（先发，让前端立刻渲染裁决面板）----
            yield EVT_DIRECTOR, decision.to_payload()

            # ---- speaker 列表：导演指定，为空则退化为「在场首位」纯旁白 ----
            speakers = self._resolve_speakers(session_row, decision, scene, cast)

            # ---- start 事件 ----
            # 不预建消息行：首个说话者的占位行在下方的演出循环里创建。
            # 这样「N 个说话者 = N 条消息」，不会多出一条空占位（历史 bug）。
            # start 的 message_id 允许为空串：前端在收到首个 `speaker_switch`/`delta`
            # 时拿到真实 id；1v1 契约里该字段总是有值，剧情模式放宽为可空。
            yield EVT_START, {
                "message_id": "",
                "estimated_prompt_tokens": assembled.estimated_prompt_tokens,
            }

            self._sessions.transition_state(session_row, "generating")
            session_row.context = assembled.to_snapshot()
            await self._db.flush()

            # ---- 旁白段（导演给的 narration，直接落一条旁白消息，不走 LLM）----
            if decision.narration:
                narration_row = await self._sessions.append_message(
                    session_row.id,
                    role="assistant",
                    content=decision.narration,
                    status="complete",
                    token_count=estimate_tokens(decision.narration),
                    meta=self._narration_meta(turn),
                )
                assistant_rows.append(narration_row)
                yield EVT_SPEAKER_SWITCH, {
                    "speaker_id": None,
                    "speaker_name": "",
                    "is_narration": True,
                    "message_id": str(narration_row.id),
                }

            # ---- 逐角色演出 ----
            usage_prompt = assembled.estimated_prompt_tokens
            usage_completion = 0
            said: list[dict[str, Any]] = []
            for index, speaker in enumerate(speakers):
                if index > 0:
                    yield EVT_SPEAKER_SWITCH, {
                        "speaker_id": speaker.get("id"),
                        "speaker_name": speaker.get("name"),
                        "is_narration": False,
                    }
                row = await self._append_speaker_placeholder(
                    session_row, speaker=speaker, turn=turn, decision=decision
                )
                assistant_rows.append(row)

                collected: list[str] = []
                async for piece in self._router.stream(
                    self._build_speaker_prompt(
                        assembled=assembled,
                        speaker=speaker,
                        decision=decision,
                        speakers=speakers,
                        said=said,
                        scene=self._story_state.get_scene_story(session_row),
                    ),
                    params=self._speaker_params(preset),
                    overrides=overrides,
                ):
                    collected.append(piece)
                    yield EVT_DELTA, {"text": piece, "speaker_id": speaker.get("id")}

                content = "".join(collected)
                await self._moderation.check_output(content)
                tokens = estimate_tokens(content)
                usage_completion += tokens
                await self._sessions.update_message(
                    row, content=content, status="complete", token_count=tokens
                )
                said.append(
                    {"id": speaker.get("id"), "name": speaker.get("name"), "content": content}
                )

            # ---- 节点事件（导演判定触发）----
            if decision.node_triggered:
                self._story_state.set_story(
                    session_row,
                    {"node_id": decision.node_triggered.get("id"), "pending_node": None},
                )
                yield EVT_NODE, {
                    "id": decision.node_triggered.get("id"),
                    "title": decision.node_triggered.get("title"),
                    "brief": decision.node_triggered.get("brief"),
                }

            # ---- 收尾：状态回 idle + 推进轮次与拍点 ----
            self._sessions.transition_state(session_row, "post_processing")
            self._sessions.transition_state(session_row, "idle")
            sm = dict(session_row.state_machine or {})
            sm["turn"] = turn + 1
            session_row.state_machine = sm
            self._story_state.bump_turn(session_row)
            await self._db.flush()

            yield EVT_USAGE, {
                "prompt_tokens": _round_tokens(usage_prompt),
                "completion_tokens": usage_completion,
            }

            # ---- image 事件（沿用 1v1 的出图钩子；本轮无任何消息则跳过）----
            if assistant_rows:
                async for evt in self._maybe_image_events(
                    overrides=overrides,
                    session_row=session_row,
                    assistant_row=assistant_rows[-1],
                    content=said[-1]["content"] if said else decision.narration,
                ):
                    yield evt

            # ---- actions 事件（行动建议；失败静默，不影响 done）----
            suggestions = await self._suggest_actions(
                session_row, said=said, overrides=overrides
            )
            if suggestions:
                yield EVT_ACTIONS, {"actions": suggestions}

            yield EVT_DONE, {
                "message_id": str(assistant_rows[-1].id) if assistant_rows else "",
                "status": "complete",
                "turn": turn + 1,
            }

        except BaseException as exc:  # noqa: BLE001 —— 需覆盖 CancelledError/GeneratorExit
            await self._finalize_incomplete(
                assistant_rows[-1] if assistant_rows else None,
                session_row,
                exc,
                assistant_rows=assistant_rows,
            )
            if isinstance(exc, AppError):
                yield EVT_ERROR, {"code": exc.code, "message": exc.message}
            elif isinstance(exc, GeneratorExit) or exc.__class__.__name__ in (
                "CancelledError",
                "GeneratorExit",
            ):
                # 客户端主动断开：连接已断，不发 error 事件，仅完成落库后向上抛
                raise
            else:
                logger.warning("story stream failed: %s", type(exc).__name__)
                yield EVT_ERROR, {
                    "code": 5021,
                    "message": f"生成失败（{type(exc).__name__}）：请重试或检查后端配置。",
                }

    # ------------------------------------------------------------------ #
    # 剧情模式辅助
    # ------------------------------------------------------------------ #
    async def _load_world(self, session_row: Any) -> dict[str, Any]:
        """载入会话绑定的世界观（**只读**，用于取 outline 与开场信息）。

        世界观可能在会话进行中被删除 —— 此时返回空 dict，剧情靠 `extensions.story`
        里的固化副本继续，不会因此中断。
        """
        world_id = self._story_state.extract_world_id(session_row)
        if not world_id:
            return {}
        try:
            uid = parse_uuid(world_id, field="world_id")
        except AppError:
            return {}
        from app.models.world import World

        row = (await self._db.execute(select(World).where(World.id == uid))).scalar_one_or_none()
        if row is None:
            return {}
        return {
            "id": str(row.id),
            "title": row.title,
            "setting": dict(row.setting or {}),
            "outline": dict(row.outline or {}),
            "opening": row.opening or "",
        }

    async def _story_history(self, session_row: Any) -> list[dict[str, Any]]:
        """带说话者名的历史（导演与角色演出都需要知道「谁说了什么」）。"""
        rows = await self._sessions.list_messages(session_row.id)
        cast_map = self._story_state.get_cast_map(session_row)
        history: list[dict[str, Any]] = []
        for msg in rows:
            if msg.status != "complete":
                continue
            meta = msg.meta or {}
            speaker_id = meta.get("speaker_id")
            name = meta.get("speaker_name") or ""
            if not name and speaker_id:
                name = (cast_map.get(str(speaker_id)) or {}).get("name") or ""
            history.append(
                {
                    "id": str(msg.id),
                    "role": msg.role,
                    "content": msg.content,
                    "name": name,
                    "is_narration": bool(meta.get("is_narration")),
                }
            )
        return history

    def _pick_fallback_speaker(self, session_row: Any, scene: dict[str, Any]) -> dict[str, Any] | None:
        """导演降级时让它继续说话的角色：上一说话者的下一位（环形轮转）。"""
        present = scene.get("present") or []
        if not present:
            cast = self._story_state.get_cast(session_row)
            return cast[0] if cast else None
        nxt = self._story_state.next_speaker_after(session_row, scene.get("last_speaker_id"))
        if not nxt:
            return None
        return {"id": nxt, **(self._story_state.get_cast_map(session_row).get(nxt) or {})}

    def _resolve_speakers(
        self,
        session_row: Any,
        decision: Any,
        scene: dict[str, Any],
        cast: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """把导演的 speaker 列表对齐到 cast（补名字、过滤陌生 id）。"""
        cast_map = {str(c.get("id") or ""): c for c in cast if c.get("id")}
        out: list[dict[str, Any]] = []
        for item in (decision.speakers or [])[:_MAX_ROUND_SPEAKERS]:
            sid = str(item.get("id") or "")
            if not sid:
                continue
            member = cast_map.get(sid) or {}
            out.append(
                {
                    "id": sid,
                    "name": item.get("name") or member.get("name") or sid,
                    "voice": member.get("voice") or "",
                    "goals": member.get("goals") or [],
                    "intent": item.get("intent") or "",
                    "direction": item.get("direction") or "",
                }
            )
        if not out and decision.degraded:
            # 降级且导演没给 speaker：退化为上一说话者下一位，保证对话继续
            fallback = self._pick_fallback_speaker(session_row, scene)
            if fallback and fallback.get("id"):
                out.append(
                    {
                        "id": str(fallback["id"]),
                        "name": fallback.get("name") or str(fallback["id"]),
                        "voice": fallback.get("voice") or "",
                        "goals": fallback.get("goals") or [],
                        "intent": "承接玩家上一轮的言行",
                        "direction": fallback.get("voice") or "",
                    }
                )
        return out

    async def _append_speaker_placeholder(
        self, session_row: Any, *, speaker: dict[str, Any], turn: int, decision: Any
    ) -> Any:
        return await self._sessions.append_message(
            session_row.id,
            role="assistant",
            content="",
            status="streaming",
            token_count=0,
            meta=self._speaker_meta(speaker=speaker, turn=turn, decision=decision),
        )

    @staticmethod
    def _speaker_meta(*, speaker: dict[str, Any] | None, turn: int, decision: Any) -> dict[str, Any]:
        return {
            "speaker_id": (speaker or {}).get("id"),
            "speaker_name": (speaker or {}).get("name") or None,
            "speaker_avatar_asset_id": None,
            "is_narration": False,
            "is_director_note": False,
            "story_node_id": (decision.node_triggered or {}).get("id"),
            "turn": turn,
            "beat_role": "reply",
            "direction": (speaker or {}).get("direction") or "",
            "intent": (speaker or {}).get("intent") or "",
        }

    @staticmethod
    def _narration_meta(turn: int) -> dict[str, Any]:
        return {
            "speaker_id": None,
            "speaker_name": None,
            "speaker_avatar_asset_id": None,
            "is_narration": True,
            "is_director_note": False,
            "turn": turn,
            "beat_role": "narration",
        }

    @staticmethod
    def _speaker_params(preset: dict[str, Any]) -> dict[str, Any]:
        sampling = preset.get("sampling") or {}
        params = {
            "temperature": sampling.get("temperature"),
            "top_p": sampling.get("top_p"),
            "max_tokens": sampling.get("max_tokens"),
            "stop": sampling.get("stop") or None,
        }
        return {k: v for k, v in params.items() if v is not None}

    def _build_speaker_prompt(
        self,
        *,
        assembled: Any,
        speaker: dict[str, Any],
        decision: Any,
        speakers: list[dict[str, Any]],
        said: list[dict[str, Any]],
        scene: dict[str, Any],
    ) -> list[Any]:
        """在装配好的基座 prompt 之上，追加「本轮你演谁 + 导演指示」。

        做法：不重写装配器，只在其产出的 messages 末尾追加一条 system 指令。
        好处是角色定义/世界书/记忆/历史全部复用同一套预算与裁剪逻辑。
        """
        from app.adapters.base import ChatMessage

        lines = [
            f"【本轮你扮演】{speaker.get('name')}（id={speaker.get('id')}）",
        ]
        if speaker.get("voice"):
            lines.append(f"语气风格：{speaker['voice']}")
        if speaker.get("goals"):
            lines.append("你的目标：" + "、".join(str(g) for g in speaker["goals"][:3]))
        if speaker.get("intent"):
            lines.append(f"本轮意图：{speaker['intent']}")
        if speaker.get("direction"):
            lines.append(f"表演提示：{speaker['direction']}")
        if decision.narration:
            lines.append(f"刚刚的旁白：{decision.narration}")
        for other in speakers:
            if other.get("id") == speaker.get("id"):
                continue
            lines.append(f"本轮还有 {other.get('name')} 也在场，稍后会发言，不要替他说话。")
        if said:
            lines.extend(
                ["本轮已经发生："]
                + [f"{s['name']}：{s['content']}" for s in said if s.get("content")]
            )
        if scene.get("beat"):
            lines.append(f"本拍：{scene['beat']}")
        lines.append(
            "只输出这个角色的台词与动作描写（用「」包裹台词，动作直接叙述），"
            "不要写旁白、不要替其他角色说话、不要加任何前缀标签。"
        )
        return [*assembled.messages, ChatMessage(role="system", content="\n".join(lines))]

    async def _suggest_actions(
        self, session_row: Any, *, said: list[dict[str, Any]], overrides: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        """生成行动建议；任何失败都静默返回空列表（前端自动隐藏建议区）。"""
        try:
            recent: list[dict[str, Any]] = []
            for msg in (await self._sessions.list_messages(session_row.id))[-6:]:
                if msg.status != "complete":
                    continue
                meta = msg.meta or {}
                recent.append(
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "name": meta.get("speaker_name") or "",
                    }
                )
            return await self._suggester.suggest(
                scene=self._story_state.get_scene_story(session_row),
                story=self._story_state.get_story(session_row),
                cast=self._story_state.get_cast(session_row),
                recent_messages=recent,
                overrides=overrides,
            )
        except Exception as exc:  # noqa: BLE001 —— 建议失败不影响对话
            logger.warning("action suggest failed: %s", type(exc).__name__)
            return []

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
        self,
        assistant_row: Any,
        session_row: Any,
        exc: BaseException,
        *,
        assistant_rows: list[Any] | None = None,
    ) -> None:
        """收尾：把本轮**全部**未完成的 assistant 消息置 incomplete，状态回 idle。

        ⚠️ 剧情模式下单轮会产出多条 assistant 消息（每个说话者一条）。原实现只处理
        `assistant_row` 单条，多角色中断时会残留 `status="streaming"` 的脏数据 ——
        这些行会在下次列表渲染时被当作「正在生成」，且破坏 seq 恢复语义。
        修复：优先遍历调用方传入的 `assistant_rows`（本轮全部落库的 assistant 行），
        并**兜底扫库**，把任何漏网的 streaming 行一并收掉，保证幂等。
        """
        try:
            rows: list[Any] = list(assistant_rows or [])
            if not rows and assistant_row is not None:
                rows.append(assistant_row)

            # 兜底：直接查库捞本轮遗留的 streaming 行（防调用方漏传 / 中途抛错）
            try:
                messages = await self._sessions.list_messages(session_row.id)
            except Exception:  # noqa: BLE001 —— 查库失败不该掩盖主异常
                messages = []
            known = {str(getattr(r, "id", "")) for r in rows if r is not None}
            for candidate in messages:
                if candidate.status == "streaming" and str(candidate.id) not in known:
                    rows.append(candidate)
                    known.add(str(candidate.id))

            for row in rows:
                if row is not None and row.status == "streaming":
                    # 保留已生成的部分内容，只把状态置 incomplete
                    await self._sessions.update_message(row, status="incomplete")

            sm = dict(session_row.state_machine or {})
            if sm.get("current") != "idle":
                error = None
                if isinstance(exc, AppError):
                    error = {"code": exc.code, "message": exc.message}
                self._force_idle(session_row, error=error)
            await self._db.flush()
        except Exception as inner:  # noqa: BLE001 —— 收尾失败不能掩盖主异常
            logger.warning("finalize incomplete failed: %s", type(inner).__name__)

    def _force_idle(self, session_row: Any, *, error: dict[str, Any] | None = None) -> None:
        """无条件把单轮状态机拉回 idle（容错版，绕过迁移表校验）。

        为什么不能用 `transition_state`：迁移表里 `generating` 只能去
        `post_processing|interrupted|error`，**没有直达 idle 的边**。收尾路径必须
        保证「无论从哪个状态中断，都能回 idle」，否则会话会被永久卡死在 generating，
        玩家再也发不出下一轮（比脏消息更严重）。

        代价：跳过一次迁移表校验。为保留可追溯性，版本号照常 +1 并记录 last_error，
        日志里也留下状态迁移痕迹。
        """
        sm = dict(session_row.state_machine or {})
        previous = sm.get("current")
        if previous != "idle":
            logger.info(
                "state forced to idle",
                extra={"from": previous, "session": str(getattr(session_row, "id", ""))},
            )
        sm["current"] = "idle"
        sm["version"] = int(sm.get("version", 0)) + 1
        sm["last_error"] = error
        session_row.state_machine = sm

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
