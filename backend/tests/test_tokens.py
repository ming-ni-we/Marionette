"""Token 估算必须"取大不取小"（保守）。

保守方向很重要：宁可把条目判为"被预算挤出"，也不要实际超限让上游截断。
"""

from __future__ import annotations

from app.services.tokens import count_wide, estimate_tokens, estimate_tokens_many


def test_empty_input_costs_nothing() -> None:
    assert estimate_tokens(None) == 0
    assert estimate_tokens("") == 0
    assert estimate_tokens_many([]) == 0


def test_chinese_costs_one_token_per_char_plus_overhead() -> None:
    assert estimate_tokens("你好") == 3  # 2 宽字符 + 1 开销
    assert count_wide("你好abc") == 2


def test_ascii_is_estimated_at_three_chars_per_token() -> None:
    # 4 个 ASCII: ceil(4/3)=2, +1 开销 = 3
    assert estimate_tokens("abcd") == 3
    assert estimate_tokens("abc") == 2


def test_estimate_is_never_below_a_naive_four_chars_per_token() -> None:
    text = "The quick brown fox jumps over the lazy dog."
    assert estimate_tokens(text) >= len(text) / 4


def test_estimate_is_monotonic() -> None:
    short, long = estimate_tokens("一段话"), estimate_tokens("一段话" * 10)
    assert long > short


def test_many_matches_sum_of_individual() -> None:
    parts = ["第一段", "second part", "第三段"]
    assert estimate_tokens_many(parts) == sum(estimate_tokens(p) for p in parts)
