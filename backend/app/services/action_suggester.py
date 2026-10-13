"""行动建议服务（剧情引擎 §8）。

**要解决的问题**：玩家进入剧情后常常「不知道能做什么」，不知道这个世界接受什么样的输入。
本服务在每轮结束时给出 3 条可点击的行动建议，**填入输入框但不自动发送** —— 保留玩家主动权。

设计取舍：
  - **低 token**：`max_tokens≈200`，只喂「当前场景 + 最近对话 + 在场角色」，不喂全量历史。
  - **非流式**：建议必须完整才能展示，流式无意义。
  - **不落库**：建议是「一次性的提示」，刷新后重新生成更合理，也避免污染消息表。
  - **不上主上下文**：建议本身**绝不**回灌进演出 prompt，否则模型会看见「别人替它想好的台词」。
  - **失败即静默**：返回 `[]`，前端自动隐藏建议区，对话主流程完全不受影响。
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.adapters.base import ChatMessage
from app.core.logging import get_logger
from app.services.llm_router import LLMRouter

logger = get_logger(__name__)

# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #
#: tone 四分类：观察 / 说话 / 行动 / 转移
TONES: frozenset[str] = frozenset({"observe", "speak", "act", "move"})

#: 默认建议条数（3 条是「有得选」与「不选择困难」的平衡点）
DEFAULT_COUNT = 3

#: 建议数上限，防止模型返回一屏
MAX_COUNT = 4

#: 采样参数：要具体、要不重复，但不需要长。
#:
#: `max_tokens` 曾为 200 —— 与导演的同款问题（见 `director._DIRECTOR_PARAMS` 注释）：
#: 3 条建议的 JSON（label + hint + tone × 3，中文）很容易写超 200 被截断，
#: `_extract_actions_json` 拿不到闭合括号 → 判为不可解析 → L2 重试同样截断
#: → 最终 `degraded`，且当 `use_fallback=False` 时**直接返回空列表**，
#: 前端表现为「行动建议区整个消失」，玩家与开发者都看不到任何报错。
#:
#: 实测线上（2026-10-13）《木叶·雾中之刃》连续 4 轮 actions 全空。
#: 提高后建议稳定产出。
_SUGGEST_PARAMS: dict[str, Any] = {"temperature": 0.8, "max_tokens": 400}

#: response_format（端点不支持时降级重试）
_JSON_FORMAT: dict[str, Any] = {"type": "json_object"}

_SUGGEST_SYSTEM = """你是一台文字冒险游戏的「行动提示器」，负责为玩家提供下一步的行动参考。

你的任务：根据当前场景与最近的对话，给出若干条**具体、可执行、彼此不同**的行动选项。

铁律：
- 每条建议是**玩家（第一人称）能直接说的话或做的动作**，不要写角色的反应。
- 建议必须**紧扣当前场景**（地点、气氛、刚刚发生的事），不要泛泛而谈。
- 四条建议的方向要有区分度，避免「换个说法问同一件事」。
- tone 只能是 observe / speak / act / move 之一：
    observe = 观察、打量、回忆、试探
    speak   = 对话、质问、坦白、套话
    act     = 出手、动手、递东西、威胁、保护
    move    = 移动、离开、跟随、躲藏
- 每条建议控制在 24 个字以内，用玩家自己的口吻。
- 严格输出**单个 JSON 对象**，不要 markdown 围栏，不要解释。

