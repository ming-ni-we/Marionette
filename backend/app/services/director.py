"""AI 导演服务（剧情引擎核心，§4）。

**导演 = 剧情的世界模拟器**：每轮玩家行动后，先由导演「裁决」这一轮的世界如何反应
（谁说话、说什么方向、场景怎么变、是否触发剧情节点、关系怎么变），再由 ChatSvc
按裁决逐角色演出。

对外只暴露 `decide()`，它**绝不抛异常** —— 三层降级保证对话永远能继续：
  L0 熔断：连续失败 ≥3 次 → 直接 `fallback()`，不再浪费一次 LLM 调用
  L1 首选：带 `response_format={"type":"json_object"}` 请求
  L2 重试：端点不支持 response_format（400/422）→ 去掉该参数重试一次
  L3 兜底：仍失败 / JSON 解析不出来 → `fallback()` 单角色降级

分层铁律：本服务只依赖 LLMRouter 与纯函数，不认识 FastAPI / HTTP / ORM 模型类。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.adapters.base import ChatMessage
from app.core.logging import get_logger
from app.services.llm_router import LLMRouter

logger = get_logger(__name__)

# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #
#: 导演输出的 JSON Schema 说明（塞进 system prompt；比原生 schema 更兼容）
_DIRECTOR_SYSTEM = """你是一台剧情世界模拟器（AI 导演），负责裁决文字冒险故事中「接下来发生什么」。

你的职责（**只裁决，不写正文**）：
1. 依据玩家这一轮的言行，判断世界如何反应；
2. 决定本轮由**哪些**角色登场说话/行动，以及各自的意图与语气方向；
3. 判断是否满足某个剧情节点的触发条件，是否需推进场景；
4. 输出角色关系的变化（结盟/结仇/猜忌等）。

铁律：
- 你不写台词，只给「意图 + 表演方向」，具体台词交给角色自己说。
- 严格输出**单个 JSON 对象**，不要 markdown 代码围栏，不要任何解释性文字。
- 字段缺失或不确定时，用空字符串 / 空数组 / null，不要编造不存在的角色 id。

