"""错误模型：7 类 error_class + 面向用户的中文 message + model_seen。

error_class 契约见 openapi.yaml components.schemas.ConnectionTestResult 与 SPEC §5。
它最初是为「LLM 连通性分类」定义的，本项目将其统一作为**所有错误响应**的分类字段，
因此每个错误体都必须带上它（取值必须是下列 7 类之一）。

错误码分段：
  4000  参数/请求校验失败
  4010  未认证（缺令牌 / 令牌无效）
  4031  内容审核命中拦截
  4040  资源不存在
  4090  状态冲突（如会话正忙）
  4290  触发限流
  5000  内部错误
  5010  端点尚未实现（本轮占位）
  5021  LLM 上游不可达
"""

from __future__ import annotations

from enum import StrEnum


class ErrorClass(StrEnum):
    """七类错误分类 —— 对外契约，不得增删。"""

    model_not_found = "model_not_found"
    endpoint_invalid = "endpoint_invalid"
    auth_failed = "auth_failed"
    quota_exhausted = "quota_exhausted"
    network_unreachable = "network_unreachable"
    timeout = "timeout"
    unknown = "unknown"


class AppError(Exception):
    """所有业务异常的基类。全局异常处理器据此组装统一信封。"""

    code: int = 5000
    http_status: int = 500
    error_class: ErrorClass = ErrorClass.unknown

    def __init__(
        self,
        message: str,
        *,
        code: int | None = None,
        http_status: int | None = None,
        error_class: ErrorClass | None = None,
        model_seen: str | None = None,
        data: object = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.model_seen = model_seen
        self.data = data
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        if error_class is not None:
            self.error_class = error_class


class BadRequestError(AppError):
    """参数校验失败（400）。"""

    code = 4000
    http_status = 400
    error_class = ErrorClass.endpoint_invalid

    def __init__(self, message: str, **kw: object) -> None:
        super().__init__(message, **kw)


class AuthFailedError(AppError):
    """未认证 / 令牌无效（401）。AC-02。"""

    code = 4010
    http_status = 401
    error_class = ErrorClass.auth_failed

    def __init__(self, message: str = "未登录或会话已失效，请重新输入访问口令。", **kw: object) -> None:
        super().__init__(message, **kw)


class ModerationBlockedError(AppError):
    """内容审核命中（403）。"""

    code = 4031
    http_status = 403
    error_class = ErrorClass.unknown

    def __init__(self, message: str = "输入内容未通过内容审核，请调整后再试。", **kw: object) -> None:
        super().__init__(message, **kw)


class NotFoundError(AppError):
    """资源不存在（404）。"""

    code = 4040
    http_status = 404
    error_class = ErrorClass.model_not_found

    def __init__(self, message: str = "请求的资源不存在或已被删除。", **kw: object) -> None:
        super().__init__(message, **kw)


class ConflictError(AppError):
    """状态冲突（409），例如同一会话并发触发生成。"""

    code = 4090
    http_status = 409
    error_class = ErrorClass.unknown

    def __init__(self, message: str = "当前状态不允许该操作，请稍后重试。", **kw: object) -> None:
        super().__init__(message, **kw)


class RateLimitedError(AppError):
    """触发限流（429）。AC-03。"""

    code = 4290
    http_status = 429
    error_class = ErrorClass.auth_failed

    def __init__(self, message: str, *, retry_after: int | None = None, **kw: object) -> None:
        self.retry_after = retry_after
        super().__init__(message, **kw)


class UnimplementedError(AppError):
    """端点尚未实现（501）。本轮占位：路径/方法/参数已对齐 openapi.yaml。"""

    code = 5010
    http_status = 501
    error_class = ErrorClass.unknown

    def __init__(self, what: str, **kw: object) -> None:
        message = (
            f"{what}尚未启用：本轮只交付「可部署最小闭环」（部署 + 健康检查 + 访问控制），"
            "该端点的业务逻辑将在下一轮实现。"
        )
        super().__init__(message, **kw)


class UpstreamError(AppError):
    """上游 LLM / 图像服务错误，按 error_class 归类。"""

    code = 5021
    http_status = 502
    error_class = ErrorClass.network_unreachable

    def __init__(
        self,
        message: str,
        *,
        error_class: ErrorClass = ErrorClass.network_unreachable,
        model_seen: str | None = None,
        **kw: object,
    ) -> None:
        super().__init__(message, error_class=error_class, model_seen=model_seen, **kw)
