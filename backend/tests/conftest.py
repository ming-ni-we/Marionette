"""测试全局环境（pytest 最先加载本文件，早于任何 app.* 导入）。

**凭证隔离**：测试进程**强制**使用固定的测试口令，绝不继承部署环境里那个随机
ACCESS_PASSWORD。理由：
  - 部署口令是随机生成的，集成用例若继承它，同一份用例在本地与服务器上走的是
    不同凭证，断言失败时分不清是「代码错」还是「环境串味」；
  - 本文件在 pytest 启动时即写入 os.environ，且早于 `app.core.config.get_settings()`
    的首次调用（lru_cache 单例），因此进程内所有组件看到的是同一个测试口令。

数据库连接串**不在这里覆盖**：集成测试必须连真实 PostgreSQL，由运行环境注入。
"""

from __future__ import annotations

import os

# 唯一的凭证来源：测试模块与集成夹具都读它，不再各自硬编码。
TEST_ACCESS_PASSWORD = "test-passphrase"

# 必须用下标赋值（覆盖），不能用 setdefault——后者会在服务器上被部署口令顶掉。
os.environ["ACCESS_PASSWORD"] = TEST_ACCESS_PASSWORD
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"

# 断言依赖这些默认值，写明比依赖 config.py 的默认值更稳
os.environ.setdefault("ACCESS_MAX_FAILED", "5")
os.environ.setdefault("ACCESS_LOCK_WINDOW_SECONDS", "900")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")
os.environ.setdefault("APP_ENV", "test")


# --------------------------------------------------------------------------- #
# 运行时 M1 单测夹具：内存 sqlite（把 PG 专有类型/server_default 适配到 sqlite）
# --------------------------------------------------------------------------- #
import uuid  # noqa: E402
from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import JSON  # noqa: E402
from sqlalchemy.dialects.postgresql import ARRAY, JSONB  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402


@compiles(JSONB, "sqlite")
def _compile_jsonb(_type, _compiler, **_kw):  # noqa: ANN001
    return "JSON"


@compiles(ARRAY, "sqlite")
def _compile_array(_type, _compiler, **_kw):  # noqa: ANN001
    return "JSON"


_ORIGINALS: list | None = None


def _adapt_metadata_for_sqlite() -> None:
    """为 sqlite 建表剥离 PG 专有 server_default（类型不改，DDL 靠 @compiles 转 JSON）。

    只动 server_default 不动 column.type：InstrumentedAttribute 会在首次比较时
    缓存 type 派生出的 comparator，改了 type 即使还原也会污染其它用例（如 test_search）。
    JSONB/ARRAY 的建表编译已由上面的 @compiles 钩子处理。
    """
    global _ORIGINALS
    if _ORIGINALS is not None:
        return

    import datetime as _dt

    from sqlalchemy import ColumnDefault

    import app.models  # noqa: F401 —— 注册全部表
    from app.models.base import Base

    _ORIGINALS = []
    for table in Base.metadata.tables.values():
        for column in table.columns:
            _ORIGINALS.append(
                (column, column.type, column.server_default, column.default, column.onupdate)
            )
            if column.server_default is not None:
                column.server_default = None
                if column.name in ("created_at", "updated_at"):
                    column.default = ColumnDefault(_dt.datetime.now)
                    if column.name == "updated_at":
                        column.onupdate = ColumnDefault(_dt.datetime.now)
                elif column.name == "status":
                    column.default = ColumnDefault("active")
            # 类型改 JSON：既让 DDL 可编译，也让 list/dict 绑定能序列化为文本
            if isinstance(column.type, JSONB):
                column.type = JSON()
            elif isinstance(column.type, ARRAY):
                column.type = JSON()


def _restore_metadata() -> None:
    global _ORIGINALS
    if _ORIGINALS is None:
        return
    for column, col_type, server_default, default, onupdate in _ORIGINALS:
        column.type = col_type
        column.server_default = server_default
        column.default = default
        column.onupdate = onupdate
    _ORIGINALS = None
    # 关键：InstrumentedAttribute 会在首次访问后把 type/comparator 缓存到**实例**上，
    # 若缓存的是被替换过的 JSON 类型，还原列类型后仍会污染后续用例（如 test_search
    # 依赖 ARRAY 的 @> 语义）。这里清掉这些缓存，强制下次访问按真实列类型重建。
    import app.models  # noqa: F401

    for mapper in _all_mappers():
        for prop in mapper.attrs:
            descriptor = prop.class_attribute
            for cached in ("type", "comparator", "_memoized_keys"):
                if cached in vars(descriptor):
                    del vars(descriptor)[cached]


def _all_mappers() -> list:
    from app.models.base import Base

    return list(Base.registry.mappers)


@pytest_asyncio.fixture(autouse=True)
def _disable_story_image_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """单测默认关闭「剧情配图自动触发」（S16 §4.6.3）。

    为什么必须 autouse：出图是**花钱且有网络副作用**的动作。本机 `.env` 里
    `STORY_IMAGE_ENABLED=true` 时，`get_settings()` 会被测试读到，于是每条走
    `ChatSvc.stream_reply` 的用例都可能真的去调火山 API —— 既烧钱，又让用例
    依赖外网而变得不稳定（实测：失败时会先重试 json_format 再重试裸调，单条
    用例从 0.1s 劣化到 24s）。

    需要验证自动触发的用例请显式覆盖：`monkeypatch.setattr(settings, ...)`。
    """
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "story_image_enabled", False, raising=False)


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    """内存 sqlite 会话（把真实元数据适配到 sqlite 后建表，用完还原元数据）。"""
    from app.models.base import Base

    _adapt_metadata_for_sqlite()
    try:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            yield session
        await engine.dispose()
    finally:
        _restore_metadata()


@pytest_asyncio.fixture
async def card_and_preset(db: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """建一张卡 + 一个预设，返回各自 id（供会话/流式用例复用）。"""
    from app.models.card import Card
    from app.models.preset import Preset

    card = Card(
        owner_id="local",
        name="林晓",
        spec="rpg_card",
        spec_version="1.0",
        data={"name": "林晓", "first_mes": "风铃轻响。", "alternate_greetings": ["第二句"]},
        extensions={},
        tags=[],
    )
    preset = Preset(
        owner_id="local",
        name="默认",
        spec="rpg_preset",
        spec_version="1.0",
        data={
            "name": "默认",
            "prompt_template": {"system": "你是 {{char}}", "placeholders": {}},
            "context_budget": {"max_context_tokens": 2048, "reserve_for_output": 256},
        },
        extensions={},
    )
    db.add_all([card, preset])
    await db.flush()
    return card.id, preset.id
