"""集成测试：内容 CRUD 与 AC-13（关键词/标签过滤 + 分页排序稳定）。"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient


# --------------------------------------------------------------------------- #
# D. 资产查询：无数据必须是空分页而不是 500
# --------------------------------------------------------------------------- #
def test_assets_empty_page_is_not_500(client: TestClient) -> None:
    resp = client.get("/api/v1/assets")
    assert resp.status_code == 200, resp.text
    page = resp.json()["data"]
    assert page["total"] == 0
    assert page["items"] == []
    assert page["hasMore"] is False


def test_card_assets_empty_page(client: TestClient, card_factory: Callable[..., dict]) -> None:
    card = card_factory("空资产角色")
    resp = client.get(f"/api/v1/cards/{card['id']}/assets")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["items"] == []


# --------------------------------------------------------------------------- #
# A. CRUD + 错误码
# --------------------------------------------------------------------------- #
def test_card_crud_and_patch_merges(client: TestClient, card_factory: Callable[..., dict]) -> None:
    card = card_factory("CRUD角色", personality="安静", tags=["日常"])
    card_id = card["id"]
    assert client.get(f"/api/v1/cards/{card_id}").status_code == 200

    patched = client.patch(f"/api/v1/cards/{card_id}", json={"data": {"scenario": "深夜的便利店"}})
    assert patched.status_code == 200, patched.text
    data = patched.json()["data"]["data"]
    assert data["scenario"] == "深夜的便利店"
    assert data["personality"] == "安静"  # PATCH 深合并：未提交字段保持原值
    assert data["tags"] == ["日常"]

    removed = client.delete(f"/api/v1/cards/{card_id}")
    assert removed.status_code == 200
    assert removed.json()["data"]["deleted"] is True
    assert client.get(f"/api/v1/cards/{card_id}").status_code == 404


def test_invalid_uuid_returns_400_not_500(client: TestClient) -> None:
    resp = client.get("/api/v1/cards/not-a-uuid")
    assert resp.status_code == 400, resp.text
    assert resp.json()["code"] == 4000


def test_missing_resource_returns_404(client: TestClient) -> None:
    resp = client.get(f"/api/v1/cards/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error_class"] == "model_not_found"


def test_limit_out_of_range_returns_400(client: TestClient) -> None:
    resp = client.get("/api/v1/cards", params={"limit": 999})
    assert resp.status_code == 400
    assert resp.json()["code"] == 4000


def test_create_card_rejects_future_spec_version(
    client: TestClient, card_payload: Callable[..., dict]
) -> None:
    payload = card_payload("未来版本角色")
    payload["spec_version"] = "9.9"
    resp = client.post("/api/v1/cards", json=payload)
    assert resp.status_code == 400
    assert "spec_version" in resp.json()["message"]


# --------------------------------------------------------------------------- #
# AC-13：关键词/标签过滤 + 分页间排序稳定
# --------------------------------------------------------------------------- #
SAMPLE_NAMES = ["栖夜书店", "栖夜咖啡馆", "栖夜车站", "栖夜天台", "栖夜码头", "栖夜小巷", "栖夜公园"]


def test_ac13_keyword_filter_and_stable_pagination(
    client: TestClient, card_factory: Callable[..., dict]
) -> None:
    for name in SAMPLE_NAMES:
        card_factory(name, tags=["分页样本"])

    filtered = client.get("/api/v1/cards", params={"q": "栖夜", "tags": "分页样本", "limit": 100})
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["data"]["total"] == len(SAMPLE_NAMES)

    whole = client.get(
        "/api/v1/cards", params={"q": "栖夜", "sort": "name", "order": "asc", "limit": 100}
    ).json()["data"]
    whole_ids = [item["id"] for item in whole["items"]]
    assert [i["data"]["name"] for i in whole["items"]] == sorted(SAMPLE_NAMES)

    # 逐页拼接必须与全量完全一致（排序稳定 = 分页间不重不漏）
    paged_ids: list[str] = []
    for page in (1, 2, 3):
        resp = client.get(
            "/api/v1/cards",
            params={"q": "栖夜", "sort": "name", "order": "asc", "page": page, "limit": 3},
        )
        assert resp.status_code == 200, resp.text
        paged_ids.extend(item["id"] for item in resp.json()["data"]["items"])
    assert len(paged_ids) == len(set(paged_ids)), "分页出现重复条目，排序不稳定"
    assert paged_ids == whole_ids, "分页拼接结果与全量排序不一致"


def test_ac13_desc_order_is_also_stable(
    client: TestClient, card_factory: Callable[..., dict]
) -> None:
    for name in ("倒序甲", "倒序乙", "倒序丙"):
        card_factory(name, tags=["倒序样本"])
    page1 = client.get(
        "/api/v1/cards",
        params={"tags": "倒序样本", "sort": "name", "order": "desc", "page": 1, "limit": 1},
    ).json()["data"]
    page2 = client.get(
        "/api/v1/cards",
        params={"tags": "倒序样本", "sort": "name", "order": "desc", "page": 2, "limit": 1},
    ).json()["data"]
    assert page1["total"] == 3
    assert page1["items"][0]["data"]["name"] == "倒序甲"
    assert page2["items"][0]["data"]["name"] == "倒序乙"


def test_ac13_multiple_tags_are_anded(client: TestClient, card_factory: Callable[..., dict]) -> None:
    card_factory("双标签角色", tags=["标签甲", "标签乙"])
    card_factory("单标签角色", tags=["标签甲"])

    both = client.get("/api/v1/cards", params=[("tags", "标签甲"), ("tags", "标签乙")]).json()["data"]
    assert [i["data"]["name"] for i in both["items"]] == ["双标签角色"]

    one = client.get("/api/v1/cards", params=[("tags", "标签甲")]).json()["data"]
    assert {i["data"]["name"] for i in one["items"]} == {"双标签角色", "单标签角色"}


def test_ac13_no_match_returns_empty_page(client: TestClient) -> None:
    resp = client.get("/api/v1/cards", params={"q": "绝对不存在的关键词zzz"})
    assert resp.status_code == 200
    assert resp.json()["data"]["items"] == []
    assert resp.json()["data"]["total"] == 0


def test_ac13_chinese_substring_search_hits_description(
    client: TestClient, card_payload: Callable[..., dict]
) -> None:
    payload = card_payload("描述检索角色", description="他总在凌晨去城南的便利店买热牛奶。")
    assert client.post("/api/v1/cards", json=payload).status_code == 201
    resp = client.get("/api/v1/cards", params={"q": "热牛奶"})
    assert resp.status_code == 200
    names = [i["data"]["name"] for i in resp.json()["data"]["items"]]
    assert "描述检索角色" in names
