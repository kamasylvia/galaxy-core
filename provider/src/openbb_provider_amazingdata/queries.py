"""AM-specific data queries (DB-backed) - the single copy of these SQLs.

OpenBB-core 1.6 的 Provider 不支持 provider 级自定义 router(Router 在平台侧,
无注入点),而这些数据面(industry_daily / 板块资金流 / 龙虎榜 / 大宗 / 两融)
没有标准模型可挂 fetcher。单出口的落地形态:**查询与口径转换只活在 provider
包一份**,api 侧是薄壳;待 openbb-core 2.x 解钉(mysharelib 现钉 <2.0)后,
在此补 Router 壳即可自动进 OpenBB 标准 API。

接口约定:入参 str YYYY-MM-DD 或 date;返回 list[dict](键 = SQL 列名,
与 api 原 galaxy_db 输出同形)。
"""

import asyncio
import concurrent.futures
from datetime import date as _date
from typing import Any

import asyncpg

from openbb_provider_amazingdata.models.equity_historical import _connect_kwargs


def _d(value: str | _date | None) -> _date | None:
    if value is None or isinstance(value, _date):
        return value
    return _date.fromisoformat(str(value))


async def _fetch_all(sql: str, *args) -> list[dict[str, Any]]:
    conn = await asyncpg.connect(**_connect_kwargs(None))
    try:
        rows = await conn.fetch(sql, *args)
        return [dict(r) for r in rows]
    finally:
        await conn.close()


def _run(sql: str, *args) -> list[dict[str, Any]]:
    """Sync entry: fresh loop in a worker thread (uvicorn request-thread safe)."""

    def _go() -> list[dict[str, Any]]:
        return asyncio.run(_fetch_all(sql, *args))

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_go).result()


async def industry_valuation(index_code, start, end, limit):
    """行业指数日行情 + PB/PE(industry_daily)."""
    if index_code:
        return await _fetch_all(
            "SELECT trade_date, index_code, open, high, low, close, volume, amount,"
            " pb, pe FROM industry_daily WHERE index_code = $1"
            " AND trade_date >= $2 AND trade_date <= $3"
            " ORDER BY trade_date DESC LIMIT $4",
            index_code, _d(start), _d(end), limit,
        )
    return await _fetch_all(
        "SELECT trade_date, index_code, close, pb, pe FROM industry_daily"
        " WHERE trade_date >= $1 AND trade_date <= $2"
        " ORDER BY trade_date DESC, index_code LIMIT $3",
        _d(start), _d(end), limit,
    )


async def sector_flow(trade_date, limit):
    """板块主力资金净流入日快照(akshare_sector_fund_flow_daily)."""
    if trade_date:
        return await _fetch_all(
            "SELECT * FROM akshare_sector_fund_flow_daily WHERE trade_date = $1"
            " ORDER BY main_net_amount DESC NULLS LAST LIMIT $2",
            _d(trade_date), limit,
        )
    return await _fetch_all(
        "SELECT * FROM akshare_sector_fund_flow_daily"
        " ORDER BY trade_date DESC, main_net_amount DESC NULLS LAST LIMIT $1",
        limit,
    )


async def lhb(symbol, limit):
    """个股龙虎榜席位明细(long_hu_bang, market_code = symbol)."""
    return await _fetch_all(
        "SELECT trade_date, security_name, trader_name, flow_mark,"
        " reason_type_name, change_range, buy_amount, sell_amount,"
        " total_amount, total_volume FROM long_hu_bang WHERE market_code = $1"
        " ORDER BY trade_date DESC LIMIT $2",
        symbol, limit,
    )


async def block_trade(symbol, limit):
    """个股大宗交易明细(block_trading)."""
    return await _fetch_all(
        "SELECT trade_date, b_buyer_name, b_seller_name, b_share_price,"
        " b_share_volume, b_share_amount FROM block_trading WHERE market_code = $1"
        " ORDER BY trade_date DESC LIMIT $2",
        symbol, limit,
    )


async def margin_detail(symbol, limit):
    """个股两融明细(margin_detail_daily)."""
    return await _fetch_all(
        "SELECT trade_date, borrow_money_balance, purch_with_borrow_money,"
        " repayment_of_borrow_money, sec_lending_balance, sales_of_borrowed_sec,"
        " repayment_of_borrow_sec, margin_trade_balance"
        " FROM margin_detail_daily WHERE market_code = $1"
        " ORDER BY trade_date DESC LIMIT $2",
        symbol, limit,
    )


def sync(coro):
    """Run one of the async queries above from sync context."""

    def _go():
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_go).result()
