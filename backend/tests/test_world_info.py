"""AC-07 / AC-08 机械证据：世界书触发三态可区分 + 逐条目 trace。

三态（必须能同时构造并断言）：
  1. 未命中            -> matched=False
  2. 命中且在预算内    -> matched=True,  in_budget=True
  3. 命中但被预算挤出  -> matched=True,  in_budget=False
"""

from __future__ import annotations

from app.services.world_info import WorldInfoEngine

ENGINE = WorldInfoEngine()


def _entry(entry_id: str, keys: list[str], content: str, **kw: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": entry_id,
        "keys": keys,
        "secondary_keys": [],
        "content": content,
        "comment": entry_id,
        "enabled": True,
        "constant": False,
        "insertion_order": 100,
        "priority": 10,
        "position": "before_char",
    }
    base.update(kw)
    return base


def _by_id(result: dict, entry_id: str) -> dict:
    return next(e for e in result["entries"] if e["entry_id"] == entry_id)


# --------------------------------------------------------------------------- #
# 三态
# --------------------------------------------------------------------------- #
def test_three_states_are_distinguishable() -> None:
    # 预算 20：常驻 5 + 命中 8 = 13 可保留；被挤出的那条 30 字 -> 31 token，超预算被挤出
    book = {
        "token_budget": 20,
        "scan_depth": 4,
        "entries": [
            _entry("e-const", [], "常驻设定", constant=True, insertion_order=1, priority=100),
            _entry("e-hit", ["咖啡馆"], "命中且在预算内", insertion_order=2, priority=50),
            _entry("e-miss", ["月球"], "不该命中", insertion_order=3, priority=20),
            _entry(
                "e-evict",
                ["咖啡"],
                "这一条内容会命中关键词咖啡但因为优先级最低会被挤出预算所以不进入最终注入",
                insertion_order=4,
                priority=1,
            ),
        ],
    }
    result = ENGINE.test(book, "我推开咖啡馆的门，外面开始下雨了。")

    const, hit, miss, evict = (_by_id(result, eid) for eid in ("e-const", "e-hit", "e-miss", "e-evict"))

    # 态 1：未命中
    assert miss["matched"] is False
    assert miss["in_budget"] is False
    assert miss["match_type"] == "none"
    assert miss["final_position"] is None

    # 态 2：命中且在预算内
    assert const["matched"] is True and const["match_type"] == "constant" and const["in_budget"] is True
    assert hit["matched"] is True and hit["match_type"] == "keyword" and hit["in_budget"] is True
    assert hit["matched_key"] == "咖啡馆"
    assert hit["final_position"] == "before_char"

    # 态 3：命中但被挤出（绝不静默丢弃：仍出现在结果里）
    assert evict["matched"] is True
    assert evict["in_budget"] is False
    assert evict["matched_key"] == "咖啡"
    assert evict["final_position"] is None
    assert "超出预算" in evict["note"]

    # 汇总计数与契约字段
    assert result["matched_count"] == 3
    assert result["in_budget_count"] == 2
    assert result["evicted_count"] == 1
    assert result["total_tokens"] == const["token_count"] + hit["token_count"]
    assert result["token_budget"] == 20
    # 逐条目必须带 AC-08 要求的五个字段
    for entry in result["entries"]:
        for field in ("matched", "match_type", "in_budget", "token_count", "final_position"):
            assert field in entry, field


def test_nothing_matched_when_text_is_irrelevant() -> None:
    book = {"token_budget": 1024, "entries": [_entry("a", ["咖啡馆"], "内容")]}
    result = ENGINE.test(book, "今天天气不错，我去爬山了。")
    assert result["matched_count"] == 0
    assert result["total_tokens"] == 0
    assert _by_id(result, "a")["matched"] is False


def test_within_budget_keeps_everything() -> None:
    book = {
        "token_budget": 10000,
        "entries": [_entry("a", ["咖啡"], "第一条命中内容"), _entry("b", ["下雨"], "第二条命中内容")],
    }
    result = ENGINE.test(book, "咖啡馆外面下雨了。")
    assert result["matched_count"] == 2
    assert result["in_budget_count"] == 2
    assert result["evicted_count"] == 0
    assert all(e["in_budget"] for e in result["entries"])


# --------------------------------------------------------------------------- #
# 触发语义
# --------------------------------------------------------------------------- #
def test_keyword_is_case_insensitive_substring_by_default() -> None:
    book = {"entries": [_entry("a", ["HELLO"], "命中了英文关键词")]}
    assert ENGINE.test(book, "say hello to me")["matched_count"] == 1


