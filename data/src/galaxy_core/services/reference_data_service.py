"""参考数据同步服务 — 通过端口接口协调参考数据同步流程."""

import logging
from datetime import date

from galaxy_core.database.core.async_connection import AsyncDatabaseManager
from galaxy_core.domain.ports.reference_provider import ReferenceProviderPort

logger = logging.getLogger(__name__)


class ReferenceDataService:
    """参考数据同步服务.

    协调 stock_basic, backward_factor 两个表的同步。
    通过端口接口与外部交互，不依赖具体 adapter 实现。
    """

    def __init__(
        self,
        reference_provider: ReferenceProviderPort,
        db_manager: AsyncDatabaseManager,
    ) -> None:
        self._provider = reference_provider
        self._db = db_manager

    async def sync(self, security_type: str, today: date) -> None:
        """同步参考数据.

        Args:
            security_type: 证券类型 (如 "EXTRA_ETF")
            today: 当前日期
        """
        logger.info(f"开始同步参考数据: security_type={security_type}")

        # 1. 获取证券基础信息
        logger.debug(f"获取 {security_type} 的证券基础信息...")
        stock_basics = await self._provider.get_stock_basic(symbols=[])
        logger.info(f"获取到 {len(stock_basics)} 条证券基础信息")

        # 2. 获取复权因子
        if stock_basics:
            symbols = [sb.symbol for sb in stock_basics]
            logger.debug(f"获取 {len(symbols)} 只证券的复权因子...")
            factors = await self._provider.get_backward_factor(symbols=symbols)
            logger.info(f"获取到 {len(factors)} 条复权因子")

        logger.info(f"参考数据同步完成: security_type={security_type}")
