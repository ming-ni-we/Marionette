"""应用入口：只做装配（中间件 + 路由 + 静态资源 + 生命周期），不写业务逻辑。

业务逻辑一律在 services/ 内（SPEC §4.2 分层铁律）。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.db import SessionLocal, check_database, dispose_engine
from app.core.envelope import failure
from app.core.errors import AppError, ErrorClass, NotFoundError, RateLimitedError
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


async def _recover_interrupted_streams() -> None:
    """服务重启回收（架构 §4.3）：滞留的 streaming 消息转 incomplete，会话状态回 idle。"""
    try:
        async with SessionLocal() as session:
            msg_result = await session.execute(
                text("UPDATE messages SET status='incomplete', updated_at=now() WHERE status='streaming'")
            )
            sess_result = await session.execute(
                text(
                    "UPDATE sessions SET state_machine = "
                    "jsonb_set(COALESCE(state_machine, '{}'::jsonb), '{current}', '\"idle\"'), "
                    "updated_at = now() "
                    "WHERE COALESCE(state_machine->>'current', 'idle') <> 'idle'"
                )
            )
            await session.commit()
        logger.info(
            "recovered interrupted streams",
            extra={
                "messages": msg_result.rowcount or 0,
                "sessions": sess_result.rowcount or 0,
            },
        )
    except Exception as exc:  # noqa: BLE001 —— 首次启动可能尚未迁移，不阻断启动
        logger.warning("stream recovery skipped: %s", type(exc).__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info(
        "marionette starting",
        extra={
            "version": settings.app_version,
            "env": settings.app_env,
            "domain": settings.domain,
        },
    )
    for warning in settings.security_warnings():
        logger.warning("security: %s", warning)

    db_ok, db_detail = await check_database()
    logger.info("database check", extra={"ok": db_ok, "detail": db_detail})
    if db_ok:
        await _recover_interrupted_streams()

    yield

    await dispose_engine()
    logger.info("marionette stopped")


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        headers: dict[str, str] = {}
        if isinstance(exc, RateLimitedError) and exc.retry_after:
            headers["Retry-After"] = str(exc.retry_after)
        logger.warning(
            "app error",
            extra={
                "code": exc.code,
                "error_class": exc.error_class.value,
                "detail": exc.message,
            },
        )
        return JSONResponse(
            status_code=exc.http_status,
            content=failure(
                exc.code,
                exc.message,
                error_class=exc.error_class,
                model_seen=exc.model_seen,
                data=exc.data,
            ),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(p) for p in first.get("loc", ()) if p != "body") or "参数"
        detail = first.get("msg", "格式不正确")
        message = f"请求参数校验失败：{location} {detail}。请检查后重试。"
        return JSONResponse(
            status_code=400,
            content=failure(4000, message, error_class=ErrorClass.endpoint_invalid),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        mapping = {
            404: (4040, "接口或资源不存在，请检查请求路径。", ErrorClass.model_not_found),
            405: (4000, "该路径不支持此请求方法。", ErrorClass.endpoint_invalid),
            401: (4010, "未登录或会话已失效，请重新输入访问口令。", ErrorClass.auth_failed),
            403: (4030, "没有权限执行该操作。", ErrorClass.unknown),
        }
        code, message, error_class = mapping.get(
            exc.status_code,
            (exc.status_code * 10, str(exc.detail), ErrorClass.unknown),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=failure(code, message, error_class=error_class),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error: %s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content=failure(
                5000,
                "服务内部错误，请查看服务端日志定位（诊断包可在设置页导出）。",
                error_class=ErrorClass.unknown,
            ),
        )


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title="提线 (Marionette) API",
        description=(
            "AI 角色扮演平台后端。统一响应信封 {code,data,message}；"
            "错误体含 error_class（7 类）+ 中文 message + model_seen。"
            "契约以 docs/spec/openapi.yaml 为准。"
        ),
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        max_age=86400,
    )

    _register_exception_handlers(app)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> JSONResponse:
        """容器 healthcheck 用：DB 可达才返回 200。"""
        db_ok, detail = await check_database()
        if db_ok:
            return JSONResponse(status_code=200, content={"status": "ok"})
        return JSONResponse(status_code=503, content={"status": "degraded", "detail": detail})

    app.include_router(api_router, prefix="/api/v1")

    _mount_spa(app, Path(settings.static_dir))
    return app


def _mount_spa(app: FastAPI, static_dir: Path) -> None:
    """托管前端构建产物；未构建时给出明确提示而不是空白页。"""
    resolved_static = static_dir.resolve()
    # Vite 构建产物把 js/css 放在 /assets/ 下，与 API 的 /api/v1/assets 不冲突
    if (static_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="spa-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> Any:
        if full_path.startswith("api/") or full_path == "healthz":
            raise NotFoundError("接口不存在，请检查请求路径。")
        if full_path:
            candidate = (resolved_static / full_path).resolve()
            # 防目录穿越：只允许命中静态目录内的真实文件
            if resolved_static in candidate.parents and candidate.is_file():
                return FileResponse(candidate)
        index = resolved_static / "index.html"
        if index.is_file():
            return FileResponse(index)
        raise NotFoundError(
            "前端资源尚未构建：请确认 frontend/ 已执行 npm run build，或使用开发服务器联调。"
        )


app = create_app()
