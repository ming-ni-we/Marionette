"""出图触发时机服务（S16 对话配图 §4.6.3）。

**要解决的问题**：剧情对话里「不时插入图片」，但**不能每轮出图** ——
一局 20 轮 × ¥0.30 = ¥6.0，且多数图没有信息量，还会打断阅读节奏。

**设计取舍**（详见 `docs/asset/09-project-plan.md` §4.6.3）：

  - **只在「值得画」的时刻出图**：节点触发（剧情转折）+ 新角色登场（视觉锚点）。
  - **两道去重**：同一 `node_id` 只画一次；同一 `character_id` 只画一次。
    否则角色每次说话都触发，配额瞬间烧光。
  - **三重节流**：总配额（默认 8 张/局）、最小间隔（默认 2 轮）、单轮上限 1 张。
  - **默认关闭**：`story_image_enabled` 默认 `false`。出图是**花钱**的功能，
    绝不能让「用户没开过但每轮都在扣费」发生。
  - **提示词调一次 LLM 扩写**，失败退回模板拼接 —— 只降质量，不降可用性。
  - **绝不抛异常**：任何失败都返回「不出图」，对话主流程完全不受影响。

分层铁律（SPEC §4.2）：本服务只依赖 `LLMRouter` 与纯数据，
**绝不 import 任何出图 SDK**（沿用 `image_hook.py` 的架构约束）。
出图本身由 `ImageHook` 负责，本服务只回答「**要不要画**」和「**画什么**」。
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
#: 触发原因（同时用作 SSE 事件的 reason 字段与日志）
REASON_NODE = "node"  # 剧情节点触发（最强信号）
REASON_CAST = "cast"  # 新角色首次登场
REASON_MANUAL = "manual"  # 玩家/前端显式请求

#: 每局出图总配额（硬性成本上限：8 × ¥0.30 = ¥2.4）
DEFAULT_QUOTA = 8

#: 两次出图之间的最小轮次间隔（防「刚画完又画」的重复感）
DEFAULT_MIN_GAP = 2

#: 画面比例 → 实际像素（模型接受 WxH）
ASPECT_SIZES: dict[str, tuple[int, int]] = {
    "landscape": (1280, 720),
    "portrait": (720, 1280),
    "square": (1024, 1024),
}
DEFAULT_ASPECT = "landscape"

#: 扩写采样参数：要具体画面，不需要长（120 字描述足够）
_PROMPT_PARAMS: dict[str, Any] = {"temperature": 0.7, "max_tokens": 400}

#: response_format（端点不支持时降级重试）
_JSON_FORMAT: dict[str, Any] = {"type": "json_object"}

#: 固定画风后缀 —— 保证同一局内视觉一致，这是「不出现角色名」之外的兜底手段
STYLE_SUFFIX = "写实电影感，冷色调，胶片颗粒，柔和自然光"

_PROMPT_SYSTEM = """你是一台文字冒险游戏的「场景画师」，负责把当前剧情转译成一句**中文画面描述**。

你的任务：只描述**此刻这个镜头里能看到什么**，供文生图模型作画。

铁律：
- **描述画面，不描述情节**。写「雨夜的青石板巷，灯笼在风里晃，屋檐滴水」，
  不要写「他走进巷子里」（那是情节，画不出来）。
- **绝不出现角色姓名**。模型不认识这些名字。改用**外观特征**：
  写「穿深灰长衫的年轻男子，眉骨有旧疤」，不要写「沈砚」。
- 只写**一个镜头**。不要写「然后」「接着」「随后」这类时间推进。
- 用**具体名词 + 具体光线**（「斑驳的木窗」「黄昏的侧逆光」），少用抽象形容词。
- 不出现任何**文字/招牌/书页内容**（模型会把字画成乱码）。
- 描述控制在 60-120 个汉字。风格词已由系统追加，**不要再写画风**。

输出格式（严格遵循，单个 JSON 对象，不要 markdown 围栏）：
{"prompt": "中文画面描述", "negative_prompt": "不要出现的元素", "aspect": "landscape|portrait|square"}

