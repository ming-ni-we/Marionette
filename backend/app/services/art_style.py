"""画风解析（纯函数，零 IO）。
--------------------------------------------------------------------------------
**要解决的问题**：不同世界观的配图长得一模一样。

根因是 `image_trigger.STYLE_SUFFIX` 那一串「写实电影感 …」被**无差别**追加到
所有世界观的出图提示词上 —— 火影忍者（该出日式动画赛璐璐）和惊悚悬疑轻小说
（该出写实电影感）用的是同一句风格词。而世界观/角色卡此前也**没有任何画风字段**，
即系统根本没有「指定画风」的数据通路。

本模块提供那条通路，按下面的优先级解析出**该局专属**的画风：

    世界观显式 setting.art_style  >  世界观 tags 智能推断  >  FALLBACK_STYLE
    角色卡 data.art_style（独立一段，与上面叠加）

**铁律**：
  - 纯函数、零 IO、零 LLM —— 可裸单测，不需要任何 fixture/mock。
  - **绝不抛异常**：任何脏数据（None / 裸字符串 / 嵌套 None）都回退，
    保证调用方**永远**拿到一个非空的世界观画风串。
  - 画风串截断到 `_STYLE_MAX` 字 —— 它要和画面描述共享 `_PROMPT_MAX=400`
    的预算，风格词不该把画面挤掉。
"""

from __future__ import annotations

from typing import Any

#: 全局最终兜底 —— 沿用历史值，保证「没有风格词」这件事永不发生（向后兼容）
FALLBACK_STYLE = "写实电影感，冷色调，胶片颗粒，柔和自然光"

#: 单段画风串长度上限（中文）
_STYLE_MAX = 80

#: 画风族定义：``族名 -> (强锚点关键词, 弱描述词, 画风串)``。
#:
#: **为什么要分强弱两层**（这是本模块最容易做错的地方）：
#: 实测踩过的坑 —— 「雾隐町」的 tags 是 `['轻小说','惊悚悬疑','雾隐町']`。
#: `轻小说` 是**出版形态**（几乎任何日系故事都会打这个 tag），`惊悚悬疑` 才是
#: **题材**。若平铺一张表，「轻小说」先命中就会把一部惊悚悬疑片判成日式动画风。
#:
#: 所以：
#:   - **强锚点**：作品名 / 明确题材词（火影、忍者、仙侠、赛博、悬疑 …）。
#:     命中任一即**直接定案**，不再看别的。
#:   - **弱描述词**：媒介形态 / 泛化修饰（轻小说、漫画、日常、都市 …）。
#:     它们只在**没有任何强锚点时**参与，且按命中数量计分，多者胜。
#:
#: 按强锚点数量降序 → 平手时按弱描述词数量降序 → 再平手按本表顺序（稳定）。
_STYLE_FAMILIES: list[tuple[str, tuple[str, ...], tuple[str, ...], str]] = [
    (
        "anime",
        # 强锚点：作品名 + 明确题材
        (
            "火影",
            "忍者",
            "忍术",
            "查克拉",
            "动漫",
            "动画",
            "二次元",
            "赛璐璐",
            "番剧",
            "少年漫",
            "少女漫",
            "galgame",
        ),
        # 弱描述词：媒介形态 / 泛化风格
        ("轻小说", "漫画", "萌系", "日系", "日式", "gal", "校园"),
        "日式动画赛璐璐风格，明快高饱和配色，干净描边，动画关键帧质感",
    ),
    (
        "wuxia",
        ("古风", "仙侠", "武侠", "江湖", "国风", "水墨", "汉服", "修仙", "古典", "古装", "侠"),
        ("诗词", "山水", "东方"),
        "国风水墨淡彩，宣纸质感，留白构图，青绿山水色调",
    ),
    (
        "scifi",
        (
            "科幻",
            "赛博",
            "机甲",
            "星际",
            "太空",
            "废土",
            "蒸汽朋克",
            "cyberpunk",
            "后启示录",
            "人工智能",
        ),
        ("未来", "机械", "科技"),
        "赛博朋克科幻感，霓虹冷光，全息反光，高对比深色调",
    ),
    (
        "realistic",
        ("写实", "悬疑", "惊悚", "推理", "犯罪", "黑色", "纪实", "恐怖", "灵异"),
        ("电影", "现实", "都市", "日常", "现代"),
        "写实电影感，冷色调，胶片颗粒，柔和自然光",
    ),
    (
        "fantasy",
        ("奇幻", "魔法", "中世纪", "剑与魔法", "史诗", "骑士", "精灵", "矮人", "龙"),
        ("欧洲", "王国", "冒险"),
        "欧式奇幻写实插画，暖金侧光，油画笔触，厚涂质感",
    ),
    (
        "healing",
        ("治愈", "萌宠", "田园", "温暖"),
        ("青春", "生活", "舒缓"),
        "日系治愈水彩，柔和漫射光，低饱和暖调，细腻纸面纹理",
    ),
]


