"""安全原语：单用户口令校验 + HttpOnly 签名会话令牌 + 速率限制。

对应验收标准：
  AC-02  未持有有效令牌访问 /api/v1/** -> 401（由 api 层依赖强制，令牌校验在此）
  AC-03  正确口令 -> 签发 HttpOnly 会话令牌；连续 5 次错误口令 -> 触发速率限制

刻意不做的事：用户表、注册、密码找回、多角色权限。本实例仅单一用户（SPEC §4.3）。
令牌为**自签**（itsdangerous，HMAC-SHA 签名 + 过期时间），因此无需服务端会话存储；
单实例场景下这是最简单且可迁移（上云换成 JWT 只需换实现）的做法。
"""

from __future__ import annotations

import hashlib
import hmac
import time
from collections import deque
from dataclasses import dataclass
from threading import Lock

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.logging import get_logger

logger = get_logger(__name__)


# --------------------------------------------------------------------------- #
# 口令校验
# --------------------------------------------------------------------------- #
def _digest(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()


def verify_password(candidate: str, expected: str) -> bool:
    """定长比较，避免因长度不同而泄露信息。"""
    if not expected:
        return False
    return hmac.compare_digest(_digest(candidate), _digest(expected))


# --------------------------------------------------------------------------- #
# 会话令牌
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Principal:
    """已认证主体。单用户场景恒为 local。"""

    subject: str = "local"


class SessionSigner:
    def __init__(self, secret_key: str, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._serializer = URLSafeTimedSerializer(secret_key, salt="marionette.session.v1")

    def issue(self, subject: str = "local") -> str:
        return self._serializer.dumps({"sub": subject})

    def verify(self, token: str | None) -> Principal | None:
        if not token:
            return None
        try:
            payload = self._serializer.loads(token, max_age=self._ttl)
        except SignatureExpired:
            return None
        except BadSignature:
            return None
        except Exception:  # noqa: BLE001 —— 任何解析异常都视为无效令牌
            return None
        subject = payload.get("sub") if isinstance(payload, dict) else None
        if not subject:
            return None
        return Principal(subject=str(subject))


# --------------------------------------------------------------------------- #
# 速率限制（进程内滑动窗口）
# --------------------------------------------------------------------------- #
class SlidingWindowLimiter:
    """按 key 的滑动窗口计数器。

    单实例部署下进程内内存足够；若将来多副本，把实现换成 Redis 计数器即可
    （接口不变，业务代码不动）。
    """

    def __init__(self, limit: int, window_seconds: int) -> None:
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        bucket = self._hits.get(key)
        if bucket is None:
            bucket = deque()
            self._hits[key] = bucket
        cutoff = now - self._window
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        return bucket

    def retry_after(self, key: str) -> int | None:
        """若已超限返回剩余冷却秒数，否则 None。"""
        now = time.monotonic()
        with self._lock:
            bucket = self._prune(key, now)
            if len(bucket) < self._limit:
                return None
            return max(1, int(self._window - (now - bucket[0])) + 1)

    def hit(self, key: str) -> bool:
        """记录一次命中；返回记录后是否已达/超限。"""
        now = time.monotonic()
        with self._lock:
            bucket = self._prune(key, now)
            bucket.append(now)
            return len(bucket) >= self._limit

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


# --------------------------------------------------------------------------- #
# 访问控制门面
# --------------------------------------------------------------------------- #
class AccessControl:
    """把「口令比对 + 令牌签发/校验 + 失败限流」收口到一个对象。"""

    def __init__(
        self,
        *,
        password: str,
        secret_key: str,
        ttl_seconds: int,
        max_failed: int,
        lock_window_seconds: int,
    ) -> None:
        self._password = password
        self.signer = SessionSigner(secret_key, ttl_seconds)
        self.failed_attempts = SlidingWindowLimiter(max_failed, lock_window_seconds)
        # 登录接口本身的总量限流（防暴力枚举），与「失败计数」相互独立
        self.login_attempts = SlidingWindowLimiter(limit=10, window_seconds=60)

    @property
    def lock_window_seconds(self) -> int:
        return self.failed_attempts._window  # noqa: SLF001 —— 同模块内部读取

    def is_locked(self, client_key: str) -> int | None:
        return self.failed_attempts.retry_after(client_key)

    def login(self, password: str, client_key: str) -> tuple[bool, str | None, int | None]:
        """返回 (是否成功, 令牌, 剩余冷却秒数)。

        调用方需先调用 is_locked；这里仍二次校验以防竞态。
        """
        locked = self.failed_attempts.retry_after(client_key)
        if locked is not None:
            return False, None, locked
        if verify_password(password, self._password):
            self.failed_attempts.reset(client_key)
            return True, self.signer.issue(), None
        reached_limit = self.failed_attempts.hit(client_key)
        logger.warning(
            "login failed",
            extra={"client": client_key, "reached_limit": reached_limit},
        )
        if reached_limit:
            return False, None, self.failed_attempts.retry_after(client_key) or 1
        return False, None, None

    def logout(self, client_key: str) -> None:
        # 令牌是无状态自签的，登出靠清除 Cookie；这里顺手清失败计数。
        self.failed_attempts.reset(client_key)

    def verify_token(self, token: str | None) -> Principal | None:
        return self.signer.verify(token)
