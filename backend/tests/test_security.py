"""AC-03 单元验证：口令校验 + 连续 5 次错误触发限流 + 令牌签验。

不依赖数据库，可用纯 pytest 运行。
"""

from __future__ import annotations

from app.core.security import AccessControl, SlidingWindowLimiter, verify_password


def test_verify_password_exact_match() -> None:
    assert verify_password("s3cret-passphrase", "s3cret-passphrase") is True
    assert verify_password("wrong", "s3cret-passphrase") is False
    assert verify_password("anything", "") is False


def test_sliding_window_limiter_blocks_at_limit() -> None:
    limiter = SlidingWindowLimiter(limit=5, window_seconds=900)
    for _ in range(4):
        assert limiter.hit("1.2.3.4") is False
    assert limiter.hit("1.2.3.4") is True  # 第 5 次达到上限
    assert limiter.retry_after("1.2.3.4") is not None
    # 其它 IP 不受影响
    assert limiter.retry_after("5.6.7.8") is None


def _make_access() -> AccessControl:
    return AccessControl(
        password="correct-horse",
        secret_key="unit-test-secret",
        ttl_seconds=3600,
        max_failed=5,
        lock_window_seconds=900,
    )


def test_login_success_issues_token() -> None:
    ac = _make_access()
    ok, token, retry = ac.login("correct-horse", "10.0.0.1")
    assert ok is True
    assert token
    assert retry is None
    principal = ac.verify_token(token)
    assert principal is not None
    assert principal.subject == "local"


def test_five_wrong_passwords_trigger_rate_limit() -> None:
    ac = _make_access()
    retry = None
    for _ in range(5):
        ok, token, retry = ac.login("nope", "10.0.0.2")
        assert ok is False
        assert token is None
    assert retry is not None  # 第 5 次触发限流
    # 锁定后即使口令正确也被拒
    ok, token, retry = ac.login("correct-horse", "10.0.0.2")
    assert ok is False
    assert retry is not None


def test_success_resets_failure_counter() -> None:
    ac = _make_access()
    for _ in range(3):
        ac.login("nope", "10.0.0.3")
    ok, _, _ = ac.login("correct-horse", "10.0.0.3")
    assert ok is True
    assert ac.is_locked("10.0.0.3") is None


def test_tampered_token_rejected() -> None:
    ac = _make_access()
    assert ac.verify_token("not-a-real-token") is None
    assert ac.verify_token(None) is None