aspect 选择：landscape=场景全景（推荐，多数情况）；portrait=单人特写；square=居中构图。"""

_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)

#: 描述长度上限（防模型写小作文）
_PROMPT_MAX = 400
_NEGATIVE_MAX = 200


# --------------------------------------------------------------------------- #
# 触发判定（纯函数 —— 可单测，无 IO）
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TriggerDecision:
    """一次触发判定的结果。`should` 为 False 时 `reason` 说明为何不出图。"""

    should: bool
    reason: str = ""
    seed: dict[str, Any] = field(default_factory=dict)
    """交给提示词构造器的素材：节点标题 / 新角色信息等。"""


#: 不出的原因 → 中文说明（便于日志排查与测试断言）
SKIP_DISABLED = "disabled"  # 功能开关关闭
SKIP_QUOTA = "quota"  # 配额耗尽
SKIP_GAP = "gap"  # 距上次出图太近
SKIP_DUP_NODE = "dup_node"  # 该节点已画过
SKIP_DUP_CAST = "dup_cast"  # 该角色已画过
SKIP_NO_SIGNAL = "no_signal"  # 本轮没有触发信号


def _as_int(value: Any, *, default: int | None) -> int | None:
    """宽容取整：脏数据（None / 字符串 / 浮点）一律回退 `default`，绝不抛异常。

    触发判定读的是 `state_machine.story`（JSONB，历史数据可能有任何形态），
    所以这里的容错是**必须的** —— 一个脏字段不能让整轮对话挂掉。
    """
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def decide_image(
    *,
    enabled: bool,
    turn: int,
    story: dict[str, Any],
    node_triggered: dict[str, Any] | None = None,
    cast: list[dict[str, Any]] | None = None,
    speakers: list[dict[str, Any]] | None = None,
    quota: int = DEFAULT_QUOTA,
    min_gap: int = DEFAULT_MIN_GAP,
) -> TriggerDecision:
    """判定本轮是否该出图。**纯函数**：不查库、不调 LLM、不写状态。

    判定顺序（**先节流后信号** —— 便宜的先判，避免无谓计算）：

      1. 开关关闭            → SKIP_DISABLED
      2. 配额已满            → SKIP_QUOTA
      3. 距上次出图 < min_gap → SKIP_GAP
      4. 节点触发且该节点未画过 → 出图（REASON_NODE）
      5. 有角色首次登场且未画过 → 出图（REASON_CAST）
      6. 都不满足            → SKIP_NO_SIGNAL
    """
    if not enabled:
        return TriggerDecision(False, SKIP_DISABLED)

    story = story or {}
    used = _as_int(story.get("image_count"), default=0)
    if used >= max(0, _as_int(quota, default=DEFAULT_QUOTA)):
        return TriggerDecision(False, SKIP_QUOTA)

    last_turn = story.get("last_image_turn")
    if last_turn is not None:
        prev = _as_int(last_turn, default=None)
        if prev is not None and _as_int(turn, default=0) - prev < max(0, _as_int(min_gap, default=DEFAULT_MIN_GAP)):
            return TriggerDecision(False, SKIP_GAP)

    # ---- 信号 1：剧情节点触发（最强）----
    node = _as_node(node_triggered)
    node_id = str(node.get("id") or "").strip()
    if node_id:
        drawn = _as_str_set(story.get("image_nodes"))
        if node_id not in drawn:
            return TriggerDecision(
                True,
                REASON_NODE,
                {
                    "node_id": node_id,
                    "node_title": str(node.get("title") or ""),
                    "node_brief": str(node.get("brief") or ""),
                },
            )
        # 该节点画过 → 继续看有没有「新角色登场」这种次强信号

    # ---- 信号 2：新角色首次登场 ----
    drawn_cast = _as_str_set(story.get("image_cast"))
    fresh = _first_unpainted_character(cast=cast, speakers=speakers, drawn=drawn_cast)
    if fresh is not None:
        return TriggerDecision(
            True,
            REASON_CAST,
            {"character_id": fresh.get("id"), "character": fresh},
        )

    # 命中过「重复节点」时给出更精确的原因，便于排查
    if node_id:
        return TriggerDecision(False, SKIP_DUP_NODE)
    return TriggerDecision(False, SKIP_NO_SIGNAL)


def _as_str_set(value: Any) -> set[str]:
    """把 story 里的去重集合字段洗成 `set[str]`（容忍脏数据）。"""
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {str(v) for v in value if v not in (None, "")}


def _as_node(value: Any) -> dict[str, Any]:
    """把 `node_triggered` 洗成 dict（容忍脏数据）。

    导演契约里它是 `{"id","title","brief"} | None`，但这条路径最终由 LLM 的 JSON
    驱动 —— 模型偶尔会直接吐一个字符串 id 而不是对象。**这里绝不能抛异常**：
    `decide_image` 在对话主流里同步调用，崩了就是整轮回复失败。

    宽容策略：dict 原样返回；非空字符串当作 `{"id": ...}`；其余（数字/列表/None）
    一律视为「无节点信号」。
    """
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        return {"id": text} if text else {}
    return {}


def _first_unpainted_character(
    *,
    cast: list[dict[str, Any]] | None,
    speakers: list[dict[str, Any]] | None,
    drawn: set[str],
) -> dict[str, Any] | None:
    """本轮在场角色里，找一个「还没画过」的。

    优先用 `speakers`（本轮真正出场的），空则退回 `cast`（全部角色）。
    这样「新角色第一次开口」就能立刻拿到视觉锚点。
    """
    for pool in (speakers, cast):
        for member in pool or []:
            if not isinstance(member, dict):
                continue
            cid = str(member.get("id") or "").strip()
            if cid and cid not in drawn:
                return member
    return None


# --------------------------------------------------------------------------- #
# 提示词构造（纯函数 + 模板兜底）
# --------------------------------------------------------------------------- #
def build_template_prompt(
    *,
    scene: dict[str, Any],
    story: dict[str, Any],
    cast: list[dict[str, Any]] | None,
    seed: dict[str, Any] | None = None,
    extra: list[str] | None = None,
) -> tuple[str, str, str]:
    """无 LLM 时的模板拼接兜底。返回 `(prompt, negative_prompt, aspect)`。

    刻意做得**很朴素**：只是把已知的结构化字段拼起来。
    它的价值不是好看，而是「扩写失败时仍然能出一张图」。
    """
    seed = seed or {}
    parts: list[str] = []

    location = str(scene.get("location") or "").strip()
    if location:
        parts.append(location)
    mood = str(scene.get("mood") or "").strip()
    if mood:
        parts.append(f"{mood}的气氛")
    beat = str(scene.get("beat") or scene.get("summary") or "").strip()
    if beat:
        parts.append(beat)
    if extra:
        parts.extend(str(x).strip() for x in extra if str(x or "").strip())

    # 新角色登场：把外观描述拼进去（而不是名字）
    char = seed.get("character")
    if isinstance(char, dict):
        voice = str(char.get("voice") or "").strip()
        if voice:
            parts.append(voice)

    body = "，".join(p for p in parts if p) or "一个安静的室内场景"
    prompt = f"{body}，{STYLE_SUFFIX}"
    return prompt[:_PROMPT_MAX], _default_negative(), DEFAULT_ASPECT


def _default_negative() -> str:
    """默认负面提示词：排除文字与水印（实测这两类最影响观感）。"""
    return "文字, 水印, 签名, 乱码字符, 畸变, 多余手指, 低分辨率"


def _extract_prompt_json(text: str) -> Any | None:
    """从 LLM 文本里抠出画面描述 JSON（容错优先，与 director/action_suggester 同策略）。"""
    if not text:
        return None
    text = text.strip()
    for candidate in (text, *_FENCE_RE.findall(text)):
        parsed = _try_load(candidate)
        if _has_prompt(parsed):
            return parsed
    # 切片兜底：取最外层花括号
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        parsed = _try_load(text[start : end + 1])
        if _has_prompt(parsed):
            return parsed
    return None


def _has_prompt(parsed: Any) -> bool:
    """解析结果是否**真的**含可用描述（防「解析成功但内容空」）。"""
    if not isinstance(parsed, dict):
        return False
    return bool(str(parsed.get("prompt") or "").strip())


def _try_load(candidate: str) -> Any | None:
    try:
        parsed = json.loads(candidate.strip())
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, (dict, list)) else None


def _clean_prompt(parsed: Any) -> tuple[str, str, str]:
    """把模型输出洗成 `(prompt, negative_prompt, aspect)`。

    `prompt` 为空即视为不可用（返回空串，调用方会退回模板）。
    """
    if not isinstance(parsed, dict):
        return "", "", DEFAULT_ASPECT
    prompt = str(parsed.get("prompt") or "").strip()
    if not prompt:
        return "", "", DEFAULT_ASPECT
    negative = str(parsed.get("negative_prompt") or "").strip() or _default_negative()
    aspect = str(parsed.get("aspect") or "").strip().lower()
    if aspect not in ASPECT_SIZES:
        aspect = DEFAULT_ASPECT
    return prompt[:_PROMPT_MAX], negative[:_NEGATIVE_MAX], aspect


def build_image_prompt(
    *,
    scene: dict[str, Any],
    story: dict[str, Any],
    cast: list[dict[str, Any]] | None,
    said: list[dict[str, Any]] | None,
    seed: dict[str, Any] | None = None,
) -> list[ChatMessage]:
    """构造「扩写画面描述」的 messages（纯函数，可单测）。

    刻意只喂**少量**上下文（与 `action_suggester` 同思路）：
    画面描述取决于「此刻这个镜头」，全量历史只会推高成本并稀释场景。
    """
    seed = seed or {}
    present = [str(x) for x in (scene.get("present") or []) if str(x or "")]
    cast_by_id = {str(c.get("id") or ""): c for c in (cast or []) if c.get("id")}

    present_lines: list[str] = []
    for cid in present:
        member = cast_by_id.get(cid)
        if member is None:
            present_lines.append(f"- {cid}")
            continue
        name = member.get("name") or cid
        voice = str(member.get("voice") or "").strip()
        present_lines.append(f"- {name}（{cid}）" + (f"：{voice}" if voice else ""))

    blocks: list[str] = [_PROMPT_SYSTEM]
    blocks.append(
        "【当前场景】\n"
        f"地点：{scene.get('location') or '未指定'}\n"
        f"时间：{scene.get('time') or '未指定'}\n"
        f"氛围：{scene.get('mood') or '未指定'}\n"
        f"本拍：{scene.get('beat') or scene.get('summary') or '未指定'}"
    )
    if present_lines:
        blocks.append("【在场角色（用外观描述替代姓名）】\n" + "\n".join(present_lines))

    # 触发原因：让模型知道「为什么此刻值得画」
    node_title = str(seed.get("node_title") or "").strip()
    node_brief = str(seed.get("node_brief") or "").strip()
    if node_title or node_brief:
        blocks.append(
            "【触发原因：剧情节点】\n"
            + (f"{node_title}\n" if node_title else "")
            + node_brief
        )
    char = seed.get("character")
    if isinstance(char, dict):
        blocks.append(
            "【触发原因：新角色登场】\n"
            f"- {char.get('name') or char.get('id')}：{char.get('voice') or '（无外观描述）'}"
        )

    recent = (said or [])[-3:]
    if recent:
        blocks.append(
            "【本轮已发生】\n"
            + "\n".join(
                f"{s.get('name') or '旁白'}：{str(s.get('content') or '')[:160]}"
                for s in recent
                if str(s.get("content") or "").strip()
            )
        )

    blocks.append(
        "现在输出这一镜的画面描述。记住：只写看得见的东西，不写角色姓名，不写情节推进。"
    )

    return [
        ChatMessage(role="system", content="\n\n".join(blocks)),
        ChatMessage(role="user", content="请给出画面描述。"),
    ]


# --------------------------------------------------------------------------- #
# 状态回写（供 ChatSvc 在出图成功后调用）
# --------------------------------------------------------------------------- #
def next_story_state(
    *,
    story: dict[str, Any],
    turn: int,
    reason: str,
    seed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """算出出图成功后的 `story` 增量补丁（纯函数）。

    **只在出图成功后调用** —— 失败不记账，避免「画失败也占配额」。
    """
    seed = seed or {}
    patch: dict[str, Any] = {
        "image_count": int(story.get("image_count") or 0) + 1,
        "last_image_turn": int(turn),
    }
    if reason == REASON_NODE:
        node_id = str(seed.get("node_id") or "").strip()
        if node_id:
            patch["image_nodes"] = sorted(_as_str_set(story.get("image_nodes")) | {node_id})
    elif reason == REASON_CAST:
        cid = str(seed.get("character_id") or "").strip()
        if cid:
            patch["image_cast"] = sorted(_as_str_set(story.get("image_cast")) | {cid})
    return patch


# --------------------------------------------------------------------------- #
# 服务（有 IO：只调 LLM 做扩写，不碰出图）
# --------------------------------------------------------------------------- #
class ImageTriggerSvc:
    """决定「要不要画」+ 产出「画什么」。**绝不抛异常**。"""

    def __init__(self, db: Any | None = None, router: LLMRouter | None = None) -> None:
        self._router = router or LLMRouter(db)

    @staticmethod
    def decide(**kwargs: Any) -> TriggerDecision:
        """转发到纯函数（便于注入 mock 与单测）。"""
        return decide_image(**kwargs)

    async def render_prompt(
        self,
        *,
        scene: dict[str, Any],
        story: dict[str, Any],
        cast: list[dict[str, Any]] | None,
        said: list[dict[str, Any]] | None = None,
        seed: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
        use_llm: bool = True,
    ) -> tuple[str, str, str, str]:
        """产出 `(prompt, negative_prompt, aspect, source)`。

        `source` 为 `"llm"` 或 `"template"` —— 便于日志与测试断言走了哪条路。
        扩写失败**一定**退回模板，绝不让「出图」因为扩写失败而取消。
        """
        if use_llm:
            messages = build_image_prompt(
                scene=scene, story=story, cast=cast, said=said, seed=seed
            )
            raw = await self._try(messages, overrides=overrides, use_json_format=True)
            parsed = _extract_prompt_json(raw) if raw else None
            if parsed is None:
                raw = await self._try(messages, overrides=overrides, use_json_format=False)
                parsed = _extract_prompt_json(raw) if raw else None
            if parsed is not None:
                prompt, negative, aspect = _clean_prompt(parsed)
                if prompt:
                    return prompt, negative, aspect, "llm"
            logger.info("image prompt expander degraded -> template")

        prompt, negative, aspect = build_template_prompt(
            scene=scene, story=story, cast=cast, seed=seed
        )
        return prompt, negative, aspect, "template"

    async def _try(
        self,
        messages: list[ChatMessage],
        *,
        overrides: dict[str, Any] | None,
        use_json_format: bool,
    ) -> str | None:
        params = dict(_PROMPT_PARAMS)
        if use_json_format:
            params["response_format"] = _JSON_FORMAT
        try:
            return await self._router.complete(messages, params=params, overrides=overrides)
        except Exception as exc:  # noqa: BLE001 —— 扩写失败绝不上抛
            logger.warning(
                "image prompt complete failed (json_format=%s): %s",
                use_json_format,
                type(exc).__name__,
            )
            return None


def aspect_to_size(aspect: str, *, width: int | None = None, height: int | None = None) -> dict[str, int]:
    """把 aspect 折算成 `{width, height}`，显式传入的宽高优先。"""
    if width and height:
        return {"width": int(width), "height": int(height)}
    w, h = ASPECT_SIZES.get(aspect, ASPECT_SIZES[DEFAULT_ASPECT])
    return {"width": w, "height": h}


__all__ = [
    "ASPECT_SIZES",
    "DEFAULT_ASPECT",
    "DEFAULT_MIN_GAP",
    "DEFAULT_QUOTA",
    "REASON_CAST",
    "REASON_MANUAL",
    "REASON_NODE",
    "SKIP_DISABLED",
    "SKIP_DUP_CAST",
    "SKIP_DUP_NODE",
    "SKIP_GAP",
    "SKIP_NO_SIGNAL",
    "SKIP_QUOTA",
    "STYLE_SUFFIX",
    "ImageTriggerSvc",
    "TriggerDecision",
    "aspect_to_size",
    "build_image_prompt",
    "build_template_prompt",
    "decide_image",
    "next_story_state",
]
