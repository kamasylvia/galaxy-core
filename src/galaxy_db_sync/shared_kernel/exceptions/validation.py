"""
验证相关异常类定义
"""

from .base import GalaxyDBBridgeError


class ValidationError(GalaxyDBBridgeError):
    """验证错误基类"""

    def __init__(
        self, message: str, field: str = None, value: str = None, *args, **kwargs
    ):
        super().__init__(message, *args)
        self.field = field
        self.value = value


class SymbolFormatError(ValidationError):
    """证券代码格式错误"""

    def __init__(self, symbol: str, message: str = None, *args, **kwargs):
        message = message or f"证券代码格式错误: {symbol}"
        super().__init__(message, field="symbol", value=symbol, *args, **kwargs)


class SymbolNotFoundError(ValidationError):
    """证券代码不存在错误"""

    def __init__(self, symbol: str, message: str = None, *args, **kwargs):
        message = message or f"证券代码不存在: {symbol}"
        super().__init__(message, field="symbol", value=symbol, *args, **kwargs)


class SecurityTypeError(ValidationError):
    """SecurityType 错误"""

    def __init__(self, security_type: str, message: str = None, *args, **kwargs):
        message = message or f"SecurityType 错误: {security_type}"
        super().__init__(
            message, field="security_type", value=security_type, *args, **kwargs
        )
