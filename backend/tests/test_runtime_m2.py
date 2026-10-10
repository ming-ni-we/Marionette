"""运行时 M2 单测：出图钩子 + 自动归档 + 审核层 + 埋点/诊断。

覆盖要点：
  - ImageHook.submit 校验（空 prompt / 不存在 card）；card 由 session 推导
  - **铁律**：ImageJob 转 done 时服务端自动建 kind=generated 资产并回填关联 + 归档
  - 出图失败 -> 任务 failed 且不建资产
  - ModerationSvc 输入/输出双端拦截；关闭审核必须带风险确认标记
  - TelemetrySvc 事件落本地 JSONL、诊断包含脱敏配置且不含 api_key
"""

from __future__ import annotations

import json
import zipfile

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import GeneratedImage
from app.core.errors import BadRequestError, ModerationBlockedError, NotFoundError


# --------------------------------------------------------------------------- #
# 测试替身：内存资产存储 + 可控图像提供者
# --------------------------------------------------------------------------- #
class _MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def save(self, data, *, filename, content_type, kind="gallery"):
        from app.adapters.base import StoredObject

        key = f"{kind}/{filename}"
        self.objects[key] = data
        return StoredObject(storage_key=key, size_bytes=len(data))

    async def read(self, storage_key: str) -> bytes:
        return self.objects[storage_key]

    async def delete(self, storage_key: str) -> bool:
        return self.objects.pop(storage_key, None) is not None

    async def exists(self, storage_key: str) -> bool:
        return storage_key in self.objects


class _FakeImageProvider:
    name = "cloud"

    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    @property
    def enabled(self) -> bool:
        return True

    async def generate(self, prompt, *, params=None):  # noqa: ANN001
        if self._fail:
            raise RuntimeError("上游出图失败")
        return GeneratedImage(
            data=b"\x89PNG-fake-bytes",
            content_type="image/png",
            meta={"prompt": prompt, "width": 1024, "height": 1024},
        )


@pytest.fixture
def image_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """把 registry 的资产存储与图像提供者替换成内存替身（出图不联网）。"""
    import app.services.image_hook as hook_mod

    store = _MemoryStore()
    monkeypatch.setattr(hook_mod, "get_asset_store", lambda: store)
    monkeypatch.setattr(hook_mod, "get_image_provider", lambda: _FakeImageProvider())
    return store


# --------------------------------------------------------------------------- #
# ImageHook：提交与校验
# --------------------------------------------------------------------------- #
async def test_image_submit_rejects_empty_prompt(db: AsyncSession) -> None:
    from app.services.image_hook import ImageHook

    with pytest.raises(BadRequestError):
        await ImageHook(db).submit({"prompt": "   "})


async def test_image_submit_rejects_unknown_card(db: AsyncSession) -> None:
    import uuid

    from app.services.image_hook import ImageHook

    with pytest.raises(BadRequestError):
        await ImageHook(db).submit({"prompt": "一只猫", "card_id": str(uuid.uuid4())})


async def test_image_submit_derives_card_from_session(
    db: AsyncSession, card_and_preset: tuple
) -> None:
    from app.services.image_hook import ImageHook
    from app.services.session import SessionSvc

    card_id, preset_id = card_and_preset
    created = await SessionSvc(db).create(
        {"character_card_id": str(card_id), "preset_id": str(preset_id), "greeting_index": -1}
    )
    hook = ImageHook(db)
    job = await hook.submit({"prompt": "夜景", "session_id": str(created["id"])})
    assert job.status == "queued"
    assert job.card_id == card_id  # 由 session 推导


