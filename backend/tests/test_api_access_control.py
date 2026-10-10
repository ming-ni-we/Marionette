"""HTTP 级验收：AC-02（未带令牌 401）与 AC-03（登录签发 HttpOnly 令牌 + 5 次错误限流）。

不依赖数据库：数据库不可达时 /system/selfcheck 仍返回 200（自检本身报告 db=fail）。

口令来自 tests/conftest.py 注入的环境变量（单一来源）。**不要在这里硬编码**：
曾经硬编码 + setdefault 的写法在服务器上会被部署口令顶掉，导致本文件与集成夹具
用两套凭证，登录莫名 401。
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.adapters.registry import get_access_control
from app.main import app

# 由 tests/conftest.py 写入；此处只读取，保证与集成夹具同源
ACCESS_PASSWORD = os.environ["ACCESS_PASSWORD"]


@pytest.fixture(autouse=True)
def _reset_limits():
    ac = get_access_control()
    ac.failed_attempts.clear()
    ac.login_attempts.clear()
    yield
    ac.failed_attempts.clear()
    ac.login_attempts.clear()


@pytest.fixture
def client():
    # raise_server_exceptions=False：本项目的 500 也走统一信封（全局异常处理器），
    # 关掉重抛才能断言"500 而不是 401"这类真实行为。
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_unauthenticated_returns_401(client: TestClient) -> None:
    resp = client.get("/api/v1/cards")
    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == 4010
    assert body["error_class"] == "auth_failed"
    assert body["data"] is None


def test_protected_surface_all_401_without_token(client: TestClient) -> None:
    for path in ("/api/v1/worldbooks", "/api/v1/sessions", "/api/v1/assets", "/api/v1/config/llm"):
        assert client.get(path).status_code == 401, path


def test_health_endpoints_are_public(client: TestClient) -> None:
    info = client.get("/api/v1/system/info")
    assert info.status_code == 200
    selfcheck = client.get("/api/v1/system/selfcheck")
    assert selfcheck.status_code == 200  # 即便 db 不可达也返回 200，自检体报告状态
    assert "db" in selfcheck.json()["data"]


def test_login_success_sets_httponly_cookie(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/login", json={"password": ACCESS_PASSWORD})
    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie
    assert "marionette_session" in set_cookie
    # 携带令牌后必须通过鉴权门（不再是 401）。本轮业务侧需要真实数据库，
    # 故此处只断言"鉴权已通过"，具体状态码由容器内的集成测试覆盖。
    follow = client.get("/api/v1/cards")
    assert follow.status_code != 401


def test_five_wrong_passwords_trigger_rate_limit(client: TestClient) -> None:
    for _ in range(4):
        assert client.post("/api/v1/auth/login", json={"password": "nope"}).status_code == 401
    fifth = client.post("/api/v1/auth/login", json={"password": "nope"})
    assert fifth.status_code == 429
    assert fifth.json()["error_class"] == "auth_failed"
    assert "Retry-After" in fifth.headers
    # 锁定后即使口令正确也被拒
    locked = client.post("/api/v1/auth/login", json={"password": ACCESS_PASSWORD})
    assert locked.status_code == 429


def test_invalid_param_returns_400(client: TestClient) -> None:
    client.post("/api/v1/auth/login", json={"password": ACCESS_PASSWORD})
    resp = client.get("/api/v1/cards", params={"limit": 999})
    assert resp.status_code == 400
    assert resp.json()["code"] == 4000
