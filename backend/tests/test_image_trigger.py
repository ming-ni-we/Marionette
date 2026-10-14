"""出图触发时机单测（`app/services/image_trigger.py`，S16 §4.6.3）。

覆盖四类：

  1. **触发规则**：节点触发 / 新角色登场 / 都不满足 / 开关关闭
  2. **去重**：同一节点只画一次、同一角色只画一次
  3. **节流**：配额上限、最小间隔
  4. **提示词**：模板兜底、LLM 输出清洗、扩写失败降级

设计要点：`decide_image` 是**纯函数**（无 IO），所以触发规则测试不需要任何 mock。
只有提示词扩写需要 mock `LLMRouter`。
"""

from __future__ import annotations

import pytest

from app.adapters.base import ChatMessage
from app.services.image_trigger import (
    DEFAULT_MIN_GAP,
    DEFAULT_QUOTA,
    REASON_CAST,
    REASON_NODE,
    SKIP_DISABLED,
    SKIP_DUP_CAST,
    SKIP_DUP_NODE,
    SKIP_GAP,
    SKIP_NO_SIGNAL,
    SKIP_QUOTA,
    STYLE_SUFFIX,
    ImageTriggerSvc,
    aspect_to_size,
    build_template_prompt,
    decide_image,
    next_story_state,
)

# --------------------------------------------------------------------------- #
# 测试夹具
# --------------------------------------------------------------------------- #
CAST = [
    {"id": "c1", "name": "沈砚", "voice": "穿深灰长衫的年轻男子，眉骨有旧疤"},
    {"id": "c2", "name": "阿箩", "voice": "戴银簪的少女，月白短襦"},
]

SCENE = {
    "location": "雨夜的青石板巷",
    "time": "子时",
    "mood": "压抑",
    "beat": "灯笼在风里晃",
    "present": ["c1"],
}

NODE = {"id": "n_dagger", "title": "匕首现形", "brief": "沈砚亮出匕首"}


def _story(**over) -> dict:
    base = {
        "image_count": 0,
        "last_image_turn": None,
        "image_nodes": [],
        "image_cast": [],
    }
    base.update(over)
    return base


def _decide(**over):
    kwargs = {
        "enabled": True,
        "turn": 10,
        "story": _story(),
        "node_triggered": None,
        "cast": CAST,
        "speakers": [],
        "quota": DEFAULT_QUOTA,
        "min_gap": DEFAULT_MIN_GAP,
    }
    kwargs.update(over)
    return decide_image(**kwargs)


# --------------------------------------------------------------------------- #
# 1. 触发规则
# --------------------------------------------------------------------------- #
class TestTriggerRules:
    def test_node_trigger_fires(self) -> None:
        """节点触发 → 出图，reason=node，并带上节点素材。"""
        d = _decide(node_triggered=NODE)
        assert d.should is True
        assert d.reason == REASON_NODE
        assert d.seed["node_id"] == "n_dagger"
        assert d.seed["node_title"] == "匕首现形"

    def test_new_character_fires(self) -> None:
        """无节点但有新角色 → 出图，reason=cast。"""
        d = _decide(cast=CAST, speakers=[CAST[0]])
        assert d.should is True
        assert d.reason == REASON_CAST
        assert d.seed["character_id"] == "c1"

    def test_node_wins_over_cast(self) -> None:
        """节点与角色同时满足 → 节点优先（更强的信号）。"""
        d = _decide(node_triggered=NODE, speakers=[CAST[0]])
        assert d.should is True
        assert d.reason == REASON_NODE

    def test_no_signal_skips(self) -> None:
        """所有角色都画过、又没有节点 → 不出图。"""
        d = _decide(
            cast=CAST,
            speakers=CAST,
            story=_story(image_cast=["c1", "c2"]),
        )
        assert d.should is False
        assert d.reason == SKIP_NO_SIGNAL

    def test_disabled_skips_even_with_node(self) -> None:
        """开关关闭时，即使节点触发也不出图（默认关闭是刻意的）。"""
        d = _decide(enabled=False, node_triggered=NODE)
        assert d.should is False
        assert d.reason == SKIP_DISABLED

    def test_empty_cast_does_not_fire(self) -> None:
        """没有角色、没有节点 → 不出图（不能凭空造图）。"""
        d = _decide(cast=[], speakers=[])
        assert d.should is False
        assert d.reason == SKIP_NO_SIGNAL

    def test_speakers_take_priority_over_cast_pool(self) -> None:
        """speakers 优先于 cast —— 本轮真正出场的人先拿视觉锚点。"""
        d = _decide(cast=CAST, speakers=[CAST[1]])
        assert d.seed["character_id"] == "c2"


