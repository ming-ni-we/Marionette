"""序幕生成服务（剧情引擎 §7）。

**要解决的问题**：玩家进入一个陌生世界时，需要先知道「这是哪儿、我是谁、要干什么」。
本服务在剧情会话创建时产出**序幕消息草稿**：世界观介绍 + 剧情开场 + 玩家处境。

设计契约：
  - **不写库**：只产出草稿（`[{role, content, meta}]`），由 `SessionSvc.create_story_session`
    落库。原因是 `seq` 必须单调递增且由 SessionSvc 单点维护，绕过它会破坏流式恢复基石。
  - **永不失败**：LLM 不可用时逐级降级 ——
      L1 LLM 生成（多段序幕）
      L2 `world.opening` + 角色卡 `first_mes` 拼接（纯文本，无 LLM）
      L3 纯模板（连 opening 为空也能给出可用文案）
  - **meta 标记完整**：每段都带 `beat_role="opening"` 与 `is_narration`，
    前端据此渲染 `OpeningCard`，且刷新/导出后仍能识别。
"""

from __future__ import annotations

from typing import Any

from app.adapters.base import ChatMessage
from app.core.logging import get_logger
from app.services.llm_router import LLMRouter

logger = get_logger(__name__)

#: 序幕各段的 `beat_role`，前端与导出格式都依赖这个字面量
BEAT_ROLE_OPENING = "opening"

#: 采样参数：序幕要稳住世界观口吻，不需要飞
_OPENING_PARAMS: dict[str, Any] = {"temperature": 0.7, "max_tokens": 700}

_OPENING_SYSTEM = """你是一位擅长开场的小说家，负责为一段文字冒险写下**序幕**。

序幕要让玩家在三十秒内明白三件事：
  1. 这是个什么样的世界（时代、地点、氛围、规则）；
  2. 眼下正在发生什么（把玩家拉进具体的场景与冲突里）；
  3. 玩家扮演的角色是谁、身处什么位置、面临什么选择。

写作要求：
- 用第二人称「你」称呼玩家，让玩家立刻代入。
- 分 2 段输出，段与段之间用空行分隔：
    第一段【世界观】——克制地交代背景与氛围，不要信息倾泻；
    第二段【开场】——落在一个具体的时间点与地点，最后留一个悬而未决的钩子。
- 全部输出**纯文本**，不要 JSON、不要 markdown 标题、不要 markdown 围栏、不要列表符号。
- 不要替玩家做决定，不要写玩家的台词。
- 总长度控制在 300 字以内。"""


# --------------------------------------------------------------------------- #
# 提示词（纯函数）
# --------------------------------------------------------------------------- #
def _render_world(world: dict[str, Any]) -> str:
    """把世界观渲染成导演/作家可读的摘要。"""
    setting = world.get("setting") or {}
    lines: list[str] = []
    summary = str(setting.get("summary") or "").strip()
    if summary:
        lines.append(f"总览：{summary}")
    for label, key in (("时代", "era"), ("氛围", "tone")):
        text = str(setting.get(key) or "").strip()
        if text:
            lines.append(f"{label}：{text}")
    for label, key in (("核心地点", "locations"), ("世界规则", "rules")):
        values = setting.get(key) or []
        if isinstance(values, list) and values:
            lines.append(f"{label}：" + "、".join(str(v) for v in values[:6]))

    factions = world.get("factions") or []
    if isinstance(factions, list) and factions:
        rendered = [
            f"{f.get('name')}（{f.get('stance') or '立场未知'}）"
            for f in factions[:6]
            if isinstance(f, dict) and f.get("name")
        ]
        if rendered:
            lines.append("势力：" + "、".join(rendered))

    outline = world.get("outline") or {}
    if isinstance(outline, dict):
        goal = str(outline.get("main_goal") or "").strip()
        if goal:
            lines.append(f"主线：{goal}")
        nodes = outline.get("nodes") or []
        if isinstance(nodes, list) and nodes:
            titles = [
                str(n.get("title") or "")
                for n in nodes[:5]
                if isinstance(n, dict) and n.get("title")
            ]
            if titles:
                lines.append("关键节点：" + " → ".join(titles))

    opening = str(world.get("opening") or "").strip()
    if opening:
        lines.append(f"作者给定的开场文字（请沿用其语气与事实）：\n{opening[:600]}")

    return "\n".join(lines) if lines else "（世界观信息为空）"


