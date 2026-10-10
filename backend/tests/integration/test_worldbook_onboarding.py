"""集成测试：AC-08（世界书命中测试三态）、首启向导示例、预设检索。"""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

THREE_STATE_BOOK = {
    "spec": "rpg_worldbook",
    "spec_version": "1.0",
    "data": {
        "name": "三态验证世界书",
        "token_budget": 20,
        "scan_depth": 4,
        "entries": [
            {"id": "c", "keys": [], "content": "常驻设定", "constant": True, "priority": 100},
            {"id": "h", "keys": ["咖啡馆"], "content": "命中且在预算内", "priority": 50},
            {"id": "m", "keys": ["月球"], "content": "不该命中", "priority": 20},
            {
                "id": "e",
                "keys": ["咖啡"],
                "content": "命中了但因为优先级最低会被挤出预算所以不进入最终注入上下文",
                "priority": 1,
            },
        ],
    },
}


def test_ac08_worldbook_test_endpoint_three_states(client: TestClient) -> None:
    created = client.post("/api/v1/worldbooks", json=THREE_STATE_BOOK)
    assert created.status_code == 201, created.text
    book_id = created.json()["data"]["id"]

    resp = client.post(
        f"/api/v1/worldbooks/{book_id}/test",
        json={"sample_text": "我推门进了咖啡馆，外面开始下雨。"},
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["data"]
    by_id = {e["entry_id"]: e for e in result["entries"]}

    assert by_id["m"]["matched"] is False  # 态 1：未命中
    assert by_id["c"]["matched"] and by_id["c"]["in_budget"]  # 态 2：常驻且在预算内
    assert by_id["h"]["matched"] and by_id["h"]["in_budget"]  # 态 2：命中且在预算内
    assert by_id["h"]["match_type"] == "keyword"
    assert by_id["h"]["matched_key"] == "咖啡馆"
    assert by_id["e"]["matched"] and not by_id["e"]["in_budget"]  # 态 3：命中但被挤出

    assert result["matched_count"] == 3
    assert result["in_budget_count"] == 2
    assert result["evicted_count"] == 1
    assert result["token_budget"] == 20
    for entry in result["entries"]:
        for field in ("matched", "match_type", "in_budget", "token_count", "final_position"):
            assert field in entry


def test_worldbook_test_does_not_persist_changes(client: TestClient) -> None:
    created = client.post("/api/v1/worldbooks", json=THREE_STATE_BOOK)
    book_id = created.json()["data"]["id"]
    before = client.get(f"/api/v1/worldbooks/{book_id}").json()["data"]

    client.post(f"/api/v1/worldbooks/{book_id}/test", json={"sample_text": "咖啡馆"})
    after = client.get(f"/api/v1/worldbooks/{book_id}").json()["data"]
    assert before == after, "命中测试不应落库"


def test_worldbook_crud_and_search(client: TestClient) -> None:
    book = {
        "spec": "rpg_worldbook",
        "spec_version": "1.0",
        "data": {
            "name": "检索用世界书",
            "description": "关于海边小镇的设定。",
            "entries": [{"keys": ["灯塔"], "content": "镇东有一座白色灯塔。"}],
            "extensions": {"rpg": {"tags": ["海边"]}},
        },
    }
    created = client.post("/api/v1/worldbooks", json=book)
    assert created.status_code == 201, created.text
    book_id = created.json()["data"]["id"]

    # 书名命中
    assert client.get("/api/v1/worldbooks", params={"q": "检索用"}).json()["data"]["total"] >= 1
    # 条目内容命中（entries 文本参与检索）
    hits = client.get("/api/v1/worldbooks", params={"q": "灯塔"}).json()["data"]
    assert "检索用世界书" in [i["data"]["name"] for i in hits["items"]]
    # 标签命中（data.extensions.rpg.tags 反规范化到 tags 列）
    tagged = client.get("/api/v1/worldbooks", params={"tags": "海边"}).json()["data"]
    assert "检索用世界书" in [i["data"]["name"] for i in tagged["items"]]

    patched = client.patch(
        f"/api/v1/worldbooks/{book_id}", json={"data": {"description": "改为关于码头。"}}
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["data"]["description"] == "改为关于码头。"
    assert patched.json()["data"]["data"]["entries"][0]["keys"] == ["灯塔"]
    assert client.delete(f"/api/v1/worldbooks/{book_id}").status_code == 200


def test_onboarding_samples_install(client: TestClient) -> None:
    resp = client.post("/api/v1/onboarding/samples")
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert 3 <= len(data["card_ids"]) <= 5, "首启向导要求 3–5 张示例卡"
    assert len(data["worldbook_ids"]) >= 1
    assert len(data["preset_ids"]) >= 1

    cards = client.get("/api/v1/cards", params={"limit": 100}).json()["data"]
    assert cards["total"] >= len(data["card_ids"])
    assert client.get("/api/v1/presets").json()["data"]["total"] >= 1
    sample = next(i for i in cards["items"] if i["id"] in data["card_ids"])
    assert sample["data"]["extensions"]["rpg"]["default_worldbook_ids"]
    assert sample["data"]["first_mes"]


def test_presets_crud_and_search(client: TestClient) -> None:
    preset = {
        "spec": "rpg_preset",
        "spec_version": "1.0",
        "data": {
            "name": "集成测试预设",
            "description": "用于集成测试的预设描述。",
            "prompt_template": {"system": "你是 {{char}}。"},
        },
    }
    created = client.post("/api/v1/presets", json=preset)
    assert created.status_code == 201, created.text

    listed = client.get("/api/v1/presets", params={"q": "集成测试"}).json()["data"]
    assert listed["total"] >= 1
    assert "集成测试预设" in [i["data"]["name"] for i in listed["items"]]

    pid = created.json()["data"]["id"]
    assert client.get(f"/api/v1/presets/{pid}").status_code == 200
    assert client.delete(f"/api/v1/presets/{pid}").status_code == 200


def test_uploaded_asset_appears_in_card_assets(
    client: TestClient, card_factory: Callable[..., dict], png_card: Callable[[dict], bytes]
) -> None:
    card = card_factory("图集角色")
    payload = png_card({"spec": "rpg_card", "data": {"name": "x", "first_mes": "y"}})
    uploaded = client.post(
        "/api/v1/assets",
        files={"file": ("gallery.png", payload, "image/png")},
        data={"kind": "gallery", "card_id": card["id"], "tags": "主视图,日常"},
    )
    assert uploaded.status_code == 201, uploaded.text
    asset = uploaded.json()["data"]
    assert asset["kind"] == "gallery"
    assert asset["tags"] == ["主视图", "日常"]

    listed = client.get(f"/api/v1/cards/{card['id']}/assets").json()["data"]
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == asset["id"]

    filtered = client.get("/api/v1/assets", params={"q": "gallery", "kind": "gallery"}).json()["data"]
    assert filtered["total"] >= 1

    assert client.delete(f"/api/v1/assets/{asset['id']}").status_code == 200
    assert client.get(f"/api/v1/assets/{asset['id']}").status_code == 404


def test_upload_asset_with_bad_kind_returns_400(
    client: TestClient, png_card: Callable[[dict], bytes]
) -> None:
    resp = client.post(
        "/api/v1/assets",
        files={"file": ("x.png", png_card({"name": "x"}), "image/png")},
        data={"kind": "not_a_kind"},
    )
    assert resp.status_code == 400
    assert "资产类型" in resp.json()["message"]
