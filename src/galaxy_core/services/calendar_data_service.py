"""交易日历数据同步服务 — 通过端口接口协调日历同步流程."""

import logging

from galaxy_core.domain.ports.calendar_provider import CalendarProviderPort
from galaxy_core.domain.ports.calendar_store import CalendarStorePort

logger = logging.getLogger(__name__)


class CalendarDataService:
    """交易日历数据同步服务.

    协调日历获取 -> 数据库保存的流程。
    通过端口接口与外部交互，不依赖具体 adapter 实现。
    """

    def __init__(
        self,
        calendar_provider: CalendarProviderPort,
        calendar_store: CalendarStorePort,
    ) -> None:
        self._provider = calendar_provider
        self._store = calendar_store

    async def sync(self, year: int) -> int:
        """同步指定年份的交易日历.

        Args:
            year: 年份

        Returns:
            同步的交易日数量
        """
        logger.info(f"开始同步 {year} 年交易日历...")

        # 1. 从 provider 获取日历
        trading_dates = await self._provider.get_trading_calendar(year)

        if not trading_dates:
            logger.warning(f"{year} 年交易日历为空")
            return 0

        # 2. 保存到 store
        await self._store.save_calendar(trading_dates)

        logger.info(f"同步完成: {year} 年 {len(trading_dates)} 个交易日")
        return len(trading_dates)