def _render_cast(cast: list[dict[str, Any]]) -> str:
    if not cast:
        return "（暂无角色群信息）"
    lines: list[str] = []
    for member in cast[:10]:
        if not isinstance(member, dict):
            continue
        name = str(member.get("name") or member.get("id") or "").strip()
        if not name:
            continue
        bits = [name]
        if member.get("role"):
            bits.append(f"（{member['role']}）")
        if member.get("description"):
            bits.append(f"：{str(member['description'])[:80]}")
        lines.append("- " + "".join(bits))
    return "\n".join(lines) if lines else "（暂无角色群信息）"


def build_opening_prompt(
    *,
    world: dict[str, Any],
    card: dict[str, Any],
    preset: dict[str, Any],
    user_persona: dict[str, Any] | None = None,
    cast: list[dict[str, Any]] | None = None,
) -> list[ChatMessage]:
    """构造序幕生成的 messages（纯函数，可单测）。"""
    blocks: list[str] = [_OPENING_SYSTEM]
    blocks.append("【世界观设定】\n" + _render_world(world))

    cast_text = _render_cast(cast or [])
    if cast_text != "（暂无角色群信息）":
        blocks.append("【这个世界的角色】\n" + cast_text)

    card_name = str(card.get("name") or "").strip()
    if card_name:
        card_bits = [f"玩家将与「{card_name}」这个人相遇。"]
        for label, key in (("身份设定", "description"), ("性格", "personality")):
            text = str(card.get(key) or "").strip()
            if text:
                card_bits.append(f"{label}：{text[:200]}")
        blocks.append("【玩家将遇到的人】\n" + "\n".join(card_bits))

    persona = user_persona or {}
    if persona.get("name") or persona.get("description"):
        blocks.append(
            "【玩家扮演的角色】\n"
            + "\n".join(
                p
                for p in (
                    f"名字：{persona.get('name')}" if persona.get("name") else "",
                    f"设定：{str(persona.get('description') or '')[:200]}"
                    if persona.get("description")
                    else "",
                )
                if p
            )
        )

    tone = str((preset.get("prompt_template") or {}).get("system") or "").strip()
    if tone:
        blocks.append("【整体演出基调（节选自预设）】\n" + tone[:400])

    blocks.append("现在写下这段冒险的序幕（两段纯文本，不要任何标记）：")
    return [
        ChatMessage(role="system", content="\n\n".join(blocks)),
        ChatMessage(role="user", content="请写下序幕。"),
    ]


