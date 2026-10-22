"""AmazingData data source (DB-backed A-share provider).

Reads K-line from local TimescaleDB ``kline_day``/``kline_week``/...
via asyncpg (same GALAXY_PG_* env as the legacy provider package).
Implements the upstream ``DataSource`` ABC so it slots into
``DataSourceManager`` as the sole source (akshare/tushare/yfinance
dropped per pure-amazingdata decision).
"""

import asyncio
import concurrent.futures
import logging
import os
from typing import Any

from openbb_app.core.data_source import DataSource

logger = logging.getLogger(__name__)


def _connect_kwargs() -> dict[str, Any]:
    return {
        "host": os.getenv("GALAXY_PG_HOST", "127.0.0.1"),
        "port": int(os.getenv("GALAXY_PG_PORT", "5432")),
        "database": os.getenv("GALAXY_PG_DB", "galaxy"),
        "user": os.getenv("GALAXY_PG_USER", "postgres"),
        "password": os.getenv("GALAXY_PG_PASSWORD", "postgres"),
    }


_INTERVAL_TABLE = {
    "1d": "kline_day",
    "1w": "kline_week",
    "1m": "kline_month",
}


async def _fetch_bars(
    symbol: str, start_date: str, end_date: str, interval: str
) -> list[dict]:
    import asyncpg
    from datetime import date as _date

    def _to_date(v: str) -> _date:
        return _date(*[int(x) for x in v.split("-")])

    table = _INTERVAL_TABLE.get(interval, "kline_day")
    conn = await asyncpg.connect(**_connect_kwargs())
    try:
        rows = await conn.fetch(
            f"""
            SELECT trade_time AS date, open, high, low, close, volume, amount
            FROM {table}
            WHERE symbol = $1 AND trade_time >= $2 AND trade_time <= $3
            ORDER BY trade_time
            """,
            symbol,
            _to_date(start_date),
            _to_date(end_date),
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


class AmazingDataSource(DataSource):
    """AmazingData DB-backed source (local TimescaleDB, sole provider)."""

    @property
    def provider_name(self) -> str:
        return "amazingdata"

    def _normalize_symbol(self, symbol: str) -> str:
        # DataSourceManager passes symbol through; normalize SH/SZ/BJ suffix here.
        try:
            from mysharelib.tools import normalize_symbol

            _, symbol_f, market = normalize_symbol(symbol)
            if market in ("SH", "SZ", "BJ"):
                return symbol_f
        except Exception:
            pass
        return symbol

    def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1d",
    ) -> list[dict[str, Any]]:
        processed = self._normalize_symbol(symbol)
        logger.info("Fetching data from amazingdata for %s (original: %s)", processed, symbol)

        def _run() -> list[dict]:
            return asyncio.run(_fetch_bars(processed, start_date, end_date, interval))

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            rows = pool.submit(_run).result()

        out: list[dict[str, Any]] = []
        for r in rows:
            d = r["date"]
            out.append(
                {
                    "date": d.isoformat() if hasattr(d, "isoformat") else str(d),
                    "open": r["open"],
                    "high": r["high"],
                    "low": r["low"],
                    "close": r["close"],
                    "volume": r["volume"],
                    "amount": r.get("amount"),
                    "interval": interval,
                }
            )
        return out