输出格式（严格遵循）：
{
  "speakers": [                      // 按发言顺序，1~3 个；空数组表示纯旁白推进
    {"id": "角色id", "name": "角色名", "intent": "本轮意图", "direction": "语气与动作提示"}
  ],
  "narration": "一段克制的情景旁白（可空）",
  "scene_patch": {"location": "", "time": "", "mood": "", "beat": "", "present": ["角色id"]},
  "node_triggered": {"id": "节点id", "title": "节点标题", "brief": "发生了什么"} | null,
  "relation_updates": [{"from": "id", "to": "id", "kind": "", "tension": 0.0, "note": ""}],
  "flags": {"标记名": true},
  "reason": "一句话说明你的裁决理由"
}"""

#: 采样参数：导演要稳定不要创意（温度低）。
#:
#: `max_tokens` 曾设为 512 —— 在「角色设定简短、单角色发言」的世界观下够用，
#: 但只要遇到**角色 voice/goals 写得较详细**、或导演一轮点了 2~3 个 speaker 的
#: 场景，裁决 JSON 就写不完被截断：`_extract_json` 找不到闭合括号 → 判为不可解析
#: → 连 L2 重试也大概率同样截断 → 最终降级为 `fallback()` 单角色接话。
#:
#: 降级是静默的（只在日志留 WARNING），表现为：永远同一个角色说话、
#: `node_triggered` 恒为 null、行动建议为空 —— 玩家会以为「这就是引擎的水平」。
#: 实测（2026-10-13，线上 deepseek-chat）《木叶·雾中之刃》连续 8 轮全部降级。
#:
#: 1024 给「3 speaker × 详细 intent/direction + narration + relations + flags」留足余量，
#: 单轮成本增加可忽略（导演本就要输出这么多内容，512 只是把它砍断而已）。
_DIRECTOR_PARAMS: dict[str, Any] = {"temperature": 0.4, "max_tokens": 1024}

#: 触发「输出疑似被截断」告警的字符数下限。
#:
#: 解析失败 + 输出长度接近上限 → 大概率是截断，而不是模型乱写。
#: 区分这两种情况对排查很关键：前者要调 max_tokens，后者要改提示词。
_DIRECTOR_TRUNCATION_HINT = 600

#: response_format 参数（L1 优先使用）
_JSON_FORMAT: dict[str, Any] = {"type": "json_object"}

#: tension 合法区间
_TENSION_MIN, _TENSION_MAX = -1.0, 1.0

#: speakers 上限（防导演一口气点一堆角色导致 token 爆炸）
MAX_SPEAKERS = 3

# 从 ```json ... ``` 或 ``` ... ``` 围栏里抠出内容
_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


# --------------------------------------------------------------------------- #
# 决策对象
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DirectorDecision:
    """导演一轮的裁决结果（不可变）。

    `speakers` 为空 = 本轮纯旁白推进（无角色台词），这不是错误 —— 是合法的「环境描写」拍。
    """

    speakers: list[dict[str, Any]] = field(default_factory=list)
    narration: str = ""
    scene_patch: dict[str, Any] = field(default_factory=dict)
    node_triggered: dict[str, Any] | None = None
    relation_updates: list[dict[str, Any]] = field(default_factory=list)
    flags: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    #: 本条决策是否来自降级路径（fallback）。前端可据此提示「导演暂时离线」
    degraded: bool = False

    # ------------------------------------------------------------------ #
    @classmethod
    def from_json(cls, raw: Any) -> DirectorDecision:
        """从任意 JSON 值构造决策，**永不抛异常**（畸形字段逐个吞掉）。

        所有字段都做类型与边界清洗：导演是小模型，输出脏是常态。
        """
        if not isinstance(raw, dict):
            return cls()
        return cls(
            speakers=cls._clean_speakers(raw.get("speakers")),
            narration=str(raw.get("narration") or "").strip(),
            scene_patch=cls._clean_scene_patch(raw.get("scene_patch")),
            node_triggered=cls._clean_node(raw.get("node_triggered")),
            relation_updates=cls._clean_relation_updates(raw.get("relation_updates")),
            flags=cls._clean_flags(raw.get("flags")),
            reason=str(raw.get("reason") or "").strip(),
            degraded=False,
        )

    @classmethod
    def fallback(cls, *, reason: str, speaker: dict[str, Any] | None = None) -> DirectorDecision:
        """单角色降级决策。

        `speaker` 给出时让它继续说话（保持体验连续）；为 None 时退化为纯旁白，
        由 ChatSvc 决定是否强行指定一位在场角色。
        """
        speakers: list[dict[str, Any]] = []
        if speaker and speaker.get("id"):
            speakers = [
                {
                    "id": str(speaker.get("id") or ""),
                    "name": str(speaker.get("name") or ""),
                    "intent": "承接玩家上一轮的言行，自然回应",
                    "direction": str(speaker.get("voice") or ""),
                }
            ]
        return cls(speakers=speakers, narration="", reason=reason, degraded=True)

    # ------------------------------------------------------------------ #
    # 字段清洗
    # ------------------------------------------------------------------ #
    @staticmethod
    def _clean_speakers(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        out: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            sid = str(item.get("id") or "").strip()
            if not sid:
                continue  # 无 id 无法关联 cast，丢弃
            out.append(
                {
                    "id": sid,
                    "name": str(item.get("name") or "").strip(),
                    "intent": str(item.get("intent") or "").strip(),
                    "direction": str(item.get("direction") or "").strip(),
                }
            )
            if len(out) >= MAX_SPEAKERS:
                break
        return out

    @staticmethod
    def _clean_scene_patch(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        patch: dict[str, Any] = {}
        for key in ("location", "time", "mood", "beat", "summary"):
            if key in value:
                text = str(value.get(key) or "").strip()
                if text:
                    patch[key] = text
        present = value.get("present")
        if isinstance(present, list):
            ids = [str(x).strip() for x in present if str(x or "").strip()]
            if ids:
                patch["present"] = ids
        return patch

    @staticmethod
    def _clean_node(value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        nid = str(value.get("id") or "").strip()
        if not nid:
            return None
        return {
            "id": nid,
            "title": str(value.get("title") or "").strip(),
            "brief": str(value.get("brief") or "").strip(),
        }

    @staticmethod
    def _clean_relation_updates(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        out: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            src = str(item.get("from") or "").strip()
            dst = str(item.get("to") or "").strip()
            if not src or not dst:
                continue
            clean: dict[str, Any] = {"from": src, "to": dst}
            kind = str(item.get("kind") or "").strip()
            if kind:
                clean["kind"] = kind
            note = str(item.get("note") or "").strip()
            if note:
                clean["note"] = note
            if "tension" in item:
                try:
                    value_f = float(item["tension"])
                except (TypeError, ValueError):
                    value_f = None
                if value_f is not None:
                    clean["tension"] = max(_TENSION_MIN, min(_TENSION_MAX, value_f))
            out.append(clean)
        return out

    @staticmethod
    def _clean_flags(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        # 只接受标量值：flag 是「世界事实」，不该是结构体
        return {
            str(k): v
            for k, v in value.items()
            if isinstance(v, (bool, int, float, str)) and str(k).strip()
        }

    # ------------------------------------------------------------------ #
    def to_payload(self) -> dict[str, Any]:
        """序列化为 SSE `director` 事件的载荷（供前端渲染裁决面板/调试）。"""
        return {
            "speakers": [dict(s) for s in self.speakers],
            "narration": self.narration,
            "scene_patch": dict(self.scene_patch),
            "node_triggered": dict(self.node_triggered) if self.node_triggered else None,
            "relation_updates": [dict(r) for r in self.relation_updates],
            "flags": dict(self.flags),
            "reason": self.reason,
            "degraded": self.degraded,
        }


# --------------------------------------------------------------------------- #
# JSON 解析（三策略）
# --------------------------------------------------------------------------- #
def _extract_json(text: str) -> Any | None:
    """从 LLM 文本里抠出 JSON 对象。三策略依次尝试，全败返回 None。

    1. 直接 `json.loads`（理想情况：端点已保证纯 JSON）
    2. 剥 markdown 代码围栏后再试
    3. 取第一个 `{` 到最后一个 `}` 的切片（应对模型在 JSON 前后加解释）
    """
    if not text:
        return None
    text = text.strip()

    for candidate in (
        text,
        *(_FENCE_RE.findall(text)),
    ):
        parsed = _try_load(candidate)
        if parsed is not None:
            return parsed

    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        return _try_load(text[start : end + 1])
    return None


def _try_load(candidate: str) -> Any | None:
    try:
        parsed = json.loads(candidate.strip())
    except (ValueError, TypeError):
        return None
    # 只认对象：数组/标量都不是合法的导演输出
    return parsed if isinstance(parsed, dict) else None


# --------------------------------------------------------------------------- #
# 提示词构造（纯函数，可单测）
# --------------------------------------------------------------------------- #
def _render_cast(cast: list[dict[str, Any]]) -> str:
    if not cast:
        return "（暂无角色群信息）"
    lines: list[str] = []
    for member in cast[:24]:  # 上限防 token 爆炸
        cid = str(member.get("id") or "")
        if not cid:
            continue
        bits = [f"- id={cid} 名={member.get('name') or cid}"]
        if member.get("role"):
            bits.append(f"身份={member['role']}")
        if member.get("voice"):
            bits.append(f"语气={member['voice']}")
        goals = member.get("goals") or []
        if isinstance(goals, list) and goals:
            bits.append("目标=" + "、".join(str(g) for g in goals[:3]))
        lines.append("；".join(bits))
    return "\n".join(lines) if lines else "（暂无角色群信息）"


def _render_relations(cast_ids: set[str], relations: list[dict[str, Any]]) -> str:
    if not relations:
        return "（暂无关系数据）"
    lines: list[str] = []
    for rel in relations[:40]:
        src = str(rel.get("from") or "")
        dst = str(rel.get("to") or "")
        if not src or not dst:
            continue
        if cast_ids and (src not in cast_ids or dst not in cast_ids):
            continue  # 关系引用已不在场的角色，忽略（防脏数据污染）
        try:
            tension = float(rel.get("tension") or 0.0)
        except (TypeError, ValueError):
            tension = 0.0
        lines.append(
            f"- {src} → {dst}：{rel.get('kind') or '关系'}（亲密度 {tension:+.1f}）"
            + (f"，{rel['note']}" if rel.get("note") else "")
        )
    return "\n".join(lines) if lines else "（暂无关系数据）"


def _render_outline(story: dict[str, Any], outline: dict[str, Any] | None) -> str:
    """把世界观大纲渲染成「剩余节点」清单，供导演判断触发。"""
    source = outline or {}
    nodes = source.get("nodes") or []
    main_goal = str(source.get("main_goal") or "").strip()
    parts: list[str] = []
    if main_goal:
        parts.append(f"主线目标：{main_goal}")
    fired = str(story.get("node_id") or "")
    pending = story.get("pending_node") or {}
    pending_id = str(pending.get("id") or "") if isinstance(pending, dict) else ""
    remaining: list[str] = []
    for node in nodes[:20]:
        if not isinstance(node, dict):
            continue
        nid = str(node.get("id") or "")
        if not nid or nid == fired:
            continue  # 已触发的节点不再提示
        mark = "【已满足待落定】" if nid == pending_id else ""
        remaining.append(
            f"- id={nid} {node.get('title') or ''}{mark}；触发条件：{node.get('trigger') or '未指定'}"
        )
    if remaining:
        parts.append("尚未触发的剧情节点：\n" + "\n".join(remaining))
    else:
        parts.append("剧情节点已全部触发，可自由推进或收束。")
    return "\n".join(parts)


def build_decision_prompt(
    *,
    card: dict[str, Any],
    preset: dict[str, Any],
    story: dict[str, Any],
    cast: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    scene: dict[str, Any],
    history: list[dict[str, Any]],
    user_input: str,
    outline: dict[str, Any] | None = None,
) -> list[ChatMessage]:
    """构造导演决策的 messages（纯函数）。

    刻意**不复用** ContextAssembler：导演需要的是「世界事实的结构化摘要」，
    而不是演出用的角色扮演 prompt。两者职责不同，分开更清晰也更省 token。
    """
    cast_ids = {str(c.get("id") or "") for c in cast if c.get("id")}
    present = [str(x) for x in (scene.get("present") or []) if str(x or "")]

    system_text = str((preset.get("prompt_template") or {}).get("system") or "").strip()
    world_summary = str(card.get("scenario") or card.get("description") or "").strip()

    blocks: list[str] = [_DIRECTOR_SYSTEM]

    if system_text:
        blocks.append("【演出基座设定（仅供你理解世界，不是你的输出格式）】\n" + system_text[:1200])
    if world_summary:
        blocks.append("【世界背景】\n" + world_summary[:800])

    blocks.append(
        "【当前场景】\n"
        f"地点：{scene.get('location') or '未指定'}\n"
        f"时间：{scene.get('time') or '未指定'}\n"
        f"氛围：{scene.get('mood') or '未指定'}\n"
        f"本拍：{scene.get('beat') or '未指定'}\n"
        f"在场角色：{', '.join(present) if present else '（未指定）'}"
    )
    blocks.append(
        "【剧情进度】\n"
        f"当前幕：{story.get('arc_id') or 'act1'}｜拍点序号：{story.get('beat_index') or 0}\n"
        + _render_outline(story, outline)
    )
    flags = story.get("flags") or {}
    if flags:
        blocks.append(
            "【已知世界事实】\n"
            + "\n".join(f"- {k} = {v}" for k, v in list(flags.items())[:20])
        )
    blocks.append("【可登场角色】\n" + _render_cast(cast))
    blocks.append("【角色关系】\n" + _render_relations(cast_ids, relations))

    recent = history[-8:]
    if recent:
        blocks.append(
            "【最近对话】\n"
            + "\n".join(
                f"{'玩家' if m.get('role') == 'user' else (m.get('name') or '旁白')}："
                f"{str(m.get('content') or '')[:300]}"
                for m in recent
            )
        )

    blocks.append(
        "【玩家这一轮的言行】\n"
        + (user_input.strip() or "（玩家未输入，视为沉默/等待）")
    )
    blocks.append("现在输出你的裁决 JSON（单个对象，无代码围栏）：")

    return [
        ChatMessage(role="system", content="\n\n".join(blocks)),
        ChatMessage(role="user", content="请裁决这一轮的世界反应。"),
    ]


# --------------------------------------------------------------------------- #
# 服务
# --------------------------------------------------------------------------- #
class DirectorSvc:
    """AI 导演：把「玩家行动 + 世界状态」变成一份可执行的演出裁决。"""

    def __init__(self, db: Any | None = None, router: LLMRouter | None = None) -> None:
        self._router = router or LLMRouter(db)

    async def decide(
        self,
        *,
        card: dict[str, Any],
        preset: dict[str, Any],
        story: dict[str, Any],
        cast: list[dict[str, Any]],
        relations: list[dict[str, Any]],
        scene: dict[str, Any],
        history: list[dict[str, Any]],
        user_input: str,
        outline: dict[str, Any] | None = None,
        fallback_speaker: dict[str, Any] | None = None,
        circuit_open: bool = False,
        overrides: dict[str, Any] | None = None,
    ) -> DirectorDecision:
        """产出本轮裁决。**永不抛异常** —— 任何失败都降级为 `fallback()`。"""
        if circuit_open:
            logger.info("director circuit open, skip LLM")
            return DirectorDecision.fallback(reason="导演连续失败已达熔断阈值，本轮降级为单角色接话。", speaker=fallback_speaker)

        messages = build_decision_prompt(
            card=card,
            preset=preset,
            story=story,
            cast=cast,
            relations=relations,
            scene=scene,
            history=history,
            user_input=user_input,
            outline=outline,
        )

        # ---- L1：带 response_format ----
        raw = await self._try_complete(messages, overrides=overrides, use_json_format=True)
        parsed = _extract_json(raw) if raw is not None else None

        # ---- L2：去掉 response_format 重试（覆盖两种失败动机）----
        #   1. 端点不支持该参数 → L1 直接抛错（raw is None）；
        #   2. 端点接受了参数但输出非 JSON 正文 → 换个措辞再要一次。
        if parsed is None:
            if raw is not None:
                logger.warning("director L1 output unparsable, retrying without format: %r", raw[:200])
            raw = await self._try_complete(messages, overrides=overrides, use_json_format=False)
            parsed = _extract_json(raw) if raw is not None else None

        if raw is None:
            return DirectorDecision.fallback(
                reason="导演调用失败（已重试），本轮降级为单角色接话。", speaker=fallback_speaker
            )
        if parsed is None:
            # 区分「被截断」与「模型乱写」：前者要调 max_tokens，后者要改提示词。
            # 二者的排查方向完全不同，早期版本只打一句 "unparsable" 分不出来，
            # 导致「导演长期静默降级」被误判成「剧情设计得不好」（见 max_tokens 注释）。
            if len(raw) >= _DIRECTOR_TRUNCATION_HINT:
                logger.warning(
                    "director output likely TRUNCATED (len=%d, max_tokens=%s) —— "
                    "裁决 JSON 未写完。考虑提高 _DIRECTOR_PARAMS['max_tokens'] "
                    "或精简角色的 voice/goals。head=%r",
                    len(raw),
                    _DIRECTOR_PARAMS.get("max_tokens"),
                    raw[:200],
                )
            else:
                logger.warning(
                    "director output unparsable and NOT truncated (len=%d) —— "
                    "疑似模型未按 JSON 输出。head=%r",
                    len(raw),
                    raw[:200],
                )
            return DirectorDecision.fallback(
                reason="导演输出无法解析为 JSON，本轮降级为单角色接话。", speaker=fallback_speaker
            )

        decision = DirectorDecision.from_json(parsed)
        logger.info(
            "director decided",
            extra={"speakers": [s["id"] for s in decision.speakers], "node": (decision.node_triggered or {}).get("id")},
        )
        return decision

    async def _try_complete(
        self,
        messages: list[ChatMessage],
        *,
        overrides: dict[str, Any] | None,
        use_json_format: bool,
    ) -> str | None:
        """单次非流式调用；失败返回 None（由调用方决定是否重试/降级）。"""
        params = dict(_DIRECTOR_PARAMS)
        if use_json_format:
            params["response_format"] = _JSON_FORMAT
        try:
            return await self._router.complete(messages, params=params, overrides=overrides)
        except Exception as exc:  # noqa: BLE001 —— 导演失败绝不上抛
            logger.warning(
                "director complete failed (json_format=%s): %s",
                use_json_format,
                type(exc).__name__,
            )
            return None


__all__ = ["MAX_SPEAKERS", "DirectorDecision", "DirectorSvc", "build_decision_prompt"]