# --------------------------------------------------------------------------- #
# 降级文案
# --------------------------------------------------------------------------- #
def fallback_from_card(
    card: dict[str, Any], world: dict[str, Any], *, user_persona: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """L2 降级：`world.opening` + 角色卡 `first_mes` 拼接，无 LLM。

    这两段本来就是「作者手写的内容」，直接呈现给玩家完全可用 —— 唯一损失是
    没有 AI 为这场会话定制措辞。
    """
    drafts: list[dict[str, Any]] = []
    world_text = str(world.get("opening") or "").strip()
    if not world_text:
        world_text = _compose_world_blurb(world)

    if world_text:
        drafts.append(
            {
                "role": "assistant",
                "content": world_text,
                "meta": _opening_meta(index=0, is_narration=True),
            }
        )

    greeting = str(card.get("first_mes") or "").strip()
    if greeting:
        drafts.append(
            {
                "role": "assistant",
                "content": greeting,
                "meta": _opening_meta(
                    index=len(drafts), is_narration=False, speaker_name=str(card.get("name") or "")
                ),
            }
        )

    if not drafts:
        drafts = fallback_template(world, user_persona=user_persona)
    return drafts


def fallback_template(
    world: dict[str, Any], *, user_persona: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """L3 兜底：连 `world.opening` 都为空时，也要给出可读的序幕。"""
    title = str(world.get("title") or "").strip() or "这个世界"
    blurb = _compose_world_blurb(world)
    content = blurb or f"你来到了「{title}」。\n\n四下无人，故事从这里开始 —— 你想先做什么？"
    return [
        {
            "role": "assistant",
            "content": content,
            "meta": _opening_meta(index=0, is_narration=True),
        }
    ]


def _compose_world_blurb(world: dict[str, Any]) -> str:
    """从结构化设定拼一段最低限度的世界观介绍（不依赖任何 LLM）。"""
    setting = world.get("setting") or {}
    title = str(world.get("title") or "").strip()
    parts: list[str] = []
    if title:
        parts.append(f"— {title} —")
    summary = str(setting.get("summary") or "").strip()
    if summary:
        parts.append(summary)
    for label, key in (("时代", "era"), ("氛围", "tone")):
        text = str(setting.get(key) or "").strip()
        if text:
            parts.append(f"{label}：{text}")
    locations = setting.get("locations") or []
    if isinstance(locations, list) and locations:
        parts.append("你可能会去：" + "、".join(str(x) for x in locations[:5]))
    rules = setting.get("rules") or []
    if isinstance(rules, list) and rules:
        parts.append("这里的规矩：" + "；".join(str(x) for x in rules[:4]))
    outline = world.get("outline") or {}
    if isinstance(outline, dict) and outline.get("main_goal"):
        parts.append(f"你要面对的事：{outline['main_goal']}")
    return "\n".join(parts)


def _opening_meta(*, index: int, is_narration: bool, speaker_name: str = "") -> dict[str, Any]:
    return {
        "beat_role": BEAT_ROLE_OPENING,
        "is_narration": bool(is_narration),
        "is_director_note": False,
        "opening_index": index,
        "turn": 0,
        "speaker_id": None,
        "speaker_name": speaker_name or None,
    }


def _split_paragraphs(text: str) -> list[str]:
    """按空行拆段；段落过少时退化为整块，保持作者原本的排版意图。"""
    raw = (text or "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in raw.split("\n\n")]
    return [p for p in parts if p]


# --------------------------------------------------------------------------- #
# 服务
# --------------------------------------------------------------------------- #
class OpeningSvc:
    """序幕生成。**绝不抛异常** —— 任何失败都降级为可用文案。"""

    def __init__(self, db: Any | None = None, router: LLMRouter | None = None) -> None:
        self._router = router or LLMRouter(db)

    async def generate(
        self,
        *,
        world: dict[str, Any],
        card: dict[str, Any],
        preset: dict[str, Any],
        cast: list[dict[str, Any]] | None = None,
        user_persona: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """返回序幕消息草稿（**不落库**）。

        草稿结构 `{role, content, meta}`，由 `SessionSvc.create_story_session` 依序落库，
        保证 `seq` 单调递增。
        """
        messages = build_opening_prompt(
            world=world, card=card, preset=preset, user_persona=user_persona, cast=cast
        )
        text = await self._try(messages, overrides=overrides)
        paragraphs = _split_paragraphs(text) if text else []
        if not paragraphs:
            logger.info("opening degraded to card/world fallback")
            return fallback_from_card(card, world, user_persona=user_persona)

        return [
            {
                "role": "assistant",
                "content": paragraph,
                "meta": _opening_meta(index=i, is_narration=True),
            }
            for i, paragraph in enumerate(paragraphs)
        ]

    async def _try(
        self, messages: list[ChatMessage], *, overrides: dict[str, Any] | None
    ) -> str | None:
        try:
            return await self._router.complete(
                messages, params=dict(_OPENING_PARAMS), overrides=overrides
            )
        except Exception as exc:  # noqa: BLE001 —— 序幕失败绝不上抛
            logger.warning("opening complete failed: %s", type(exc).__name__)
            return None


__all__ = [
    "BEAT_ROLE_OPENING",
    "OpeningSvc",
    "build_opening_prompt",
    "fallback_from_card",
    "fallback_template",
]
