"""交易日历存储端口."""

from datetime import date
from typing import Protocol, runtime_checkable


@runtime_checkable
class CalendarStorePort(Protocol):
    """交易日历存储接口 — 对接 PostgreSQL（async）."""

    async def save_calendar(self, dates: list[date]) -> None: ...

    async def get_trading_calendar(self, year: int) -> list[date]: ...

    async def get_trading_days(self, start_date: date, end_date: date) -> list[date]:
        """获取指定日期范围内的交易日列表.

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            该范围内 is_trading_day=True 的日期列表（升序）
        """
        ...
