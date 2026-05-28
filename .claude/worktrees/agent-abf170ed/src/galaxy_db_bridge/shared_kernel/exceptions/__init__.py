"""
异常类模块 - 统一导出所有异常类
"""

from .base import GalaxyDBBridgeError, ConfigurationError
from .validation import (
    ValidationError,
    SymbolFormatError,
    SymbolNotFoundError,
    SecurityTypeError,
)
from .api import (
    APIError,
    APITimeoutError,
    APIRateLimitError,
    APIConnectionError,
    APIResponseError,
)
from .cache import CacheError, CacheConnectionError, CacheOperationError

__all__ = [
    # 基础异常
    "GalaxyDBBridgeError",
    "ConfigurationError",
    # 验证异常
    "ValidationError",
    "SymbolFormatError",
    "SymbolNotFoundError",
    "SecurityTypeError",
    # API 异常
    "APIError",
    "APITimeoutError",
    "APIRateLimitError",
    "APIConnectionError",
    "APIResponseError",
    # 缓存异常
    "CacheError",
    "CacheConnectionError",
    "CacheOperationError",
]