# --------------------------------------------------------------------------- #
# 2. 去重
# --------------------------------------------------------------------------- #
class TestDedup:
    def test_same_node_not_drawn_twice(self) -> None:
        """同一节点画过 → 不再画；若此时也无新角色，应给出 dup_node。"""
        d = _decide(
            node_triggered=NODE,
            cast=CAST,
            speakers=CAST,
            story=_story(image_nodes=["n_dagger"], image_cast=["c1", "c2"]),
        )
        assert d.should is False
        assert d.reason == SKIP_DUP_NODE

    def test_different_node_fires(self) -> None:
        """换一个节点 → 可以出图。"""
        d = _decide(
            node_triggered={"id": "n_other", "title": "另一件事"},
            story=_story(image_nodes=["n_dagger"]),
            cast=[],
            speakers=[],
        )
        assert d.should is True
        assert d.seed["node_id"] == "n_other"

    def test_same_character_not_drawn_twice(self) -> None:
        """同一角色画过 → 不再画；也不会误报 dup_cast（该原因留给显式场景）。"""
        d = _decide(
            cast=CAST,
            speakers=[CAST[0]],
            story=_story(image_cast=["c1"]),
        )
        # c2 还没画过，所以这里应该命中 c2 而非跳过
        assert d.should is True
        assert d.seed["character_id"] == "c2"

    def test_all_characters_drawn_skips(self) -> None:
        d = _decide(
            cast=CAST,
            speakers=CAST,
            story=_story(image_cast=["c1", "c2"]),
        )
        assert d.should is False
        assert d.reason == SKIP_NO_SIGNAL

    def test_dup_cast_constant_is_reachable_in_docs(self) -> None:
        """SKIP_DUP_CAST 是保留常量（供未来显式去重路径使用），确保它可被导入。"""
        assert SKIP_DUP_CAST == "dup_cast"


# --------------------------------------------------------------------------- #
# 3. 节流
# --------------------------------------------------------------------------- #
class TestThrottle:
    def test_quota_exhausted_skips(self) -> None:
        """配额用满 → 即使节点触发也不画（硬性成本上限）。"""
        d = _decide(
            node_triggered=NODE,
            story=_story(image_count=DEFAULT_QUOTA),
        )
        assert d.should is False
        assert d.reason == SKIP_QUOTA

    def test_quota_boundary_one_left_still_fires(self) -> None:
        """配额剩 1 张时仍可出图。"""
        d = _decide(
            node_triggered=NODE,
            story=_story(image_count=DEFAULT_QUOTA - 1),
        )
        assert d.should is True

    def test_min_gap_blocks_too_soon(self) -> None:
        """距上次出图不足 min_gap 轮 → 不出图。"""
        d = _decide(
            turn=10,
            node_triggered=NODE,
            story=_story(last_image_turn=9),
            min_gap=2,
        )
        assert d.should is False
        assert d.reason == SKIP_GAP

    def test_min_gap_boundary_allows(self) -> None:
        """刚好满足 min_gap → 可以出图。"""
        d = _decide(
            turn=10,
            node_triggered=NODE,
            story=_story(last_image_turn=8),
            min_gap=2,
        )
        assert d.should is True

    def test_check_order_throttle_before_signal(self) -> None:
        """节流先于信号判定：配额耗尽时即使有强信号也直接跳过。"""
        d = _decide(
            node_triggered=NODE,
            cast=CAST,
            speakers=CAST,
            story=_story(image_count=99),
        )
        assert d.should is False
        assert d.reason == SKIP_QUOTA

    def test_dirty_gap_value_does_not_crash(self) -> None:
        """story 里的脏数据（字符串 / None）不能让判定抛异常。"""
        d = _decide(
            turn=10,
            node_triggered=NODE,
            story=_story(last_image_turn="not-a-number", image_count="bad"),
        )
        # image_count 无法转 int → 视为 0；间隔无法计算 → 放行
        assert d.should is True

    def test_none_turn_never_blocks(self) -> None:
        """从未出过图（last_image_turn=None）→ 间隔不构成阻塞。"""
        d = _decide(turn=0, node_triggered=NODE, story=_story(last_image_turn=None))
        assert d.should is True


