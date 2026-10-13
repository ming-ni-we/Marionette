"""Worlds + 剧情会话 API 集成测试（真实 PostgreSQL，需 MARIONETTE_INTEGRATION=1）。

覆盖 S9 端点：
  - `GET/POST /worlds`、`GET/PATCH/DELETE /worlds/{id}` 的正常路径与 404
  - `POST /sessions` 带 `world_id` → spec=story_session；不带 → rpg_session（零回归）
  - `GET /sessions/{id}/story`（剧情状态恢复）
  - `GET /sessions/{id}/actions`（补拉建议；1v1 返回空列表）
  - 枚举一致性：信封结构 / 鉴权

运行方式（api 容器内）：
    docker compose exec -e MARIONETTE_INTEGRATION=1 python -m pytest tests/integration/test_story_api.py -q
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

WORLD_BODY: dict[str, Any] = {
    "spec": "rpg_world",
    "spec_version": "1.0",
    "title": "雨巷旧案",
    "setting": {
        "summary": "1935 年的上海，雨连着下了半个月。",
        "era": "民国",
        "tone": "阴冷、克制",
        "locations": ["老弄堂"],
        "rules": ["没人愿意谈起那桩案子"],
    },
    "factions": [{"id": "f1", "name": "巡捕房", "stance": "中立", "description": ""}],
    "cast": [
        {"id": "su_wan", "name": "苏晚", "role": "主角", "voice": "克制、短句",
         "goals": ["查明旧案"], "description": ""},
        {"id": "lin_jiu", "name": "林九", "role": "配角", "voice": "油滑",
         "goals": [], "description": ""},
    ],
    "relations": [{"from": "su_wan", "to": "lin_jiu", "kind": "旧识", "tension": 0.6, "note": ""}],
    "outline": {
        "main_goal": "查明旧案",
        "nodes": [{"id": "n-003", "title": "旧案重启", "brief": "", "trigger": "出示账册"}],
        "endings": ["真相大白"],
    },
    "opening": "雨敲着铁皮棚。",
    "extensions": {},
    "tags": ["民国"],
}


@pytest.fixture
def world_factory(client: TestClient) -> Callable[..., dict[str, Any]]:
    def factory(title: str = "雨巷旧案", **over: Any) -> dict[str, Any]:
        body = {**WORLD_BODY, "title": title}
        body.update(over)
        resp = client.post("/api/v1/worlds", json=body)
        assert resp.status_code == 201, resp.text
        return resp.json()["data"]

    return factory


@pytest.fixture
def preset_id(client: TestClient) -> str:
    """取一个可用预设（新建一张最小预设，避免依赖种子数据）。"""
    resp = client.post(
        "/api/v1/presets",
        json={
            "spec": "rpg_preset",
            "spec_version": "1.0",
            "data": {
                "name": "测试预设",
                "prompt_template": {"system": "你是 {{char}}", "placeholders": {}},
                "context_budget": {"max_context_tokens": 2048, "reserve_for_output": 256},
            },
        },
    )
    if resp.status_code == 201:
        return resp.json()["data"]["id"]
    # 已存在则从列表取第一个
    listed = client.get("/api/v1/presets", params={"limit": 1})
    assert listed.status_code == 200, listed.text
    items = listed.json()["data"]["items"]
    assert items, "需要至少一个预设"
    return items[0]["id"]


# --------------------------------------------------------------------------- #
# Worlds CRUD
# --------------------------------------------------------------------------- #
class TestWorldsApi:
    def test_create_and_get(self, client: TestClient, world_factory: Callable[..., dict]) -> None:
        created = world_factory()
        assert created["title"] == "雨巷旧案"
        assert len(created["cast"]) == 2
        assert created["tags"] == ["民国"]

        got = client.get(f"/api/v1/worlds/{created['id']}")
        assert got.status_code == 200
        assert got.json()["data"]["title"] == "雨巷旧案"

    def test_list(self, client: TestClient, world_factory: Callable[..., dict]) -> None:
        world_factory(title="世界甲")
        resp = client.get("/api/v1/worlds")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body["data"]
        # 分页字段是平铺的（total/page/limit/hasMore），不是嵌套的 meta 信封。
        assert {"total", "page", "limit", "hasMore"} <= set(body["data"])

    def test_list_query_filter(self, client: TestClient, world_factory: Callable[..., dict]) -> None:
        world_factory(title="雨巷旧案")
        world_factory(title="雪原孤舟")
        resp = client.get("/api/v1/worlds", params={"q": "雨巷"})
        assert resp.status_code == 200
        titles = [i["title"] for i in resp.json()["data"]["items"]]
        assert "雨巷旧案" in titles
        assert "雪原孤舟" not in titles

    def test_patch(self, client: TestClient, world_factory: Callable[..., dict]) -> None:
        created = world_factory()
        resp = client.patch(
            f"/api/v1/worlds/{created['id']}",
            json={"opening": "改了开场。", "tags": ["新标签"]},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["opening"] == "改了开场。"
        assert data["tags"] == ["新标签"]
        assert data["title"] == "雨巷旧案"  # 未传保留

    def test_delete(self, client: TestClient, world_factory: Callable[..., dict]) -> None:
        created = world_factory()
        resp = client.delete(f"/api/v1/worlds/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted"] is True
        assert client.get(f"/api/v1/worlds/{created['id']}").status_code == 404

    def test_get_missing_404(self, client: TestClient) -> None:
        assert client.get("/api/v1/worlds/00000000-0000-0000-0000-000000000000").status_code == 404

    def test_patch_missing_404(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/v1/worlds/00000000-0000-0000-0000-000000000000", json={"title": "x"}
        )
        assert resp.status_code == 404

    def test_create_validation_error(self, client: TestClient) -> None:
        """title 为空串违反 min_length=1 → 400（本项目统一把校验错映射为 400）。"""
        resp = client.post("/api/v1/worlds", json={**WORLD_BODY, "title": ""})
        assert resp.status_code == 400


# --------------------------------------------------------------------------- #
# 剧情会话创建
# --------------------------------------------------------------------------- #
class TestStorySessionApi:
    def test_create_without_world_stays_rpg(
        self, client: TestClient, card_factory: Callable[..., dict], preset_id: str
    ) -> None:
        card = card_factory("林晓")
        resp = client.post(
            "/api/v1/sessions",
            json={"character_card_id": card["id"], "preset_id": preset_id},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["spec"] == "rpg_session"
        assert data["world_id"] is None

    def test_create_with_world_is_story(
        self,
        client: TestClient,
        card_factory: Callable[..., dict],
        preset_id: str,
        world_factory: Callable[..., dict],
    ) -> None:
        card = card_factory("苏晚")
        world = world_factory()
        resp = client.post(
            "/api/v1/sessions",
            json={
                "character_card_id": card["id"],
                "preset_id": preset_id,
                "world_id": world["id"],
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["spec"] == "story_session"
        assert data["world_id"] == world["id"]
        # 序幕：至少一条 opening 消息
        assert data["messages"], "剧情会话必须有序幕"
        assert all(m["meta"]["beat_role"] == "opening" for m in data["messages"])

    def test_create_story_response_is_fully_serialized(
        self,
        client: TestClient,
        card_factory: Callable[..., dict],
        preset_id: str,
        world_factory: Callable[..., dict],
    ) -> None:
        """回归：创建剧情会话的响应必须能完整序列化，不得 500。

        历史缺陷：`create_story_session` 在落完序幕 `flush()` 后直接 `serialize(row)`，
        而 `flush()` 会把已加载属性标记为 expired；`serialize` 读 `updated_at` 时在
        async greenlet 之外触发懒加载 IO，抛 `MissingGreenlet` → 线上 POST /sessions
        带 world_id 直接 500（1v1 分支因有 refresh 而不受影响）。

        此测试必须有真实 PostgreSQL 才会执行（见模块 docstring），
        内存夹具无法覆盖 async 会话生命周期，这正是该 bug 长期未被发现的原因。
        """
        card = card_factory("林晓")
        world = world_factory(title="序列化回归世界")
        resp = client.post(
            "/api/v1/sessions",
            json={
                "character_card_id": card["id"],
                "preset_id": preset_id,
                "world_id": world["id"],
            },
        )
        assert resp.status_code == 201, f"创建剧情会话必须成功，实际: {resp.status_code} {resp.text}"
        data = resp.json()["data"]
        # 序列化完整性：这几个字段都来自 flush 后可能 expired 的列
        for key in ("id", "created_at", "updated_at", "title", "state_machine", "scene"):
            assert data.get(key) is not None, f"字段 {key} 未被正确序列化"
        assert data["scene"]["mood"] == "阴冷、克制"
        assert data["scene"]["present"] == ["su_wan", "lin_jiu"]

    def test_fork_session_response_is_fully_serialized(
        self,
        client: TestClient,
        card_factory: Callable[..., dict],
        preset_id: str,
    ) -> None:
        """回归：fork 会话同样在 flush() 后 serialize()，必须已补 refresh。

        与 `create_story_session` 同类缺陷（同一文件、同一模式）。
        """
        card = card_factory("林九")
        created = client.post(
            "/api/v1/sessions",
            json={"character_card_id": card["id"], "preset_id": preset_id},
        )
        assert created.status_code == 201, created.text
        sid = created.json()["data"]["id"]

        resp = client.post(f"/api/v1/sessions/{sid}/fork", json={})
        assert resp.status_code in (200, 201), f"fork 必须成功，实际: {resp.status_code} {resp.text}"
        data = resp.json()["data"]
        assert data.get("id") and data.get("created_at") and data.get("updated_at")

    def test_create_with_missing_world_404(
        self, client: TestClient, card_factory: Callable[..., dict], preset_id: str
    ) -> None:
        card = card_factory("林晓")
        resp = client.post(
            "/api/v1/sessions",
            json={
                "character_card_id": card["id"],
                "preset_id": preset_id,
                "world_id": "00000000-0000-0000-0000-000000000000",
            },
        )
        assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# 剧情状态 / 行动建议端点
# --------------------------------------------------------------------------- #
class TestStoryStateApi:
    def test_story_endpoint_for_story_session(
        self,
        client: TestClient,
        card_factory: Callable[..., dict],
        preset_id: str,
        world_factory: Callable[..., dict],
    ) -> None:
        card = card_factory("苏晚")
        world = world_factory()
        session = client.post(
            "/api/v1/sessions",
            json={"character_card_id": card["id"], "preset_id": preset_id,
                  "world_id": world["id"]},
        ).json()["data"]

        resp = client.get(f"/api/v1/sessions/{session['id']}/story")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["is_story"] is True
        assert data["spec"] == "story_session"
        assert data["world_id"] == world["id"]
        assert [c["id"] for c in data["cast"]] == ["su_wan", "lin_jiu"]
        assert data["relations"][0]["kind"] == "旧识"
        assert "beat_index" in data["story"]
        assert data["scene"]["present"] == ["su_wan", "lin_jiu"]

    def test_story_endpoint_for_rpg_session(
        self, client: TestClient, card_factory: Callable[..., dict], preset_id: str
    ) -> None:
        """1v1 会话调用 /story 不报错，返回 is_story=False。"""
        card = card_factory("林晓")
        session = client.post(
            "/api/v1/sessions",
            json={"character_card_id": card["id"], "preset_id": preset_id},
        ).json()["data"]
        resp = client.get(f"/api/v1/sessions/{session['id']}/story")
        assert resp.status_code == 200
        assert resp.json()["data"]["is_story"] is False

    def test_actions_endpoint_rpg_returns_empty(
        self, client: TestClient, card_factory: Callable[..., dict], preset_id: str
    ) -> None:
        card = card_factory("林晓")
        session = client.post(
            "/api/v1/sessions",
            json={"character_card_id": card["id"], "preset_id": preset_id},
        ).json()["data"]
        resp = client.get(f"/api/v1/sessions/{session['id']}/actions")
        assert resp.status_code == 200
        assert resp.json()["data"]["actions"] == []

    def test_actions_endpoint_story_never_500(
        self,
        client: TestClient,
        card_factory: Callable[..., dict],
        preset_id: str,
        world_factory: Callable[..., dict],
    ) -> None:
        """无 LLM 上游时也应返回结构合法的空/兜底列表，不得 500。"""
        card = card_factory("苏晚")
        world = world_factory()
        session = client.post(
            "/api/v1/sessions",
            json={"character_card_id": card["id"], "preset_id": preset_id,
                  "world_id": world["id"]},
        ).json()["data"]
        resp = client.get(f"/api/v1/sessions/{session['id']}/actions")
        assert resp.status_code == 200, resp.text
        assert isinstance(resp.json()["data"]["actions"], list)

    def test_story_endpoint_missing_session_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/sessions/00000000-0000-0000-0000-000000000000/story")
        assert resp.status_code == 404
