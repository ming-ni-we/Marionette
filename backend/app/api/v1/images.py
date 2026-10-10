"""Images 路由（出图任务，F12 / schemas.md §10.2）。

路由只做编排：解析入参 -> 调 ImageHook -> 套统一信封。
业务逻辑（含**服务端自动归档**）一律在 services/image_hook.py。

契约对齐 openapi.yaml：
  POST /images/jobs        202 入队（建任务行）
  GET  /images/jobs/{id}   200 查询

说明：POST 采用「同步出图 + 归档」语义（单机单用户，无需真实任务队列）；
调用成功即返回 status=done 且带 asset_id。若关闭即时执行（?defer=true），
则只建 queued 记录返回 202。
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.v1.deps import DbSession
from app.schemas.asset import ImageJob, ImageJobCreateRequest
from app.schemas.common import Envelope
from app.services.image_hook import ImageHook

router = APIRouter(tags=["Images"])


@router.post(
    "/images/jobs",
    response_model=Envelope[ImageJob],
    status_code=202,
    summary="触发一次图像生成",
)
async def create_image_job(
    db: DbSession,
    payload: ImageJobCreateRequest,
    defer: bool = Query(
        False,
        description="true 时仅入队（status=queued），由前端稍后轮询；默认同步出图并归档。",
    ),
) -> Envelope[ImageJob]:
    """提交出图任务。

    - defer=false（默认）：同步执行 -> 完成时服务端自动创建 kind=generated 资产，
      返回 status=done 且带 asset_id（前端据此取图，无需自行拼装归档）。
    - defer=true：仅建任务行（status=queued），返回后由前端轮询 GET。
    """
    hook = ImageHook(db)
    fields = payload.model_dump(mode="json")
    job = await hook.submit(fields)
    if not defer:
        params = {
            "width": payload.width,
            "height": payload.height,
            "seed": payload.seed,
            "negative_prompt": payload.negative_prompt,
            "steps": payload.steps,
        }
        job = await hook.run(job, prompt=payload.prompt, params=params)
    return Envelope(data=ImageJob.model_validate(hook.serialize(job)))


@router.get(
    "/images/jobs/{jobId}",
    response_model=Envelope[ImageJob],
    summary="查询图像生成任务",
)
async def get_image_job(db: DbSession, jobId: str) -> Envelope[ImageJob]:
    hook = ImageHook(db)
    row = await hook.get_row(jobId)
    return Envelope(data=ImageJob.model_validate(hook.serialize(row)))
