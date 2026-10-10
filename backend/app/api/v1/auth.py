"""Auth 路由：单用户口令登录 / 登出 / 会话校验（公开）。

对应 AC-02 / AC-03。不做注册、不做密码找回、不建用户表（SPEC §4.3）。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request, Response

from app.adapters.registry import get_access_control, get_auth_provider
from app.api.v1.deps import client_key
from app.core.config import get_settings
from app.core.errors import AuthFailedError, RateLimitedError
from app.schemas.auth import LoginRequest, LoginResponse, SessionStatusResponse
from app.schemas.common import Envelope

router = APIRouter(tags=["Auth"])


def _set_session_cookie(response: Response, token: str) -> datetime:
    s = get_settings()
    expires_at = datetime.now(UTC) + timedelta(seconds=s.session_ttl_seconds)
    response.set_cookie(
        key=s.session_cookie_name,
        value=token,
        max_age=s.session_ttl_seconds,
        httponly=True,  # 防 XSS 读取
        secure=s.session_cookie_secure,  # 生产 HTTPS 下必须为 True
        samesite="lax",
        path="/",
    )
    return expires_at


@router.post(
    "/auth/login",
    response_model=Envelope[LoginResponse],
    summary="单用户口令登录",
    description="校验通过后签发 HttpOnly 签名会话令牌；连续 5 次错误口令触发速率限制（429）。",
)
async def login(
    payload: LoginRequest, request: Request, response: Response
) -> Envelope[LoginResponse]:
    s = get_settings()
    key = client_key(request)
    ac = get_access_control()

    # 1) 失败锁定（连续错误口令）
    locked = ac.is_locked(key)
    if locked is not None:
        raise RateLimitedError(
            f"错误口令次数过多，请 {locked} 秒后再试。",
            retry_after=locked,
            data={"retry_after": locked},
        )

    # 2) 接口级总量限流（防暴力枚举，与失败计数独立）
    throttle = ac.login_attempts.retry_after(key)
    if throttle is not None:
        raise RateLimitedError(
            f"登录请求过于频繁，请 {throttle} 秒后再试。",
            retry_after=throttle,
            data={"retry_after": throttle},
        )
    ac.login_attempts.hit(key)

    # 3) 校验口令
    outcome = get_auth_provider().authenticate(payload.password, key)
    if not outcome.ok or not outcome.token:
        if outcome.retry_after:
            raise RateLimitedError(
                f"连续 {s.access_max_failed} 次口令错误，已限制登录 {outcome.retry_after} 秒。",
                retry_after=outcome.retry_after,
                data={"retry_after": outcome.retry_after},
            )
        raise AuthFailedError("访问口令不正确，请重试。")

    expires_at = _set_session_cookie(response, outcome.token)
    return Envelope(
        data=LoginResponse(authenticated=True, expires_at=expires_at, message="登录成功。")
    )


@router.post(
    "/auth/logout",
    response_model=Envelope[dict],
    summary="登出",
    description="清除会话 Cookie。令牌为无状态自签，登出即客户端丢弃令牌。",
)
async def logout(request: Request, response: Response) -> Envelope[dict]:
    s = get_settings()
    get_auth_provider().logout(client_key(request))
    response.delete_cookie(key=s.session_cookie_name, path="/")
    return Envelope(data={"logged_out": True})


@router.get(
    "/auth/session",
    response_model=Envelope[SessionStatusResponse],
    summary="校验当前会话",
    description="公开端点：返回当前是否已认证，供前端判断是否需要跳到登录页。",
)
async def session_status(request: Request) -> Envelope[SessionStatusResponse]:
    s = get_settings()
    token = request.cookies.get(s.session_cookie_name)
    principal = get_auth_provider().verify_token(token)
    if principal is None:
        return Envelope(data=SessionStatusResponse(authenticated=False))
    expires_at = datetime.now(UTC) + timedelta(seconds=s.session_ttl_seconds)
    return Envelope(
        data=SessionStatusResponse(
            authenticated=True, subject=principal.subject, expires_at=expires_at
        )
    )
