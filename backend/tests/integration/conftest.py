"""集成测试夹具（真实 PostgreSQL）。

**隔离策略**：本次运行创建一个独立的临时 schema，引擎的 `search_path` 指向它，
结束时 `DROP SCHEMA ... CASCADE`。绝不触碰生产 schema 的表。

> 说明：tests 内在**临时 schema** 里用 `Base.metadata.create_all` 建表；
> 生产建表依旧只走 Alembic（铁律不变）。这样测试既不污染生产库，也不依赖迁移执行顺序。

运行方式（api 容器内）：
    docker compose exec -e MARIONETTE_INTEGRATION=1 -e ASSETS_DIR=/tmp/mtest-assets \\
        api python -m pytest tests/integration -q
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

INTEGRATION_ENABLED = os.environ.get("MARIONETTE_INTEGRATION") == "1"


def _mk_engine(schema: str):
    """每个请求一个 NullPool 引擎：TestClient 每次请求可能在不同事件循环里跑。"""
    from app.core.config import get_settings

    return create_async_engine(
        get_settings().database_url,
        poolclass=NullPool,
        connect_args={"server_settings": {"search_path": f'"{schema}",public'}},
    )


def _admin_engine():
    from app.core.config import get_settings

    return create_async_engine(
        get_settings().database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool
    )


@pytest.fixture(scope="session")
def pg_schema() -> Any:
    if not INTEGRATION_ENABLED:
        pytest.skip("需要真实 PostgreSQL；设 MARIONETTE_INTEGRATION=1 并在 api 容器内运行")

    import app.models  # noqa: F401 —— 注册全部表
    from app.models.base import Base

    schema = f"mtest_{uuid.uuid4().hex[:10]}"

    async def _setup() -> None:
        admin = _admin_engine()
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        await admin.dispose()
        engine = _mk_engine(schema)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    async def _teardown() -> None:
        admin = _admin_engine()
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin.dispose()

    asyncio.run(_setup())
    try:
        yield schema
    finally:
        asyncio.run(_teardown())


@pytest.fixture(scope="session")
def client(pg_schema: str) -> Any:
    """已登录的测试客户端；DB 依赖被替换为指向临时 schema 的会话。"""
    from app.api.v1 import deps
    from app.core.config import get_settings
    from app.main import app

    async def _override():
        engine = _mk_engine(pg_schema)
        try:
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
        finally:
            await engine.dispose()

    app.dependency_overrides[deps.db_session] = _override
    # 不用 with：跳过 lifespan，避免启动回收任务触碰生产表
    http = TestClient(app, base_url="https://testserver", raise_server_exceptions=False)
    login = http.post("/api/v1/auth/login", json={"password": get_settings().access_password})
    assert login.status_code == 200, login.text
    try:
        yield http
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# 工厂夹具
# --------------------------------------------------------------------------- #
def _payload(name: str, **over: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "name": name,
        "description": f"{name}的描述文本，用于关键词检索。",
        "first_mes": f"你好，我是{name}。",
        "tags": [],
    }
    data.update(over)
    return {"spec": "rpg_card", "spec_version": "1.0", "data": data}


def _png_card(payload: dict[str, Any]) -> bytes:
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo

    info = PngInfo()
    info.add_text(
        "chara",
        base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii"),
    )
    buffer = io.BytesIO()
    Image.new("RGB", (96, 144), (24, 30, 44)).save(buffer, format="PNG", pnginfo=info)
    return buffer.getvalue()


@pytest.fixture
def card_payload() -> Callable[..., dict[str, Any]]:
    return _payload


@pytest.fixture
def png_card() -> Callable[[dict[str, Any]], bytes]:
    return _png_card


@pytest.fixture
def card_factory(client: TestClient) -> Callable[..., dict[str, Any]]:
    def factory(name: str, **over: Any) -> dict[str, Any]:
        resp = client.post("/api/v1/cards", json=_payload(name, **over))
        assert resp.status_code == 201, resp.text
        return resp.json()["data"]

    return factory