输出格式（严格遵循）：
{"actions": [
  {"label": "把账册推到他面前", "hint": "看他会不会露馅", "tone": "act"},
  {"label": "问他三十七笔银子去哪了", "hint": "直接施压", "tone": "speak"}
]}"""

_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)
#: 单条建议字数上限（超长截断，避免撑破 UI 芯片）
_LABEL_MAX = 40
_HINT_MAX = 60


# --------------------------------------------------------------------------- #
# JSON 解析（与 director 同策略，容错优先）
# --------------------------------------------------------------------------- #
def _extract_actions_json(text: str) -> Any | None:
    """从 LLM 文本里抠出建议 JSON。接受 `{"actions":[...]}` 与**裸数组**两种形态。

    切片兜底时**必须优选数组分支**：散文夹 `[{...}]` 的场合，`{`/`}` 边界会先命中
    内层对象，得到一个不含 `actions` 的普通 dict（等于解析失败）。
    因此这里显式按「数组优先、且结果必须真的含建议」来裁决。
    """
    if not text:
        return None
    text = text.strip()
    for candidate in (text, *_FENCE_RE.findall(text)):
        parsed = _try_load(candidate)
        if _has_actions(parsed):
            return parsed

    # 切片兜底：数组优先（inner object 会掩盖列表结构），再退回对象
    for opener, closer in (("[", "]"), ("{", "}")):
        start, end = text.find(opener), text.rfind(closer)
        if 0 <= start < end:
            parsed = _try_load(text[start : end + 1])
            if _has_actions(parsed):
                return parsed
    return None


def _has_actions(parsed: Any) -> bool:
    """判断解析结果是否**真的**含有建议条目（空 dict / 无关对象不算）。"""
    if isinstance(parsed, list):
        return True
    if isinstance(parsed, dict):
        return "actions" in parsed
    return False


def _try_load(candidate: str) -> Any | None:
    """解析 JSON；对象与数组都算合法（建议列表允许裸数组）。"""
    try:
        parsed = json.loads(candidate.strip())
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, (dict, list)) else None


# --------------------------------------------------------------------------- #
# 清洗
# --------------------------------------------------------------------------- #
def _clean_suggestions(raw: Any, *, count: int) -> list[dict[str, Any]]:
    """把模型输出洗成稳定的建议列表。

    宽容策略：接受 `{"actions":[...]}` 与裸数组两种形态；label 缺失即丢弃该条
    （没有 label 的芯片点不了）；tone 非法一律归为 observe。
    """
    if isinstance(raw, dict):
        items = raw.get("actions")
    elif isinstance(raw, list):
        items = raw
    else:
        items = None
    if not isinstance(items, list):
        return []

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("text") or "").strip()
        if not label:
            continue
        label = label[:_LABEL_MAX]
        if label in seen:  # 去重：模型常给同义重复项
            continue
        seen.add(label)
        tone = str(item.get("tone") or "").strip().lower()
        if tone not in TONES:
            tone = "observe"
        out.append(
            {
                "id": f"a{index}",
                "label": label,
                "hint": str(item.get("hint") or "").strip()[:_HINT_MAX],
                "tone": tone,
            }
        )
        if len(out) >= count:
            break
    return out


# --------------------------------------------------------------------------- #
# 提示词（纯函数）
# --------------------------------------------------------------------------- #
def build_suggest_prompt(
    *,
    scene: dict[str, Any],
    story: dict[str, Any],
    cast: list[dict[str, Any]],
    recent_messages: list[dict[str, Any]],
    count: int = DEFAULT_COUNT,
) -> list[ChatMessage]:
    """构造行动建议的 messages（纯函数，可单测）。

    刻意只喂**少量**上下文：建议的质量取决于「最近发生了什么」，
    全量历史只会推高成本并稀释当前场景。
    """
    present = [str(x) for x in (scene.get("present") or []) if str(x or "")]
    cast_by_id = {str(c.get("id") or ""): c for c in cast if c.get("id")}
    present_lines: list[str] = []
    for cid in present:
        member = cast_by_id.get(cid)
        if member is None:
            present_lines.append(f"- {cid}")
        else:
            name = member.get("name") or cid
            voice = str(member.get("voice") or "").strip()
            present_lines.append(f"- {name}（{cid}）" + (f"：{voice}" if voice else ""))

    blocks: list[str] = [_SUGGEST_SYSTEM]
    blocks.append(
        "【当前场景】\n"
        f"地点：{scene.get('location') or '未指定'}\n"
        f"时间：{scene.get('time') or '未指定'}\n"
        f"氛围：{scene.get('mood') or '未指定'}\n"
        f"本拍：{scene.get('beat') or scene.get('summary') or '未指定'}"
    )
    if present_lines:
        blocks.append("【在场角色】\n" + "\n".join(present_lines))

    flags = story.get("flags") or {}
    if flags:
        blocks.append(
            "【已知事实】\n" + "\n".join(f"- {k} = {v}" for k, v in list(flags.items())[:8])
        )

    recent = recent_messages[-6:]
    if recent:
        blocks.append(
            "【最近发生】\n"
            + "\n".join(
                f"{'玩家' if m.get('role') == 'user' else (m.get('name') or '旁白')}："
                f"{str(m.get('content') or '')[:200]}"
                for m in recent
            )
        )

    blocks.append(
        f"现在给出 {count} 条行动建议（面向玩家、彼此不同、贴合当前场景）。"
        '输出 JSON：{"actions": [{"label": "...", "hint": "...", "tone": "observe|speak|act|move"}]}'
    )

    return [
        ChatMessage(role="system", content="\n\n".join(blocks)),
        ChatMessage(role="user", content="请给出行动建议。"),
    ]


# --------------------------------------------------------------------------- #
# 规则兜底
# --------------------------------------------------------------------------- #
def fallback_suggestions(scene: dict[str, Any], *, count: int = DEFAULT_COUNT) -> list[dict[str, Any]]:
    """LLM 不可用时的规则兜底：给出「观察 / 搭话 / 移动」这类永远可用的选项。

    不做场景理解，只保证玩家**不会面对空的输入框**。
    """
    location = str(scene.get("location") or "四周").strip() or "四周"
    templates: list[tuple[str, str, str]] = [
        (f"仔细观察{location}", "留意有没有被忽略的细节", "observe"),
        ("开口问一句，试探对方的反应", "用问题推动对话", "speak"),
        ("说出你此刻真正的想法", "把态度摆在明面上", "speak"),
        (f"离开{location}", "换个地方，让事情自己发酵", "move"),
    ]
    out: list[dict[str, Any]] = []
    for index, (label, hint, tone) in enumerate(templates[:count]):
        out.append({"id": f"f{index}", "label": label, "hint": hint, "tone": tone})
    return out


# --------------------------------------------------------------------------- #
# 服务
# --------------------------------------------------------------------------- #
class ActionSuggesterSvc:
    """每轮结束时的行动建议生成器。**绝不抛异常**，失败返回 `[]`。"""

    def __init__(self, db: Any | None = None, router: LLMRouter | None = None) -> None:
        self._router = router or LLMRouter(db)

    async def suggest(
        self,
        *,
        scene: dict[str, Any],
        story: dict[str, Any],
        cast: list[dict[str, Any]],
        recent_messages: list[dict[str, Any]],
        count: int = DEFAULT_COUNT,
        overrides: dict[str, Any] | None = None,
        use_fallback: bool = True,
    ) -> list[dict[str, Any]]:
        """返回 `[{id,label,hint,tone}]`；任何失败都返回兜底或空列表。

        `use_fallback=False` 时失败直接返回 `[]` —— 供「建议是否降级」的测试与
        希望静默失败的调用方使用。
        """
        count = max(1, min(MAX_COUNT, int(count) if count is not None else DEFAULT_COUNT))
        messages = build_suggest_prompt(
            scene=scene, story=story, cast=cast, recent_messages=recent_messages, count=count
        )

        raw = await self._try(messages, overrides=overrides, use_json_format=True)
        parsed = _extract_actions_json(raw) if raw else None
        if parsed is None:
            raw = await self._try(messages, overrides=overrides, use_json_format=False)
            parsed = _extract_actions_json(raw) if raw else None

        actions = _clean_suggestions(parsed, count=count) if parsed is not None else []
        if actions:
            return actions

        logger.info("action suggester degraded")
        if not use_fallback:
            return []
        return fallback_suggestions(scene, count=count)

    async def _try(
        self,
        messages: list[ChatMessage],
        *,
        overrides: dict[str, Any] | None,
        use_json_format: bool,
    ) -> str | None:
        params = dict(_SUGGEST_PARAMS)
        if use_json_format:
            params["response_format"] = _JSON_FORMAT
        try:
            return await self._router.complete(messages, params=params, overrides=overrides)
        except Exception as exc:  # noqa: BLE001 —— 建议失败绝不上抛
            logger.warning(
                "action suggester complete failed (json_format=%s): %s",
                use_json_format,
                type(exc).__name__,
            )
            return None


__all__ = [
    "DEFAULT_COUNT",
    "MAX_COUNT",
    "TONES",
    "ActionSuggesterSvc",
    "build_suggest_prompt",
    "fallback_suggestions",
]
