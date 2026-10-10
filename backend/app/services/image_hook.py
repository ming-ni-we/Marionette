"""图像出图钩子服务（架构 §4.8 / schemas.md §10.2）。

职责：
  - 触发（手动 / 会话内自动）-> 建 `image_jobs` 记录并入队
  - 调 ImageProvider（默认 CloudImageProvider）出图，不阻塞对话主流（失败仅置 failed）
  - **完成（done）时由服务端自动归档**（OPEN-007 归档链路契约化，铁律）：
      1. 创建 kind=generated 的 assets 行，回填 card_id / session_id / message_id / meta，
         置 archived=true，并写入 image_jobs.asset_id
      2. 登记进角色图集（资产的 card_id 即图集归属，前端按 card_id 检索即可）
    **前端禁止自行拼装归档逻辑**：出图完成必须拿到服务端生成的 asset_id。

分层铁律（SPEC §4.2）：本服务只依赖 ImageProvider / AssetStore 接口与 ORM 模型，
绝不 import 任何厂商 SDK。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import GeneratedImage
from app.adapters.registry import get_asset_store, get_image_provider
from app.core.errors import AppError, BadRequestError, ErrorClass, NotFoundError, UpstreamError
from app.core.ids import parse_uuid
from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.card import Card
from app.models.image_job import ImageJob as ImageJobRow
from app.models.session import Session as SessionRow
from app.services.config import ConfigSvc

logger = get_logger(__name__)

# 出图任务状态（与 schemas.asset.ImageJobStatus 严格一致）
JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_DONE = "done"
JOB_FAILED = "failed"

# 自动归档出的资产类型（schemas.md §10.2 铁律）
ARCHIVE_KIND = "generated"

# 会话内出图触发的默认提示词前缀（前端可在 overrides 里覆盖）
DEFAULT_IMAGE_PROMPT_PREFIX = ""


@dataclass(frozen=True)
class ImageBackend:
    """已解析的出图后端参数（api_key 为明文，仅在本层内存中使用）。"""

    provider: str
    base_url: str
    api_key: str
    model: str


class ImageHook:
    """出图任务编排 + **服务端自动归档**。

    与对话流的关系：`submit()` 建任务行；`run()` 调适配器出图并在 done 时归档。
    SSE 的 `image` 事件由 ChatSvc 依据归档结果推送（asset_id + job_id）。
    """

    def __init__(self, db: AsyncSession | None = None) -> None:
        self._db = db

    # ------------------------------------------------------------------ #
    # 后端参数解析（DB 配置优先，环境变量兜底）
    # ------------------------------------------------------------------ #
    async def resolve_backend(self) -> ImageBackend:
        raw: dict[str, Any] = {}
        if self._db is not None:
            raw = await ConfigSvc(self._db).get_image_raw()
        backend = ImageBackend(
            provider=str(raw.get("provider") or "cloud"),
            base_url=str(raw.get("base_url") or ""),
            api_key=str(raw.get("api_key") or ""),
            model=str(raw.get("model") or ""),
        )
        if backend.provider == "cloud" and (not backend.base_url or not backend.api_key):
            raise UpstreamError(
                "尚未配置图像后端：请在「设置 → 出图」里填写图像 API 的 base_url 与 api_key。",
                error_class=ErrorClass.endpoint_invalid,
            )
        return backend

    # ------------------------------------------------------------------ #
    # 建任务（提交）
    # ------------------------------------------------------------------ #
    async def submit(self, payload: dict[str, Any]) -> ImageJobRow:
        """建一条出图任务并入队（status=queued）。

        card_id 缺省时由 session_id 推导；两者都非法/外部校验失败时抛 400/404。
        """
        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            raise BadRequestError("出图提示词（prompt）不能为空。")

        card_id = await self._resolve_card_id(payload)
        session_id = payload.get("session_id")
        message_id = payload.get("message_id")

        row = ImageJobRow(
            session_id=parse_uuid(session_id, field="session_id") if session_id else None,
            card_id=card_id,
            message_id=parse_uuid(message_id, field="message_id") if message_id else None,
            status=JOB_QUEUED,
            provider=str(payload.get("provider") or "cloud"),
            archived=False,
        )
        if self._db is None:
            raise RuntimeError("ImageHook.submit 需要数据库会话。")
        self._db.add(row)
        await self._db.flush()
        await self._db.refresh(row)
        logger.info("image job queued", extra={"job": str(row.id), "card": str(card_id)})
        return row

    async def _resolve_card_id(self, payload: dict[str, Any]) -> uuid.UUID | None:
        """归档目标角色：显式 card_id 优先，否则由 session_id 推导（并做存在性校验）。"""
        if self._db is None:
            return None
        raw_card = payload.get("card_id")
        if raw_card:
            card_id = parse_uuid(raw_card, field="card_id")
            exists = (
                await self._db.execute(select(Card.id).where(Card.id == card_id))
            ).scalar_one_or_none()
            if exists is None:
                raise BadRequestError(f"归档目标角色（id={card_id}）不存在。")
            return card_id

        raw_session = payload.get("session_id")
        if raw_session:
            session_id = parse_uuid(raw_session, field="session_id")
            session_row = (
                await self._db.execute(select(SessionRow).where(SessionRow.id == session_id))
            ).scalar_one_or_none()
            if session_row is None:
                raise BadRequestError(f"归档目标会话（id={session_id}）不存在。")
            return session_row.card_id
        return None

    # ------------------------------------------------------------------ #
    # 取任务
    # ------------------------------------------------------------------ #
    async def get_row(self, job_id: str | uuid.UUID) -> ImageJobRow:
        if self._db is None:
            raise RuntimeError("ImageHook.get_row 需要数据库会话。")
        uid = parse_uuid(job_id, field="jobId")
        row = (
            await self._db.execute(select(ImageJobRow).where(ImageJobRow.id == uid))
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError(f"出图任务（id={uid}）不存在或已被删除。")
        return row

    @staticmethod
    def serialize(row: ImageJobRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "status": row.status,
            "provider": row.provider,
            "prompt_id": row.prompt_id,
            "card_id": row.card_id,
            "session_id": row.session_id,
            "message_id": row.message_id,
            "asset_id": row.asset_id,
            "archived": bool(row.archived),
            "error": row.error,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    # ------------------------------------------------------------------ #
    # 执行出图（入队 -> running -> done/failed + 归档）
    # ------------------------------------------------------------------ #
    async def run(self, job: ImageJobRow, *, prompt: str, params: dict[str, Any] | None = None) -> ImageJobRow:
        """执行出图任务。成功则 done 并**自动归档**；失败置 failed（不抛给对话主流）。"""
        if self._db is None:
            raise RuntimeError("ImageHook.run 需要数据库会话。")

        job.status = JOB_RUNNING
        await self._db.flush()

        backend = await self.resolve_backend()
        generated = await self._generate(backend, prompt, params)
        await self._finalize_done(job, generated, prompt=prompt, params=params or {})
        return job

    async def _generate(
        self, backend: ImageBackend, prompt: str, params: dict[str, Any] | None
    ) -> GeneratedImage:
        """调适配器出图；把上游异常归类为 UpstreamError（含 error_class）。"""
        provider = get_image_provider()
        try:
            return await provider.generate(prompt, params=params)
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001 —— 兜底归类，避免裸 500
            logger.warning("image generate failed: %s", type(exc).__name__)
            raise UpstreamError(
                f"图像生成失败（{type(exc).__name__}）：请检查出图后端配置。",
                error_class=ErrorClass.unknown,
            ) from exc

    async def _finalize_done(
        self,
        job: ImageJobRow,
        generated: GeneratedImage,
        *,
        prompt: str,
        params: dict[str, Any],
    ) -> None:
        """**服务端自动归档**（铁律）：落存储 -> 建 kind=generated 资产 -> 关联图集。

        归档要素：card_id / session_id / message_id 三关联 + meta（prompt/尺寸/模型）。
        """
        if self._db is None:
            raise RuntimeError("归档需要数据库会话。")

        ext = ".png" if generated.content_type == "image/png" else ""
        filename = f"generated-{job.id}{ext or '.bin'}"
        stored = await get_asset_store().save(
            generated.data,
            filename=filename,
            content_type=generated.content_type,
            kind=ARCHIVE_KIND,
        )

        meta: dict[str, Any] = {
            **(generated.meta or {}),
            "prompt": prompt,
            "job_id": str(job.id),
        }
        if params.get("negative_prompt"):
            meta["negative_prompt"] = params["negative_prompt"]
        if params.get("seed") not in (None, -1):
            meta["seed"] = params["seed"]

        asset = Asset(
            owner_id="local",
            kind=ARCHIVE_KIND,
            filename=filename,
            content_type=generated.content_type or "image/png",
            size_bytes=stored.size_bytes,
            storage_key=stored.storage_key,
            card_id=job.card_id,
            session_id=job.session_id,
            message_id=job.message_id,
            tags=["generated"],
            meta=meta,
        )
        self._db.add(asset)
        await self._db.flush()
        await self._db.refresh(asset)

        # 回填任务：done + asset_id + archived=true（前端据 asset_id 取图，无需拼装）
        job.status = JOB_DONE
        job.asset_id = asset.id
        job.archived = True
        job.error = None
        await self._db.flush()
        await self._db.refresh(job)
        logger.info(
            "image job archived",
            extra={"job": str(job.id), "asset": str(asset.id), "card": str(job.card_id)},
        )

    async def mark_failed(self, job: ImageJobRow, exc: BaseException) -> None:
        """把任务置 failed（写中文 error），不创建资产、不影响对话主流。"""
        if self._db is None:
            return
        job.status = JOB_FAILED
        job.error = getattr(exc, "message", None) or f"出图失败（{type(exc).__name__}）。"
        await self._db.flush()

    # ------------------------------------------------------------------ #
    # 会话内便捷入口：提交并立即出图 + 归档（供 ChatSvc 的 image 钩子调用）
    # ------------------------------------------------------------------ #
    async def generate_and_archive(
        self,
        *,
        prompt: str,
        params: dict[str, Any] | None = None,
        card_id: str | uuid.UUID | None = None,
        session_id: str | uuid.UUID | None = None,
        message_id: str | uuid.UUID | None = None,
    ) -> ImageJobRow:
        """一步到位：建任务 -> 出图 -> 归档。失败时把任务置 failed 并向上抛 AppError。"""
        job = await self.submit(
            {
                "prompt": prompt,
                "card_id": card_id,
                "session_id": session_id,
                "message_id": message_id,
            }
        )
        try:
            return await self.run(job, prompt=prompt, params=params)
        except BaseException as exc:  # noqa: BLE001 —— 归档失败也要留痕，再向上抛
            await self.mark_failed(job, exc)
            raise


__all__ = [
    "ARCHIVE_KIND",
    "DEFAULT_IMAGE_PROMPT_PREFIX",
    "JOB_DONE",
    "JOB_FAILED",
    "JOB_QUEUED",
    "JOB_RUNNING",
    "ImageBackend",
    "ImageHook",
]