# --------------------------------------------------------------------------- #
# 铁律：done 时服务端自动归档（建 generated 资产 + 回填关联）
# --------------------------------------------------------------------------- #
async def test_image_done_auto_archives_generated_asset(
    db: AsyncSession, card_and_preset: tuple, image_env
) -> None:
    from app.models.asset import Asset
    from app.services.image_hook import ImageHook
    from app.services.session import SessionSvc

    card_id, preset_id = card_and_preset
    session = await SessionSvc(db).create(
        {"character_card_id": str(card_id), "preset_id": str(preset_id), "greeting_index": -1}
    )
    # 配置图像后端（base_url + api_key），否则 resolve_backend 会因未配置而拒绝
    from app.services.config import ConfigSvc

    await ConfigSvc(db).set_image(
        {"provider": "cloud", "base_url": "https://img.example.com/v1", "api_key": "sk-test12345678"}
    )
    hook = ImageHook(db)
    job = await hook.generate_and_archive(
        prompt="雨夜的书店",
        params={"width": 768, "height": 1024, "seed": 42},
        card_id=card_id,
        session_id=session["id"],
    )

    # 任务已 done 且回填 asset_id / archived
    assert job.status == "done"
    assert job.archived is True
    assert job.asset_id is not None
    assert job.error is None

    # 服务端创建了 kind=generated 资产，并带齐三关联 + meta
    asset = (
        await db.execute(select(Asset).where(Asset.id == job.asset_id))
    ).scalar_one()
    assert asset.kind == "generated"
    assert asset.card_id == card_id           # 登记进角色图集
    assert asset.session_id is not None       # 归属会话
    assert asset.content_type == "image/png"
    assert asset.meta["prompt"] == "雨夜的书店"
    assert asset.meta["seed"] == 42
    assert asset.meta["job_id"] == str(job.id)


