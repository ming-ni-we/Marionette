"""M2 HTTP 级验收：新端点已替换 501、鉴权门生效、本地埋点端点可落盘。

仅覆盖**不依赖数据库**的可断言行为：
  - 新增/改造端点未登录一律 401（AC-02 一致口径）
  - POST /events 无 DB 依赖：登录后 202 且落本地 JSONL
"""

from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

ACCESS_PASSWORD = os.environ["ACCESS_PASSWORD"]


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _login(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/login", json={"password": ACCESS_PASSWORD})
    assert resp.status_code == 200


def test_new_endpoints_require_auth(client: TestClient) -> None:
    assert client.post("/api/v1/images/jobs", json={"prompt": "x"}).status_code == 401
    assert client.get("/api/v1/images/jobs/00000000-0000-0000-0000-000000000000").status_code == 401
    assert client.post("/api/v1/events", json={"name": "x"}).status_code == 401
    assert client.get("/api/v1/diagnostics/export").status_code == 401


def test_events_records_locally(client: TestClient, tmp_path, monkeypatch) -> None:
    # 把埋点目录指向临时路径，避免污染工作区
    import app.services.telemetry as telemetry_mod

    monkeypatch.setattr(telemetry_mod, "telemetry_dir", lambda: tmp_path)

    _login(client)
    resp = client.post(
        "/api/v1/events",
        json={"name": "session_created", "properties": {"card_id": "abc"}},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["name"] == "session_created"

    # 已落本地 JSONL（不上报云端）
    lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(lines[-1])["name"] == "session_created"
