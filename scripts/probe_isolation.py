"""决定性探针：验证 conftest 的 schema 隔离机制到底有没有生效。

不修改任何文件。只做：建临时 schema -> 用与 conftest 完全相同的 connect_args 建引擎
-> 打印实际 search_path / current_schema -> 调 TestClient 写一条卡 -> 数两边行数
-> 清理。
"""
from __future__ import annotations

import asyncio
import os
import uuid

os.environ["MARIONETTE_INTEGRATION"] = "1"
os.environ.setdefault("ACCESS_PASSWORD", "probe-pass")
os.environ.setdefault("SECRET_KEY", "probe-secret")

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.core.config import get_settings  # noqa: E402

SCHEMA = f"probe_{uuid.uuid4().hex[:8]}"
URL = get_settings().database_url


def mk_engine(schema: str):
    return create_async_engine(
        URL,
        poolclass=NullPool,
        connect_args={"server_settings": {"search_path": f'"{schema}",public'}},
    )


def admin_engine():
    return create_async_engine(URL, isolation_level="AUTOCOMMIT", poolclass=NullPool)


async def setup() -> None:
    import app.models  # noqa: F401
    from app.models.base import Base

    a = admin_engine()
    async with a.begin() as c:
        await c.execute(text(f'CREATE SCHEMA "{SCHEMA}"'))
    await a.dispose()
    e = mk_engine(SCHEMA)
    async with e.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    await e.dispose()


async def probe_search_path() -> None:
    e = mk_engine(SCHEMA)
    async with e.connect() as c:
        sp = (await c.execute(text("SHOW search_path"))).scalar_one()
        cs = (await c.execute(text("select current_schema()"))).scalar_one()
        print(f"[probe] SHOW search_path = {sp}")
        print(f"[probe] current_schema() = {cs}")
        print(f"[probe] 期望 = {SCHEMA}")
    await e.dispose()


def run_http() -> None:
    from app.api.v1 import deps
    from app.main import app
    from fastapi.testclient import TestClient

    async def _override():
        engine = mk_engine(SCHEMA)
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
    http = TestClient(app, base_url="https://testserver", raise_server_exceptions=False)
    login = http.post("/api/v1/auth/login", json={"password": get_settings().access_password})
    print(f"[probe] login = {login.status_code}")
    payload = {
        "spec": "rpg_card",
        "spec_version": "1.0",
        "data": {"name": "PROBE_ISOLATION_CARD", "first_mes": "x"},
    }
    r = http.post("/api/v1/cards", json=payload)
    print(f"[probe] POST /cards = {r.status_code}")
    app.dependency_overrides.clear()


async def count(schema: str, name: str) -> int:
    e = admin_engine()
    async with e.connect() as c:
        r = await c.execute(
            text(f'select count(*) from "{schema}".cards where name = :n'), {"n": name}
        )
        v = int(r.scalar_one())
    await e.dispose()
    return v


async def teardown() -> None:
    a = admin_engine()
    async with a.begin() as c:
        await c.execute(text(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE'))
    await a.dispose()


async def main() -> None:
    await setup()
    print(f"[probe] 临时 schema = {SCHEMA}")
    await probe_search_path()
    run_http()
    in_tmp = await count(SCHEMA, "PROBE_ISOLATION_CARD")
    in_pub = await count("public", "PROBE_ISOLATION_CARD")
    print(f"[probe] 写入落在 临时schema = {in_tmp} 条 ; public = {in_pub} 条")
    print(
        "[probe] 结论 = "
        + ("隔离生效（仅临时 schema 有数据）" if in_tmp == 1 and in_pub == 0 else "隔离失效（数据落进 public）")
    )
    await teardown()


asyncio.run(main())