async def test_image_failure_marks_failed_without_asset(
    db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.image_hook as hook_mod
    from app.models.asset import Asset
    from app.services.image_hook import ImageHook

    card_id, _ = card_and_preset
    monkeypatch.setattr(hook_mod, "get_asset_store", lambda: _MemoryStore())
    monkeypatch.setattr(hook_mod, "get_image_provider", lambda: _FakeImageProvider(fail=True))

    from app.services.config import ConfigSvc

    await ConfigSvc(db).set_image(
        {"provider": "cloud", "base_url": "https://img.example.com/v1", "api_key": "sk-test12345678"}
    )
    hook = ImageHook(db)
    with pytest.raises(Exception):  # noqa: B017 —— 上游失败向上抛
        await hook.generate_and_archive(prompt="会失败的图", card_id=card_id)

    # 未创建任何资产；任务留下 failed 足迹
    assets = (await db.execute(select(Asset))).scalars().all()
    assert assets == []
    from app.models.image_job import ImageJob as ImageJobRow

    jobs = (await db.execute(select(ImageJobRow))).scalars().all()
    assert jobs and jobs[0].status == "failed"
    assert jobs[0].error


async def test_image_get_row_not_found(db: AsyncSession) -> None:
    import uuid

    from app.services.image_hook import ImageHook

    with pytest.raises(NotFoundError):
        await ImageHook(db).get_row(str(uuid.uuid4()))


# --------------------------------------------------------------------------- #
# 审核层
# --------------------------------------------------------------------------- #
async def test_moderation_blocks_input(db: AsyncSession) -> None:
    from app.services.config import ConfigSvc
    from app.services.moderation import ModerationSvc

    await ConfigSvc(db).set_moderation(
        {
            "enabled": True,
            "check_input": True,
            "check_output": True,
            "rules": {"blocked_words": ["禁词"], "block_on_match": True},
        }
    )
    with pytest.raises(ModerationBlockedError):
        await ModerationSvc(db).check_input("这句话里有禁词")
    # 正常文本放行
    verdict = await ModerationSvc(db).check_input("正常的问候")
    assert verdict.blocked is False


async def test_moderation_blocks_output(db: AsyncSession) -> None:
    from app.services.config import ConfigSvc
    from app.services.moderation import ModerationSvc

    await ConfigSvc(db).set_moderation(
        {"enabled": True, "rules": {"blocked_words": ["违禁输出"]}}
    )
    with pytest.raises(ModerationBlockedError):
        await ModerationSvc(db).check_output("模型吐出了违禁输出")


async def test_moderation_disabled_bypasses(db: AsyncSession) -> None:
    from app.services.config import ConfigSvc
    from app.services.moderation import ModerationSvc

    # 直接落库为关闭态（绕过路由风险确认，此处只测适配器行为）
    await ConfigSvc(db).set_moderation(
        {"enabled": False, "rules": {"blocked_words": ["禁词"]}}
    )
    verdict = await ModerationSvc(db).check_input("这里也有禁词")
    assert verdict.blocked is False


def test_disable_requires_risk_ack() -> None:
    from app.services.moderation import validate_moderation_update

    existing = {"enabled": True}
    # 开 -> 关，未带风险确认：拒绝
    with pytest.raises(BadRequestError):
        validate_moderation_update({"enabled": False}, existing=existing)
    # 带风险确认：放行，且 risk_ack 不落库
    cleaned = validate_moderation_update({"enabled": False}, existing=existing, risk_ack=True)
    assert cleaned == {"enabled": False}


def test_disable_idempotent_when_already_off() -> None:
    from app.services.moderation import validate_moderation_update

    # 本就关闭，再次写关闭无需风险确认（幂等）
    cleaned = validate_moderation_update({"enabled": False}, existing={"enabled": False})
    assert cleaned == {"enabled": False}


def test_build_settings_falls_back_to_default_words() -> None:
    from app.services.moderation import build_settings

    settings = build_settings({"enabled": True, "rules": {"blocked_words": []}})
    assert settings.enabled is True
    assert settings.blocked_words  # 回落内置默认词表


# --------------------------------------------------------------------------- #
# 埋点与诊断包
# --------------------------------------------------------------------------- #
def test_telemetry_records_local_only(tmp_path) -> None:
    from app.services.telemetry import TelemetrySvc

    svc = TelemetrySvc(directory=tmp_path)
    entry = svc.record("session_created", {"card_id": "abc", "nested": {"x": 1}, "long": "y" * 999})
    assert entry["name"] == "session_created"
    assert entry["properties"]["nested"] == "<dict>"          # 嵌套对象不落库
    assert len(entry["properties"]["long"]) == 512            # 超长截断

    # 落盘为 JSONL，可被读回
    raw = (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip()
    assert json.loads(raw)["name"] == "session_created"
    assert svc.read_events()[0]["name"] == "session_created"


async def test_diagnostics_zip_is_masked(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.telemetry import TelemetrySvc

    svc = TelemetrySvc(directory=tmp_path)
    svc.record("worldbook_entry_triggered", {"entry_id": "e1"})
    blob = await svc.build_diagnostics(checks=[{"name": "database", "status": "ok"}])

    with zipfile.ZipFile(__import__("io").BytesIO(blob)) as zf:
        names = set(zf.namelist())
        assert "summary.json" in names
        summary = json.loads(zf.read("summary.json"))
    # 配置快照脱敏：只含布尔与模型名，绝不含任何 api_key / 明文口令
    snapshot = summary["config_snapshot"]
    assert "api_key" not in json.dumps(snapshot)
    assert summary["checks"][0]["name"] == "database"
    assert summary["events"][0]["name"] == "worldbook_entry_triggered"


# --------------------------------------------------------------------------- #
# 对话流接线：image 事件 + 审核拦截
# --------------------------------------------------------------------------- #
class _FakeRouter:
    def __init__(self, pieces: list[str]) -> None:
        self._pieces = pieces

    async def stream(self, messages, **kwargs):  # noqa: ANN001
        for piece in self._pieces:
            yield piece


async def test_chat_emits_image_event_with_asset(
    db: AsyncSession, card_and_preset: tuple, image_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.chat import ChatSvc
    from app.services.config import ConfigSvc
    from app.services.session import SessionSvc

    card_id, preset_id = card_and_preset
    await ConfigSvc(db).set_image(
        {"provider": "cloud", "base_url": "https://img.example.com/v1", "api_key": "sk-test12345678"}
    )
    session = await SessionSvc(db).create(
        {"character_card_id": str(card_id), "preset_id": str(preset_id), "greeting_index": -1}
    )

    chat = ChatSvc(db)
    monkeypatch.setattr(chat, "_router", _FakeRouter(["雨", "夜", "。"]))

    events: list[tuple[str, dict]] = []
    async for evt in chat.stream_reply(
        str(session["id"]), input_text="画一张画", overrides={"image": {"prompt": "雨夜"}}
    ):
        events.append(evt)

    names = [e for e, _ in events]
    assert "image" in names
    assert names[-1] == "done"
    image_payload = dict(events)["image"]
    assert image_payload["asset_id"]
    assert image_payload["job_id"]


async def test_chat_moderation_blocks_input(
    db: AsyncSession, card_and_preset: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.chat import ChatSvc
    from app.services.config import ConfigSvc
    from app.services.session import SessionSvc

    card_id, preset_id = card_and_preset
    await ConfigSvc(db).set_moderation({"enabled": True, "rules": {"blocked_words": ["禁词"]}})
    session = await SessionSvc(db).create(
        {"character_card_id": str(card_id), "preset_id": str(preset_id), "greeting_index": -1}
    )

    chat = ChatSvc(db)
    monkeypatch.setattr(chat, "_router", _FakeRouter(["不应", "生成"]))

    # 输入含禁词：在进入生成前即被拦截（403）
    with pytest.raises(ModerationBlockedError):
        async for _ in chat.stream_reply(str(session["id"]), input_text="这有禁词"):
            pass