def _score_family(
    lowered: list[str], strong: tuple[str, ...], weak: tuple[str, ...]
) -> tuple[int, int]:
    """算某个画风族的 `(强命中数, 弱命中数)`。"""
    s = sum(1 for kw in strong if any(kw.lower() in tag for tag in lowered))
    w = sum(1 for kw in weak if any(kw.lower() in tag for tag in lowered))
    return s, w


def infer_style_from_tags(tags: Any) -> str | None:
    """按世界观 tags 推断画风串；推断不出返回 `None`。

    匹配规则：**大小写不敏感的子串命中**（tag 里含关键词即算命中）。
    用子串而非全等，是因为用户的 tag 五花八门（「火影忍者」「火影同人」
    「@火影」都该命中）。

    **定案规则**（见 `_STYLE_FAMILIES` 的注释，这里有实测踩坑记录）：
      1. 先看**强锚点**：命中数最多者胜。一个强锚点就足以定案。
         （「火影」压过一切；「惊悚悬疑」压过同组的「轻小说」）
      2. 没有强锚点时，退而看**弱描述词**：命中数最多者胜。
         （只有 `['轻小说']` 这种泛 tag 时，也能推出动画风）
      3. 强弱全都没命中 → `None`（由调用方兜底）。

    遍历顺序由**得分**决定，不依赖 tags 或规则的书写顺序 ——
    保证同一组 tags 结果稳定、可预测。

    脏数据（None / 裸字符串 / `[None, ""]`）一律返回 `None`，不抛异常。
    """
    if not isinstance(tags, (list, tuple, set)):
        return None
    lowered = [str(t).strip().lower() for t in tags if str(t or "").strip()]
    if not lowered:
        return None

    scored: list[tuple[tuple[int, int], str]] = []
    for _name, strong, weak, style in _STYLE_FAMILIES:
        s, w = _score_family(lowered, strong, weak)
        if s or w:
            scored.append(((s, w), style))

    if not scored:
        return None
    # 强命中优先，其次弱命中；同为最大值的取先出现者（`max` 在并列时返回第一个）
    best = max(scored, key=lambda item: item[0])
    return best[1]


def resolve_art_style(
    *,
    world_setting: Any = None,
    world_tags: Any = None,
    card_data: Any = None,
) -> tuple[str, str]:
    """解析该局画风，返回 ``(world_style, character_style)`` **两段独立串**。

    - ``world_style``     —— **整体画风**（媒介 / 笔触 / 色调 / 光照）。
      优先级：世界观显式 `setting.art_style` > tags 推断 > `FALLBACK_STYLE`。
      **保证非空**。
    - ``character_style`` —— **该角色的外观/人设**（发色 / 服饰 / 气质）。
      取自角色卡 `data.art_style`，**可以为空串**（没填就不注入这一段）。

    **为什么返回两段而不是拼成一串**：
    `"日式动画赛璐璐风格，穿深灰长衫的男子"` 这样直接相连，模型会把
    「深灰长衫」也当成画风词，甚至渲染出「赛璐璐质感的衣服」这类语义污染。
    分成两段后，`build_image_prompt` 会把它们放进带中文标题的不同区块
    （`【画面风格】` / `【角色外观】`），零成本完成语义隔离。

    **优先级语义**：用户拍板的「角色卡 > 世界观」是**叠加**而非覆盖 ——
    世界观管整体画风，角色卡管这个人的长相。两者语义不同，本就该同时生效。
    """
    # ---- 世界观层：显式 > tags 推断 > 兜底 ----
    ws = world_setting if isinstance(world_setting, dict) else {}
    explicit = str(ws.get("art_style") or "").strip()
    if explicit:
        world = explicit[:_STYLE_MAX]
    else:
        inferred = infer_style_from_tags(world_tags)
        world = (inferred or FALLBACK_STYLE)[:_STYLE_MAX]

    # ---- 角色卡层：该角色的外观/人设（可空）----
    cd = card_data if isinstance(card_data, dict) else {}
    character = str(cd.get("art_style") or "").strip()[:_STYLE_MAX]

    return world, character


__all__ = [
    "FALLBACK_STYLE",
    "infer_style_from_tags",
    "resolve_art_style",
]
