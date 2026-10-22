"""
缓存相关异常类定义
"""

from .base import GalaxyDBBridgeError


class CacheError(GalaxyDBBridgeError):
    """缓存错误基类"""

    def __init__(
        self, message: str, operation: str = None, key: str = None, *args, **kwargs
    ):
        super().__init__(message, *args)
        self.operation = operation
        self.key = key


class CacheConnectionError(CacheError):
    """缓存连接错误"""

    def __init__(self, connection_info: str, message: str = None, *args, **kwargs):
        message = message or f"缓存连接失败: {connection_info}"
        super().__init__(message, operation="connect", key=None, *args, **kwargs)
        self.connection_info = connection_info


class CacheOperationError(CacheError):
    """缓存操作错误"""

    def __init__(
        self,
        operation: str,
        key: str,
        reason: str = None,
        message: str = None,
        *args,
        **kwargs,
    ):
        message = message or f"缓存操作失败: {operation} for key {key}"
        super().__init__(message, operation=operation, key=key, *args, **kwargs)
        self.reason = reason
