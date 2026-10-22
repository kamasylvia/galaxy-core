"""交易日历提供者端口."""

from datetime import date
from typing import Protocol, runtime_checkable


@runtime_checkable
class CalendarProviderPort(Protocol):
    """交易日历提供者接口 — 对接 AmazingData SDK（async，to_thread 集中在 adapter）."""

    async def get_trading_calendar(self, year: int) -> list[date]: ...
