"""延迟加载的AmazingData客户端."""

import logging
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from .client import AmazingDataClient

logger = logging.getLogger(__name__)


class LazyAmazingDataClient:
    """延迟加载的AmazingData客户端.

    首次访问时自动从配置初始化客户端.
    """

    def __init__(self):
        self._instance: AmazingDataClient | None = None
        self._initialized = False

    def __getattr__(self, name: str):
        # 首次访问任何属性时初始化客户端
        if not self._initialized:
            logger.info("首次访问AmazingDataClient，正在从配置初始化...")
            from .client import AmazingDataClient

            self._instance = AmazingDataClient.from_config()
            self._initialized = True

        # 返回实例的属性
        return getattr(self._instance, name)

    def force_initialize(self) -> AmazingDataClient:
        """强制初始化客户端."""
        if not self._initialized:
            from .client import AmazingDataClient

            self._instance = AmazingDataClient.from_config()
            self._initialized = True
        # return self._instance
        return cast(AmazingDataClient, self._instance)

    def get_instance(self) -> AmazingDataClient:
        """获取客户端实例（如果尚未初始化则进行初始化）."""
        if not self._initialized:
            self.force_initialize()
        return cast(AmazingDataClient, self._instance)


# 全局延迟加载客户端实例
amazing_data_client = LazyAmazingDataClient()
