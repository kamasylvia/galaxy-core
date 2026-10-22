"""K线数据提供者端口."""

from datetime import date
from typing import Protocol, runtime_checkable

from galaxy_core.domain.value_objects import Interval, KlineBar, StockInfo


@runtime_checkable
class KlineProviderPort(Protocol):
    """K线数据提供者接口 — 对接 AmazingData SDK（async，to_thread 集中在 adapter）."""

    async def get_kline(
        self,
        symbols: list[str],
        interval: Interval,
        start: str,
        end: str,
    ) -> list[KlineBar]: ...

    async def get_stock_list(self, market: str) -> list[StockInfo]: ...

    async def get_listing_dates(self, symbols: list[str]) -> dict[str, date]: ...
