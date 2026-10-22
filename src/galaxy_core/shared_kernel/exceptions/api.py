"""
API 相关异常类定义
"""

from .base import GalaxyDBBridgeError


class APIError(GalaxyDBBridgeError):
    """API 错误基类"""

    def __init__(
        self,
        message: str,
        endpoint: str = None,
        status_code: int = None,
        *args,
        **kwargs,
    ):
        super().__init__(message, *args)
        self.endpoint = endpoint
        self.status_code = status_code


class APITimeoutError(APIError):
    """API 超时错误"""

    def __init__(
        self,
        endpoint: str,
        timeout_duration: float,
        message: str = None,
        *args,
        **kwargs,
    ):
        message = message or f"API 请求超时: {endpoint} (超时时间: {timeout_duration}s)"
        super().__init__(message, endpoint=endpoint, status_code=None, *args, **kwargs)
        self.timeout_duration = timeout_duration


class APIRateLimitError(APIError):
    """API 限流错误"""

    def __init__(
        self,
        endpoint: str,
        retry_after: int = None,
        message: str = None,
        *args,
        **kwargs,
    ):
        message = message or f"API 请求频率超限: {endpoint}"
        super().__init__(message, endpoint=endpoint, status_code=429, *args, **kwargs)
        self.retry_after = retry_after


class APIConnectionError(APIError):
    """API 连接错误"""

    def __init__(
        self, endpoint: str, reason: str = None, message: str = None, *args, **kwargs
    ):
        message = message or f"API 连接失败: {endpoint}"
        super().__init__(message, endpoint=endpoint, status_code=None, *args, **kwargs)
        self.reason = reason


class APIResponseError(APIError):
    """API 响应错误"""

    def __init__(
        self,
        endpoint: str,
        status_code: int,
        response_body: str = None,
        message: str = None,
        *args,
        **kwargs,
    ):
        message = message or f"API 响应错误: {endpoint} (状态码: {status_code})"
        super().__init__(
            message, endpoint=endpoint, status_code=status_code, *args, **kwargs
        )
        self.response_body = response_body


class EmptyResponseError(APIError):
    """API 返回空响应但应有数据(窗口含交易日).

    典型场景:AmazingData 凌晨时段性返空(数据存在但 API 返 0 条)。
    与 SDKError 区分:这不是 SDK bug,是 API 端时段性问题,重试可恢复。
    调用方(scheduler/retry_handler)应重试;CLI 用户应判断是否手动补数。
    与 APIResponseError 区分:无 HTTP 状态码,属语义错误(应有数据但空)。
    """

    def __init__(
        self,
        message: str,
        endpoint: str = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            message, endpoint=endpoint, status_code=None, *args, **kwargs
        )


class SDKError(APIError):
    """SDK 内部错误（如 AmazingData 已知 bug）"""

    def __init__(
        self,
        message: str,
        endpoint: str = None,
        original_error: Exception = None,
        *args,
        **kwargs,
    ):
        super().__init__(message, endpoint=endpoint, status_code=None, *args, **kwargs)
        self.original_error = original_error


class SDKBugError(GalaxyDBBridgeError):
    """SDK 已知 bug 导致的错误（如 NoneType TypeError）.

    与 SDKError 平级，表示 SDK 的已知 bug 而非一般 SDK 错误。
    调用方遇到此异常应跳过当前操作但不缓存空结果（下次同步会重试）。
    """

    def __init__(
        self,
        message: str,
        original_error: Exception = None,
        *args,
        **kwargs,
    ):
        super().__init__(message, *args)
        self.original_error = original_error
