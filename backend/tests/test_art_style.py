"""画风解析测试（`app.services.art_style`）。

纯函数模块，**不需要任何 fixture / mock / DB** —— 这也是把它独立成模块的
收益之一（对照 `image_trigger` 的测试要造 scene/cast/seed 一堆夹具）。

重点覆盖两类易错点：
  1. **强弱打分**：实测踩过的坑 —— 「雾隐町」的 tags 是
     `['轻小说','惊悚悬疑','雾隐町']`，`轻小说` 是出版形态（泛词）、
     `惊悚悬疑` 才是题材。若平铺一张表，`轻小说` 先命中会把一部惊悚悬疑片
     判成日式动画风。所以专门有用例盯着「强锚点压过泛词」。
  2. **脏数据韧性**：这个函数的输入来自 JSONB（历史数据可能有任何形态），
     绝不能因为一个脏字段就抛异常拖垮出图。
"""

from __future__ import annotations

from app.services.art_style import (
    FALLBACK_STYLE,
    infer_style_from_tags,
    resolve_art_style,
)


# --------------------------------------------------------------------------- #
# infer_style_from_tags
# --------------------------------------------------------------------------- #
class TestInferStyleFromTags:
    def test_anime_by_franchise_anchor(self) -> None:
        """「火影」这类作品名是最强锚点。"""
        got = infer_style_from_tags(["火影忍者", "同人", "疾风传", "任务推进", "二次元"])
        assert got is not None
        assert "动画" in got and "赛璐璐" in got

    def test_thriller_beats_generic_medium_tag(self) -> None:
        """回归守卫：**强锚点（题材）必须压过弱描述词（出版形态）**。

        实测数据：雾隐町 tags = ['轻小说','惊悚悬疑','雾隐町']。
        「轻小说」属于动画族的弱描述词，「惊悚悬疑」属于写实族的强锚点 ——
        必须判成写实电影感，否则一部惊悚悬疑片会出成日式动画风。
        """
        got = infer_style_from_tags(["轻小说", "惊悚悬疑", "雾隐町"])
        assert got is not None
        assert "写实电影感" in got
        assert "动画" not in got

    def test_generic_medium_alone_still_infers(self) -> None:
        """只有泛 tag（无强锚点）时，弱描述词也要能兜住 —— 别退回全局兜底。"""
        got = infer_style_from_tags(["轻小说"])
        assert got is not None
        assert "动画" in got

    def test_wuxia(self) -> None:
        got = infer_style_from_tags(["古风", "仙侠"])
        assert got is not None and "水墨" in got

    def test_scifi(self) -> None:
        got = infer_style_from_tags(["科幻", "赛博"])
        assert got is not None and "赛博朋克" in got

    def test_fantasy(self) -> None:
        got = infer_style_from_tags(["奇幻", "魔法", "中世纪"])
        assert got is not None and "奇幻" in got

    def test_healing(self) -> None:
        got = infer_style_from_tags(["治愈", "萌宠"])
        assert got is not None and "水彩" in got

    def test_case_insensitive(self) -> None:
        """英文 tag 大小写不敏感。"""
        got = infer_style_from_tags(["Cyberpunk"])
        assert got is not None and "赛博朋克" in got

    def test_substring_match(self) -> None:
        """子串命中：用户 tag 五花八门（「火影同人」「@火影」都该命中）。"""
        assert infer_style_from_tags(["火影同人"]) is not None
        assert infer_style_from_tags(["@火影"]) is not None

    def test_no_match_returns_none(self) -> None:
        assert infer_style_from_tags(["随便", "别的"]) is None

    def test_dirty_input_never_raises(self) -> None:
        """JSONB 里什么都可能有 —— 一律返回 None，绝不抛。"""
        assert infer_style_from_tags(None) is None
        assert infer_style_from_tags("abc") is None  # 裸字符串不是列表
        assert infer_style_from_tags(123) is None
        assert infer_style_from_tags([None, "", "  "]) is None
        assert infer_style_from_tags([]) is None
        assert infer_style_from_tags({"a": 1}) is None

    def test_result_is_stable_regardless_of_tag_order(self) -> None:
        """得分决定结果，不依赖 tags 书写顺序 —— 保证可预测。"""
        a = infer_style_from_tags(["悬疑", "轻小说"])
        b = infer_style_from_tags(["轻小说", "悬疑"])
        assert a == b
        assert a is not None and "写实" in a


# --------------------------------------------------------------------------- #
# resolve_art_style
# --------------------------------------------------------------------------- #
class TestResolveArtStyle:
    def test_explicit_setting_wins_over_tags(self) -> None:
        """世界观显式填了画风 → 无视 tags 推断。"""
        world, _char = resolve_art_style(
            world_setting={"art_style": "油画厚涂感"},
            world_tags=["火影忍者"],
        )
        assert world == "油画厚涂感"

    def test_tags_inference_when_no_explicit(self) -> None:
        world, _char = resolve_art_style(
            world_setting={"era": "战国"},
            world_tags=["火影忍者", "二次元"],
        )
        assert "动画" in world

    def test_fallback_when_nothing_available(self) -> None:
        """两样都没有 → 全局兜底（**保证非空**，不能出现「没有风格词」）。"""
        world, char = resolve_art_style()
        assert world == FALLBACK_STYLE
        assert char == ""

    def test_fallback_when_tags_unmatched(self) -> None:
        world, _ = resolve_art_style(world_tags=["完全不认识的词"])
        assert world == FALLBACK_STYLE

    def test_character_style_is_independent_segment(self) -> None:
        """角色外观与世界观画风是**两段独立串**，不拼接。

        分开返回是为了让 `build_image_prompt` 放进两个带标题的区块 ——
        若拼成 `"日式动画赛璐璐，银白长发"`，模型会把「银白长发」也当画风词。
        """
        world, char = resolve_art_style(
            world_tags=["火影忍者"],
            card_data={"art_style": "银白长发，黑色立领制服"},
        )
        assert "动画" in world
        assert char == "银白长发，黑色立领制服"
        assert "银白长发" not in world  # 关键：没被混进画风串

    def test_character_style_empty_when_absent(self) -> None:
        _world, char = resolve_art_style(card_data={})
        assert char == ""

    def test_explicit_style_truncated(self) -> None:
        """超长画风串截断 —— 它要和画面描述共享 prompt 预算。"""
        world, char = resolve_art_style(
            world_setting={"art_style": "深" * 500},
            card_data={"art_style": "长" * 500},
        )
        assert len(world) <= 80
        assert len(char) <= 80

    def test_all_dirty_inputs_no_raise(self) -> None:
        """三维度全传脏数据 → 回退兜底，不抛。"""
        world, char = resolve_art_style(
            world_setting="不是 dict",  # type: ignore[arg-type]
            world_tags=12345,  # type: ignore[arg-type]
            card_data=["也不是 dict"],  # type: ignore[arg-type]
        )
        assert world == FALLBACK_STYLE
        assert char == ""

    def test_whitespace_only_treated_as_empty(self) -> None:
        """只填了空格视为没填 —— 别把空白塞进 prompt。"""
        world, char = resolve_art_style(
            world_setting={"art_style": "   "},
            world_tags=["火影忍者"],
            card_data={"art_style": "  \n "},
        )
        assert "动画" in world  # 空白 → 走 tags 推断
        assert char == ""
