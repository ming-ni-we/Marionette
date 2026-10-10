"""数据库引擎与会话工厂（SQLAlchemy 2.0 async）。

铁律：禁止在生产使用 `Base.metadata.create_all`，建表一律走 Alembic（见 pitfalls.jsonl）。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_settings = get_settings()

engine = create_async_engine(
    _settings.database_url,
    echo=_settings.db_echo,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：请求级数据库会话。"""
    async with SessionLocal() as session:
        yield session


async def check_database() -> tuple[bool, str]:
    """返回 (是否连通, 中文说明)。"""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, "数据库连接正常。"
    except Exception as exc:  # noqa: BLE001
        return False, f"无法连接数据库：{type(exc).__name__}。请检查 db 容器是否 healthy、DB_PASSWORD 是否正确。"


async def check_pgvector() -> tuple[bool, str]:
    """确认 pgvector 扩展已装载。"""
    try:
        async with engine.connect() as conn:
            row = await conn.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            )
            version = row.scalar_one_or_none()
        if version:
            return True, f"pgvector {version} 已装载。"
        return False, "未找到 pgvector 扩展：镜像必须是 pgvector/pgvector:pg18，且迁移已执行 CREATE EXTENSION vector。"
    except Exception as exc:  # noqa: BLE001
        return False, f"检测 pgvector 失败：{type(exc).__name__}。请先确认数据库连通。"


async def dispose_engine() -> None:
    await engine.dispose()
