"""业务异常集中定义:统一错误响应体为 {code, message}。

HTTP 状态只在此处定义默认值,路由层不自行拼错误响应。
"""


class TradeWindsError(Exception):
    """业务异常基类。code 是稳定错误码,前端/调用方据此分支,不解析 message。"""

    code: str = "internal_error"
    status_code: int = 500

    def __init__(
        self, message: str, *, code: str | None = None, status_code: int | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(TradeWindsError):
    """资源不存在。路由层对跨用户访问也应抛此异常,不泄露存在性。"""

    code = "not_found"
    status_code = 404


class AuthError(TradeWindsError):
    """认证/鉴权失败。注册冲突等 409 场景通过 status_code 覆盖。"""

    code = "auth_failed"
    status_code = 401


class QuotaExceededError(TradeWindsError):
    """用户配额(主题数、LLM 用量等)已满。"""

    code = "quota_exceeded"
    status_code = 403


class LLMError(TradeWindsError):
    """LLM 调用在重试后仍失败(网络/限流/5xx)。"""

    code = "llm_unavailable"
    status_code = 503
