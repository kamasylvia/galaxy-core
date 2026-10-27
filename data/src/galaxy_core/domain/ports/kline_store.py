"""K线数据存储端口."""

from datetime import date
from typing import Protocol, runtime_checkable

from galaxy_core.domain.value_objects import Interval, KlineBar


@runtime_checkable
class KlineStorePort(Protocol):
    """K线数据存储接口 — 对接 PostgreSQL/TimescaleDB（async）."""

    async def save_kline(
        self,
        data: list[KlineBar],
        interval: Interval,
    ) -> None: ...

    async def get_kline(
        self,
        symbol: str,
        interval: Interval,
        start: str,
        end: str,
    ) -> list[KlineBar]: ...

    async def get_last_sync_dates(
        self,
        symbols: list[str],
        interval: Interval,
    ) -> dict[str, date | None]: ...

    async def set_last_sync_dates(
        self,
        symbol_dates: dict[str, date],
        interval: Interval,
    ) -> None: ...