# --------------------------------------------------------------------------- #
# 4. 状态回写
# --------------------------------------------------------------------------- #
class TestNextStoryState:
    def test_node_reason_records_node_id(self) -> None:
        patch = next_story_state(
            story=_story(), turn=7, reason=REASON_NODE, seed={"node_id": "n_x"}
        )
        assert patch["image_count"] == 1
        assert patch["last_image_turn"] == 7
        assert patch["image_nodes"] == ["n_x"]
        assert "image_cast" not in patch

    def test_cast_reason_records_character_id(self) -> None:
        patch = next_story_state(
            story=_story(), turn=7, reason=REASON_CAST, seed={"character_id": "c1"}
        )
        assert patch["image_cast"] == ["c1"]
        assert "image_nodes" not in patch

    def test_accumulates_and_dedups(self) -> None:
        patch = next_story_state(
            story=_story(image_cast=["c1", "c2"], image_count=2),
            turn=9,
            reason=REASON_CAST,
            seed={"character_id": "c1"},
        )
        assert patch["image_count"] == 3
        assert patch["image_cast"] == ["c1", "c2"]  # 去重且有序

    def test_manual_reason_only_counts(self) -> None:
        """手动出图不记节点/角色（玩家点的不应消耗自动触发的去重名额）。"""
        patch = next_story_state(
            story=_story(), turn=3, reason="manual", seed={"node_id": "n_x"}
        )
        assert patch["image_count"] == 1
        assert "image_nodes" not in patch


# --------------------------------------------------------------------------- #
# 5. 提示词
# --------------------------------------------------------------------------- #
class TestTemplatePrompt:
    def test_includes_scene_fields_and_style(self) -> None:
        prompt, negative, aspect = build_template_prompt(
            scene=SCENE, story=_story(), cast=CAST
        )
        assert "雨夜的青石板巷" in prompt
        assert "压抑" in prompt
        assert "灯笼在风里晃" in prompt
        assert STYLE_SUFFIX in prompt
        assert negative  # 有默认负面词
        assert aspect == "landscape"

    def test_includes_new_character_appearance(self) -> None:
        """新角色登场时，把外观描述拼进去（而不是名字）。"""
        prompt, _, _ = build_template_prompt(
            scene=SCENE,
            story=_story(),
            cast=CAST,
            seed={"character": CAST[0]},
        )
        assert "眉骨有旧疤" in prompt

    def test_empty_scene_still_produces_prompt(self) -> None:
        """场景全空也要能拼出一个（朴素的）提示词 —— 不能返回空串。"""
        prompt, _, _ = build_template_prompt(scene={}, story=_story(), cast=[])
        assert prompt.strip()
        assert STYLE_SUFFIX in prompt

    def test_negative_excludes_text_and_watermark(self) -> None:
        """默认负面词必须排除文字与水印（实测最影响观感的两类）。"""
        _, negative, _ = build_template_prompt(scene=SCENE, story=_story(), cast=[])
        assert "文字" in negative
        assert "水印" in negative


