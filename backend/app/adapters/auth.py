"""默认 AuthProvider：单用户口令 + 签名会话令牌。"""

from __future__ import annotations

from app.adapters.base import AuthProvider, LoginOutcome
from app.core.security import AccessControl, Principal


class PasswordAuthProvider(AuthProvider):
    def __init__(self, access: AccessControl) -> None:
        self._access = access

    def authenticate(self, password: str, client_key: str) -> LoginOutcome:
        ok, token, retry_after = self._access.login(password, client_key)
        return LoginOutcome(ok=ok, token=token, retry_after=retry_after)

    def verify_token(self, token: str | None) -> Principal | None:
        return self._access.verify_token(token)

    def is_locked(self, client_key: str) -> int | None:
        return self._access.is_locked(client_key)

    def logout(self, client_key: str) -> None:
        self._access.logout(client_key)
