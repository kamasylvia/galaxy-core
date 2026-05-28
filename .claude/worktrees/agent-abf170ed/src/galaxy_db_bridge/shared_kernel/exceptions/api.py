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