def test_case_sensitive_flag_is_respected() -> None:
    book = {"entries": [_entry("a", ["HELLO"], "内容", case_sensitive=True)]}
    assert ENGINE.test(book, "say hello")["matched_count"] == 0
    assert ENGINE.test(book, "say HELLO")["matched_count"] == 1


def test_match_whole_words_blocks_partial_hit() -> None:
    book = {"entries": [_entry("a", ["cat"], "内容", match_whole_words=True)]}
    assert ENGINE.test(book, "concatenate")["matched_count"] == 0
    assert ENGINE.test(book, "a cat sat")["matched_count"] == 1


def test_disabled_entry_never_matches() -> None:
    book = {"entries": [_entry("a", ["咖啡"], "内容", enabled=False)]}
    entry = _by_id(ENGINE.test(book, "咖啡馆"), "a")
    assert entry["matched"] is False
    assert "已禁用" in entry["note"]


def test_selective_requires_secondary_keyword() -> None:
    book = {
        "entries": [
            _entry("a", ["咖啡"], "内容", selective=True, secondary_keys=["雨天"])
        ]
    }
    assert ENGINE.test(book, "我在咖啡馆坐着。")["matched_count"] == 0
    assert ENGINE.test(book, "雨天，我在咖啡馆坐着。")["matched_count"] == 1


def test_regex_matching_sets_match_type_regex() -> None:
    book = {"entries": [_entry("a", [r"第\d+天"], "内容", use_regex=True)]}
    entry = _by_id(ENGINE.test(book, "这是第3天。"), "a")
    assert entry["matched"] is True
    assert entry["match_type"] == "regex"
    assert entry["matched_key"] == r"第\d+天"


def test_invalid_regex_degrades_to_literal_with_warning() -> None:
    book = {"entries": [_entry("a", ["第["], "内容", use_regex=True)]}
    entry = _by_id(ENGINE.test(book, "括号写作 第[ 的样子"), "a")
    assert entry["matched"] is True  # 降级为字面匹配
    assert entry["warnings"] and "编译失败" in entry["warnings"][0]


def test_recursive_scanning_triggers_second_entry() -> None:
    book = {
        "recursive_scanning": True,
        "max_recursion_depth": 3,
        "entries": [
            _entry("a", ["启动"], "这段话里藏着暗号：月光钥匙。"),
            _entry("b", ["月光钥匙"], "只有被递归触发才会出现的内容。"),
        ],
    }
    result = ENGINE.test(book, "现在启动。")
    assert _by_id(result, "a")["matched"] is True
    second = _by_id(result, "b")
    assert second["matched"] is True
    assert "递归" in second["note"]


def test_recursion_depth_is_capped() -> None:
    book = {
        "recursive_scanning": True,
        "max_recursion_depth": 1,
        "entries": [
            _entry("a", ["启动"], "暗号甲。"),
            _entry("b", ["暗号甲"], "暗号乙。"),
            _entry("c", ["暗号乙"], "最末端内容。"),
        ],
    }
    result = ENGINE.test(book, "启动。")
    assert _by_id(result, "a")["matched"] is True
    assert _by_id(result, "b")["matched"] is True
    assert _by_id(result, "c")["matched"] is False  # 超过 max_recursion_depth=1


def test_higher_priority_is_kept_when_budget_is_tight() -> None:
    long_text = "很长的一段内容" * 6  # 每条约 43 token
    book = {
        "token_budget": 50,
        "entries": [
            _entry("low", ["命中"], long_text, priority=1),
            _entry("high", ["命中"], long_text, priority=99),
        ],
    }
    result = ENGINE.test(book, "命中")
    assert _by_id(result, "high")["in_budget"] is True
    assert _by_id(result, "low")["in_budget"] is False
    assert result["evicted_count"] == 1


def test_output_order_follows_insertion_order() -> None:
    book = {
        "entries": [
            _entry("later", ["命中"], "第三条", insertion_order=300),
            _entry("first", ["命中"], "第一条", insertion_order=100),
            _entry("middle", ["命中"], "第二条", insertion_order=200),
        ]
    }
    order = [e["entry_id"] for e in ENGINE.test(book, "命中")["entries"]]
    assert order == ["first", "middle", "later"]


def test_scan_depth_override_is_reported() -> None:
    book = {"scan_depth": 4, "entries": []}
    assert ENGINE.test(book, "x")["scan_depth"] == 4
    assert ENGINE.test(book, "x", scan_depth=9)["scan_depth"] == 9
