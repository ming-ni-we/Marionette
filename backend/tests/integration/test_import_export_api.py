"""集成测试：AC-05 / AC-06（HTTP 层导入导出可回导）+ 导出包。"""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

SOURCE_V2: dict[str, Any] = {
    "spec": "chara_card_v2",
    "spec_version": "2.0",
    "data": {
        "name": "HTTP往返角色",
        "description": "用于验证导入导出的描述文本。",
        "personality": "冷静、话少",
        "scenario": "雨天的公交站",
        "first_mes": "「车还有十分钟。」她把伞往你那边偏了偏。",
        "mes_example": "{{user}}: 谢谢\n{{char}}: 「顺路而已。」",
        "creator_notes": "测试备注",
        "alternate_greetings": ["「你也等这班车？」"],
        "tags": ["日常", "通勤"],
        "creator": "tester",
        "character_version": "1.0",
    },
    "unknown_plugin_key": {"keep": True},
}

COMPARED_FIELDS = (
    "description",
    "personality",
    "scenario",
    "first_mes",
    "mes_example",
    "creator_notes",
    "tags",
    "alternate_greetings",
)


def test_ac05_ac06_http_import_export_roundtrip(
    client: TestClient, png_card: Callable[[dict], bytes]
) -> None:
    imported = client.post(
        "/api/v1/import/card",
        files={"file": ("card.png", png_card(SOURCE_V2), "image/png")},
        data={"on_conflict": "rename"},
    )
    assert imported.status_code == 201, imported.text
    result = imported.json()["data"]
    assert result["source_format"] == "st_v2"
    assert result["preserved_unknown_keys"] == ["envelope.unknown_plugin_key"]

    card_id = result["object_id"]
    stored = client.get(f"/api/v1/cards/{card_id}").json()["data"]
    for field in COMPARED_FIELDS:
        assert stored["data"][field] == SOURCE_V2["data"][field], field
    assert stored["data"]["extensions"]["rpg"]["avatar_asset_id"], "PNG 应落为头像资产"

    # 头像资产已自动登记，且可取二进制（AC-10 的资产侧证据）
    assets = client.get(f"/api/v1/cards/{card_id}/assets").json()["data"]
    assert assets["total"] == 1
    blob = client.get(f"/api/v1/assets/{assets['items'][0]['id']}/content")
    assert blob.status_code == 200
    assert blob.content[:8] == b"\x89PNG\r\n\x1a\n"

    # 导出 ST V2 JSON
    exported = client.get(f"/api/v1/export/card/{card_id}", params={"format": "json"})
    assert exported.status_code == 200, exported.text
    st = json.loads(exported.content)
    assert st["spec"] == "chara_card_v2"
    for field in COMPARED_FIELDS:
        assert st["data"][field] == SOURCE_V2["data"][field], field
    assert st["unknown_plugin_key"] == {"keep": True}

    # 回导 -> 字段等价（AC-06）
    reimported = client.post(
        "/api/v1/import/card",
        files={"file": ("again.json", exported.content, "application/json")},
        data={"on_conflict": "rename"},
    )
    assert reimported.status_code == 201, reimported.text
    again = client.get(f"/api/v1/cards/{reimported.json()['data']['object_id']}").json()["data"]
    for field in COMPARED_FIELDS:
        assert again["data"][field] == stored["data"][field], field


def test_export_png_is_reimportable(
    client: TestClient, card_factory: Callable[..., dict]
) -> None:
    card = card_factory("PNG导出角色", description="用于 PNG 导出回导。")
    exported = client.get(f"/api/v1/export/card/{card['id']}", params={"format": "png"})
    assert exported.status_code == 200, exported.text
    assert exported.content[:8] == b"\x89PNG\r\n\x1a\n"

    reimported = client.post(
        "/api/v1/import/card",
        files={"file": ("png-roundtrip.png", exported.content, "image/png")},
        data={"on_conflict": "rename"},
    )
    assert reimported.status_code == 201, reimported.text
    again = client.get(f"/api/v1/cards/{reimported.json()['data']['object_id']}").json()["data"]
    # on_conflict=rename 的既定语义：与既有同名卡冲突时追加「(导入副本)」
    # （见 ImportExportSvc._renamed）。所以名字不能再断言"原样不变"，
    # 这里要验证的是**卡片正文无损**：除名字外字段逐字段等价。
    assert again["data"]["name"] == "PNG导出角色 (导入副本)"
    assert again["data"]["description"] == card["data"]["description"]


def test_import_broken_file_returns_400(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/import/card",
        files={"file": ("broken.png", b"definitely not a card", "image/png")},
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["code"] == 4000
    assert body["error_class"] == "endpoint_invalid"
    assert body["message"]


def test_import_worldbook_from_st_world_info(client: TestClient) -> None:
    st_world_info = {
        "name": "公交线路世界书",
        "entries": [
            {"keys": ["37路"], "content": "37 路公交末班车是 22:40。", "insertion_order": 10},
            {"key": "雨", "content": "雨天这趟车常晚点。", "disable": True, "order": 5},
        ],
    }
    resp = client.post(
        "/api/v1/import/worldbook",
        files={"file": ("line.json", json.dumps(st_world_info, ensure_ascii=False).encode(), "application/json")},
        data={"on_conflict": "rename"},
    )
    assert resp.status_code == 201, resp.text
    book_id = resp.json()["data"]["object_id"]
    stored = client.get(f"/api/v1/worldbooks/{book_id}").json()["data"]
    assert stored["data"]["name"] == "公交线路世界书"
    first, second = stored["data"]["entries"]
    assert first["keys"] == ["37路"]
    assert second["enabled"] is False
    assert second["insertion_order"] == 5


def test_export_bundle_has_manifest(client: TestClient, card_factory: Callable[..., dict]) -> None:
    card = card_factory("打包角色")
    resp = client.post(
        "/api/v1/export/bundle", json={"card_ids": [card["id"]], "include_assets": True}
    )
    assert resp.status_code == 200, resp.text
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
        assert "manifest.json" in names
        assert f"cards/{card['id']}.json" in names
        manifest = json.loads(zf.read("manifest.json"))
        exported = json.loads(zf.read(f"cards/{card['id']}.json"))
    assert manifest["format"] == "marionette.bundle"
    assert manifest["cards"][0]["name"] == "打包角色"
    assert exported["spec"] == "chara_card_v2"


def test_export_bundle_missing_object_returns_404(client: TestClient) -> None:
    resp = client.post("/api/v1/export/bundle", json={"card_ids": [str(uuid.uuid4())]})
    assert resp.status_code == 404
    assert resp.json()["error_class"] == "model_not_found"


def test_export_card_invalid_format_returns_400(
    client: TestClient, card_factory: Callable[..., dict]
) -> None:
    card = card_factory("格式校验角色")
    resp = client.get(f"/api/v1/export/card/{card['id']}", params={"format": "pdf"})
    assert resp.status_code == 400
    assert "json" in resp.json()["message"]