class TestAspectToSize:
    @pytest.mark.parametrize(
        ("aspect", "expected"),
        [
            ("landscape", (1280, 720)),
            ("portrait", (720, 1280)),
            ("square", (1024, 1024)),
        ],
    )
    def test_known_aspects(self, aspect, expected) -> None:
        size = aspect_to_size(aspect)
        assert (size["width"], size["height"]) == expected

    def test_unknown_aspect_falls_back(self) -> None:
        size = aspect_to_size("nonsense")
        assert (size["width"], size["height"]) == (1280, 720)

    def test_explicit_wh_wins(self) -> None:
        size = aspect_to_size("square", width=640, height=480)
        assert (size["width"], size["height"]) == (640, 480)


# --------------------------------------------------------------------------- #
# 6. LLM 扩写（需要 mock）
# --------------------------------------------------------------------------- #
class _FakeRouter:
    """假 router：按调用次序返回预设文本，并记录收到的 messages。"""

    def __init__(self, responses: list[str | None]) -> None:
        self._responses = list(responses)
        self.calls: list[list[ChatMessage]] = []

    async def complete(self, messages, *, params=None, overrides=None):  # noqa: ANN001
        self.calls.append(list(messages))
        if not self._responses:
            return None
        return self._responses.pop(0)


def _build_messages_has_scene(msgs: list[ChatMessage]) -> bool:
    text = "\n".join(m.content for m in msgs)
    return "雨夜的青石板巷" in text


@pytest.mark.asyncio
async def test_llm_success_uses_llm_source() -> None:
    router = _FakeRouter(['{"prompt": "雨夜长巷，灯笼摇晃", "aspect": "square"}'])
    svc = ImageTriggerSvc(router=router)
    prompt, negative, aspect, source = await svc.render_prompt(
        scene=SCENE, story=_story(), cast=CAST
    )
    assert source == "llm"
    assert prompt == "雨夜长巷，灯笼摇晃"
    assert aspect == "square"
    assert negative  # 未给则补默认负面词
    assert _build_messages_has_scene(router.calls[0])


@pytest.mark.asyncio
async def test_llm_fenced_json_still_parsed() -> None:
    """模型套了 markdown 围栏也要能解析。"""
    router = _FakeRouter(['```json\n{"prompt": "雪原上的孤灯"}\n```'])
    svc = ImageTriggerSvc(router=router)
    prompt, _, _, source = await svc.render_prompt(scene=SCENE, story=_story(), cast=CAST)
    assert source == "llm"
    assert prompt == "雪原上的孤灯"


@pytest.mark.asyncio
async def test_llm_garbage_falls_back_to_template() -> None:
    """两次都解析失败 → 退回模板，且**仍然产出提示词**（只降质量不降可用性）。"""
    router = _FakeRouter(["不是 JSON", "还是不是 JSON"])
    svc = ImageTriggerSvc(router=router)
    prompt, negative, aspect, source = await svc.render_prompt(
        scene=SCENE, story=_story(), cast=CAST
    )
    assert source == "template"
    assert "雨夜的青石板巷" in prompt
    assert STYLE_SUFFIX in prompt
    assert negative
    assert len(router.calls) == 2  # 降级重试了一次（先去 json_format，再去掉）


@pytest.mark.asyncio
async def test_llm_empty_prompt_falls_back() -> None:
    """解析成功但 prompt 为空 → 视为不可用，退回模板。"""
    router = _FakeRouter(['{"prompt": "   "}', '{"prompt": ""}'])
    svc = ImageTriggerSvc(router=router)
    prompt, _, _, source = await svc.render_prompt(scene=SCENE, story=_story(), cast=CAST)
    assert source == "template"
    assert prompt.strip()


@pytest.mark.asyncio
async def test_llm_exception_falls_back_not_raises() -> None:
    """router 抛异常也不能冒泡 —— 出图绝不能因为扩写失败而取消。"""

    class _Boom:
        async def complete(self, *_a, **_kw):
            raise RuntimeError("upstream down")

    svc = ImageTriggerSvc(router=_Boom())
    prompt, _, _, source = await svc.render_prompt(scene=SCENE, story=_story(), cast=CAST)
    assert source == "template"
    assert prompt.strip()


