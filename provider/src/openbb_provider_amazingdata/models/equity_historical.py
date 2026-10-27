"""AmazingData Equity Historical fetcher (DB-backed).

Reads ``obb_equity_historical`` view (migration 29):
symbol/date aligned to OpenBB ``EquityHistoricalData`` standard model,
vwap derived as amount/volume in-view (D5).
"""

import asyncio
import concurrent.futures
from datetime import date, datetime
from typing import Any

import asyncpg
from dateutil.relativedelta import relativedelta
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_historical import (
    EquityHistoricalData,
    EquityHistoricalQueryParams,
)
from openbb_core.provider.utils.descriptions import QUERY_DESCRIPTIONS
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field


class AmazingDataEquityHistoricalQueryParams(EquityHistoricalQueryParams):
    """AmazingData Equity Historical query (DB-backed)."""

    __json_schema_extra__ = {
        "symbol": {"multiple_items_allowed": True},
    }

    interval: str | None = Field(
        default="day",
        description=QUERY_DESCRIPTIONS.get("interval", ""),
    )


class AmazingDataEquityHistoricalData(EquityHistoricalData):
    """AmazingData Equity Historical data (column names already aligned in-view)."""

    amount: float | None = Field(
        default=None,
        description="Turnover in CNY (single-exit compatibility with the SQL path).",
    )


async def _fetch_rows(
    conn: asyncpg.Connection,
    symbol: str,
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    """Single-symbol range read from the view."""
    rows = await conn.fetch(
        """
        SELECT symbol, date, open, high, low, close, volume, amount, vwap
        FROM obb_equity_historical
        WHERE symbol = $1 AND date >= $2 AND date <= $3
        ORDER BY date
        """,
        symbol,
        start,
        end,
    )
    return [dict(r) for r in rows]


def _connect_kwargs(credentials: dict[str, str] | None) -> dict[str, Any]:
    """PG connection kwargs: credentials dict > env defaults (local galaxy)."""
    import os

    creds = credentials or {}
    return {
        "host": creds.get("pg_host") or os.getenv("GALAXY_PG_HOST", "127.0.0.1"),
        "port": int(creds.get("pg_port") or os.getenv("GALAXY_PG_PORT", "5432")),
        "database": creds.get("pg_db") or os.getenv("GALAXY_PG_DB", "galaxy"),
        "user": creds.get("pg_user") or os.getenv("GALAXY_PG_USER", "postgres"),
        "password": creds.get("pg_password") or os.getenv("GALAXY_PG_PASSWORD", "postgres"),
    }


class AmazingDataEquityHistoricalFetcher(
    Fetcher[
        AmazingDataEquityHistoricalQueryParams,
        list[AmazingDataEquityHistoricalData],
    ]
):
    """Fetch A-share historical prices from local TimescaleDB."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> AmazingDataEquityHistoricalQueryParams:
        """Fill default date range (1y) like other providers."""
        transformed = dict(params)
        now = datetime.now().date()
        if transformed.get("start_date") is None:
            transformed["start_date"] = now - relativedelta(years=1)
        if transformed.get("end_date") is None:
            transformed["end_date"] = now
        return AmazingDataEquityHistoricalQueryParams(**transformed)

    @staticmethod
    def extract_data(
        query: AmazingDataEquityHistoricalQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Sync entry: async PG read runs in a dedicated thread.

        The OpenBB query executor may already run an event loop in this
        thread, so asyncio.run() here would raise. A fresh thread has
        no loop and can own one safely.
        """
        symbols = query.symbol if isinstance(query.symbol, list) else [query.symbol]
        conn_kwargs = _connect_kwargs(credentials)

        def _run() -> list[dict]:
            return asyncio.run(_extract_async(query, symbols, conn_kwargs))

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_run).result()

    @staticmethod
    def transform_data(
        query: AmazingDataEquityHistoricalQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[AmazingDataEquityHistoricalData]:
        """Validate rows into standard model."""
        return [AmazingDataEquityHistoricalData.model_validate(d) for d in data]


async def _extract_async(
    query: AmazingDataEquityHistoricalQueryParams,
    symbols: list[str],
    conn_kwargs: dict[str, Any],
) -> list[dict]:
    """Concurrent per-symbol reads over one connection."""
    conn = await asyncpg.connect(**conn_kwargs)
    try:
        results = await asyncio.gather(
            *(_fetch_rows(conn, s, query.start_date, query.end_date) for s in symbols)
        )
    finally:
        await conn.close()
    flat = [row for rows in results for row in rows]
    if not flat:
        raise EmptyDataError()
    return flat
