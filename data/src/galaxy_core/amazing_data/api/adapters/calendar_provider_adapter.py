"""交易日历提供者适配器 — 包装 AmazingDataClient 为 CalendarProviderPort."""

import asyncio
import logging
from datetime import date, datetime

from galaxy_core.amazing_data.api.client import AmazingDataClient
from galaxy_core.domain.ports.calendar_provider import CalendarProviderPort

logger = logging.getLogger(__name__)


class CalendarProviderAdapter:
    """CalendarProviderPort 实现 — 包装 AmazingDataClient 同步 SDK 为 async 接口.

    asyncio.to_thread() 集中在此 adapter 层，应用层代码完全异步。
    """

    def __init__(self, client: AmazingDataClient) -> None:
        self._client = client

    async def get_trading_calendar(self, year: int) -> list[date]:
        """获取指定年份的交易日历.

        Args:
            year: 年份

        Returns:
            该年份的交易日列表 (date 对象)
        """
        # asyncio.to_thread 包装同步 SDK 调用
        # SDK 返回 list[datetime] 或 list[int]，取决于 data_type 参数
        raw_calendar = await asyncio.to_thread(
            self._client.get_trading_calendar,
            data_type="datetime",
        )

        # 转换为 list[date] 并按年份过滤
        trading_dates: list[date] = []
        for item in raw_calendar:
            if isinstance(item, datetime):
                d = item.date()
            elif isinstance(item, date):
                d = item
            elif isinstance(item, int):
                # int 格式: YYYYMMDD
                d = datetime.strptime(str(item)[:8], "%Y%m%d").date()
            else:
                logger.warning(f"无法解析日历条目: {item} (type={type(item)})")
                continue

            if d.year == year:
                trading_dates.append(d)

        logger.debug(f"获取到 {year} 年 {len(trading_dates)} 个交易日")
        return trading_dates
