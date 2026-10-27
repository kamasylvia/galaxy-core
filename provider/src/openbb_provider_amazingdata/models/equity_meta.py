"""Equity meta fetchers: quote / profile / search (DB-backed).

单出口第三批(2026-10-27):
- EquityQuote:最近日线合成现价/成交量 + 250 根 52 周高低(与 api 原
  「400 天 bars 取 last 250」语义一致,SQL 内一次算齐)+ stock_basic 名称;
- Profile:stock_basic 单行;
- Search:stock_basic 列表(query 不做模糊匹配——api 的 /tickers 语义是
  全列表,列 symbol/security_name/comp_name)。

A 股字段以扩展字段随标准模型输出。
"""

import asyncio
import concurrent.futures
from datetime import date
from typing import Any

import asyncpg
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_quote import (
    EquityQuoteData,
    EquityQuoteQueryParams,
)
from openbb_core.provider.standard_models.equity_info import (
    EquityInfoData,
    EquityInfoQueryParams,
)
from openbb_core.provider.standard_models.equity_search import (
    EquitySearchData,
    EquitySearchQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_provider_amazingdata.models.equity_historical import _connect_kwargs


async def _fetch_quote_rows(symbols: list[str]) -> list[dict[str, Any]]:
    conn = await asyncpg.connect(**_connect_kwargs(None))
    try:
        out: list[dict[str, Any]] = []
        for symbol in symbols:
            row = await conn.fetchrow(
                """
                SELECT b.symbol,
                       b.close   AS last_price,
                       b.volume  AS last_volume,
                       b.open    AS day_open,
                       b.high    AS day_high,
                       b.low     AS day_low,
                       w.week52_high,
                       w.week52_low,
                       s.security_name,
                       s.comp_name
                FROM kline_day b
                LEFT JOIN stock_basic s ON s.symbol = b.symbol
                LEFT JOIN LATERAL (
                    SELECT max(high) AS week52_high, min(low) AS week52_low
                    FROM (SELECT high, low FROM kline_day
                          WHERE symbol = $1 ORDER BY trade_time DESC LIMIT 250) t
                ) w ON true
                WHERE b.symbol = $1
                ORDER BY b.trade_time DESC LIMIT 1
                """,
                symbol,
            )
            if row:
                out.append(dict(row))
        return out
    finally:
        await conn.close()


async def _fetch_profile_row(symbol: str) -> dict[str, Any] | None:
    conn = await asyncpg.connect(**_connect_kwargs(None))
    try:
        row = await conn.fetchrow(
            """
            SELECT symbol, security_name, comp_name, listplate_name,
                   list_date, delist_date, is_listed
            FROM stock_basic WHERE symbol = $1 LIMIT 1
            """,
            symbol,
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def _fetch_search_rows(query: str) -> list[dict[str, Any]]:
    conn = await asyncpg.connect(**_connect_kwargs(None))
    try:
        rows = await conn.fetch(
            """
            SELECT symbol, security_name, comp_name FROM stock_basic
            WHERE symbol NOT LIKE '159%' AND symbol NOT LIKE '511%'
              AND symbol NOT LIKE '512%' AND symbol NOT LIKE '513%'
            ORDER BY symbol LIMIT 8000
            """
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


def _threaded(coro):
    """Sync entry: fresh loop in a worker thread (uvicorn request-thread safe)."""

    def _run():
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run).result()


def _normalize_bare(code: str) -> str:
    """裸 6 位数字补交易所后缀:6/9→.SH,0/2/3→.SZ,4/8→.BJ(其余原样)."""
    if len(code) == 6 and code.isdigit():
        if code[0] in ("6", "9"):
            return code + ".SH"
        if code[0] in ("0", "2", "3"):
            return code + ".SZ"
        if code[0] in ("4", "8"):
            return code + ".BJ"
    return code


def _symbols(query) -> list[str]:
    """拆 symbol 参数(list/逗号串,OpenBB 1.6 不代拆)+ 裸码补后缀."""
    raw = query.symbol if isinstance(query.symbol, list) else [query.symbol]
    out: list[str] = []
    for item in raw:
        for s in str(item).split(","):
            s = s.strip()
            if s:
                out.append(_normalize_bare(s))
    return out


# ---------------------------------------------------------------------------
# EquityQuote
# ---------------------------------------------------------------------------


class AmazingDataEquityQuoteQueryParams(EquityQuoteQueryParams):
    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}


class AmazingDataEquityQuoteData(EquityQuoteData):
    week52_high: float | None = Field(default=None, description="52 周最高")
    week52_low: float | None = Field(default=None, description="52 周最低")
    security_name: str | None = Field(default=None, description="证券简称")
    comp_name: str | None = Field(default=None, description="公司名称")


class AmazingDataEquityQuoteFetcher(
    Fetcher[AmazingDataEquityQuoteQueryParams, list[AmazingDataEquityQuoteData]]
):
    @staticmethod
    def transform_query(params: dict[str, Any]) -> AmazingDataEquityQuoteQueryParams:
        return AmazingDataEquityQuoteQueryParams(**params)

    @staticmethod
    def extract_data(query, credentials, **kwargs: Any) -> list[dict]:
        return _threaded(_fetch_quote_rows(_symbols(query)))

    @staticmethod
    def transform_data(query, data: list[dict], **kwargs: Any):
        if not data:
            raise EmptyDataError(f"no quote rows for {query.symbol}")
        return [AmazingDataEquityQuoteData(**r) for r in data]


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


class AmazingDataEquityInfoQueryParams(EquityInfoQueryParams):
    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": False}}


class AmazingDataEquityInfoData(EquityInfoData):
    security_name: str | None = Field(default=None, description="证券简称")
    comp_name: str | None = Field(default=None, description="公司名称")
    listplate_name: str | None = Field(default=None, description="上市板块")
    list_date: date | None = Field(default=None, description="上市日期")
    delist_date: date | None = Field(default=None, description="退市日期")
    is_listed: bool | None = Field(default=None, description="在市状态")


class AmazingDataEquityInfoFetcher(
    Fetcher[AmazingDataEquityInfoQueryParams, AmazingDataEquityInfoData]
):
    @staticmethod
    def transform_query(params: dict[str, Any]) -> AmazingDataEquityInfoQueryParams:
        return AmazingDataEquityInfoQueryParams(**params)

    @staticmethod
    def extract_data(query, credentials, **kwargs: Any) -> dict | None:
        return _threaded(_fetch_profile_row(_symbols(query)[0]))

    @staticmethod
    def transform_data(query, data: dict | None, **kwargs: Any):
        if not data:
            raise EmptyDataError(f"no profile row for {query.symbol}")
        return AmazingDataEquityInfoData(**data)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class AmazingDataEquitySearchQueryParams(EquitySearchQueryParams):
    """query 不做模糊匹配:语义为「universe 列表」(与 api /tickers 一致)."""


class AmazingDataEquitySearchData(EquitySearchData):
    security_name: str | None = Field(default=None, description="证券简称")
    comp_name: str | None = Field(default=None, description="公司名称")


class AmazingDataEquitySearchFetcher(
    Fetcher[AmazingDataEquitySearchQueryParams, list[AmazingDataEquitySearchData]]
):
    @staticmethod
    def transform_query(params: dict[str, Any]) -> AmazingDataEquitySearchQueryParams:
        return AmazingDataEquitySearchQueryParams(**params)

    @staticmethod
    def extract_data(query, credentials, **kwargs: Any) -> list[dict]:
        return _threaded(_fetch_search_rows(getattr(query, "query", "") or ""))

    @staticmethod
    def transform_data(query, data: list[dict], **kwargs: Any):
        if not data:
            raise EmptyDataError("no symbols")
        return [AmazingDataEquitySearchData(**r) for r in data]