@pytest.mark.asyncio
async def test_use_llm_false_skips_router() -> None:
    """显式关掉 LLM 扩写时，不应调用 router。"""
    router = _FakeRouter(['{"prompt": "不该被用到"}'])
    svc = ImageTriggerSvc(router=router)
    _, _, _, source = await svc.render_prompt(
        scene=SCENE, story=_story(), cast=CAST, use_llm=False
    )
    assert source == "template"
    assert router.calls == []


@pytest.mark.asyncio
async def test_prompt_includes_node_reason() -> None:
    """触发原因（节点标题）要喂给扩写模型，让它知道「为什么画这一刻」。"""
    router = _FakeRouter(['{"prompt": "刀刃反光"}'])
    svc = ImageTriggerSvc(router=router)
    await svc.render_prompt(
        scene=SCENE,
        story=_story(),
        cast=CAST,
        seed={"node_id": "n_dagger", "node_title": "匕首现形", "node_brief": "沈砚亮出匕首"},
    )
    text = "\n".join(m.content for m in router.calls[0])
    assert "匕首现形" in text
    assert "沈砚亮出匕首" in text


# --------------------------------------------------------------------------- #
# 6. 脏数据守卫（输入来自 LLM 的 JSON，绝不能让对话主流崩）
# --------------------------------------------------------------------------- #
class TestDirtyNodeTriggered:
    """`node_triggered` 契约是 `dict | None`，但由 LLM 生成，必须容忍走样。

    **背景（真实事故）**：手工验证时传了字符串 `"n1"` 而非 `{"id": "n1"}`，
    `decide_image` 抛 `AttributeError: 'str' object has no attribute 'get'`。
    该方法在对话主流里**同步调用**，一崩就是整轮回复失败 —— 出图这种附属功能
    绝不能有这种杀伤力。
    """

    def test_string_node_is_coerced_to_id(self) -> None:
        """模型直接吐字符串 id 时，当作 `{"id": ...}` 处理（而非崩溃）。"""
        d = _decide(node_triggered="n_dagger")

        assert d.should is True
        assert d.reason == REASON_NODE
        assert d.seed["node_id"] == "n_dagger"

    def test_empty_string_is_ignored(self) -> None:
        d = _decide(node_triggered="   ", cast=[], speakers=[])

        assert d.should is False
        assert d.reason == SKIP_NO_SIGNAL

    @pytest.mark.parametrize("junk", [123, 4.5, ["n1"], {"nested": "x"}, object()])
    def test_non_dict_non_str_does_not_crash(self, junk: object) -> None:
        """任何非 dict/非 str 的脏值都只应「视为无节点信号」，绝不抛异常。"""
        d = _decide(node_triggered=junk, cast=[], speakers=[])

        assert d.should is False
        assert d.reason == SKIP_NO_SIGNAL

    def test_dict_without_id_falls_through_to_cast(self) -> None:
        """缺 id 的节点对象视为无节点信号，但不应影响「新角色」这条次强信号。"""
        d = _decide(node_triggered={"title": "只有标题没有 id"})

        assert d.should is True
        assert d.reason == REASON_CAST

    def test_string_node_dedup_uses_same_key(self) -> None:
        """字符串节点与 dict 节点必须共用同一套去重键，否则会重复出图。

        注意：断言「**不是** `REASON_NODE`」而非「`should is False`」——
        节点被去重后，设计上会继续探测次强信号（新角色登场），因此
        `reason` 会落到 `REASON_CAST`。这里把 cast 清空以隔离出「节点去重」本身。
        """
        # 先用 dict 形态画过
        d1 = _decide(node_triggered=NODE)
        assert d1.reason == REASON_NODE

        # 再用字符串形态触发同一节点 → 节点信号应被去重拦下
        story = _story(image_count=1, last_image_turn=0, image_nodes=["n_dagger"])
        d2 = _decide(node_triggered="n_dagger", story=story, turn=10)

        assert d2.reason != REASON_NODE, "同一节点不得因形态不同而重复触发"

        # 隔离验证：无角色可选时，去重后应报告 dup_node
        d3 = _decide(node_triggered="n_dagger", story=story, turn=10, cast=[], speakers=[])
        assert d3.should is False
        assert d3.reason == SKIP_DUP_NODE
