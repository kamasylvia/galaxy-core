"""
基础异常类定义
"""


class GalaxyDBBridgeError(Exception):
    """Galaxy DB Bridge 项目所有异常的基类"""

    def __init__(self, message: str, *args, **kwargs):
        super().__init__(message, *args)
        self.message = message


class ConfigurationError(GalaxyDBBridgeError):
    """配置错误异常"""

    def __init__(self, message: str, config_key: str = None, *args, **kwargs):
        super().__init__(message, *args)
        self.config_key = config_key
