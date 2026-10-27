"""Local TimescaleDB reads for A-share widgets (galaxy-core data layer).

Direct asyncpg reads against the ``galaxy`` database (same GALAXY_PG_*
env as AmazingDataSource). Ported from the legacy flat ``fin_data/_db``
module into the ``openbb_app`` package.
"""

import asyncio
import concurrent.futures
from datetime import date as _date

import asyncpg
import pandas as pd

from openbb_app.core.amazingdata_source import _connect_kwargs


async def _fetch(sql: str, *args):
    conn = await asyncpg.connect(**_connect_kwargs())
    try:
        return await conn.fetch(sql, *args)
    finally:
        await conn.close()


async def _fetchrow(sql: str, *args):
    conn = await asyncpg.connect(**_connect_kwargs())
    try:
        return await conn.fetchrow(sql, *args)
    finally:
        await conn.close()


def _run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def to_records(df):
    """DataFrame -> JSON-safe records (NaN/NaT/inf -> None, dates -> ISO)."""
    import datetime as _dt
    import math

    if df is None or len(df) == 0:
        return []
    df = df.replace([float("inf"), float("-inf")], None)
    recs = df.to_dict(orient="records")
    for r in recs:
        for k, v in list(r.items()):
            if v is None:
                continue
            if isinstance(v, float) and (
                math.isnan(v) or math.isinf(v) or pd.isna(v)
            ):
                r[k] = None
            elif isinstance(v, (_dt.date, _dt.datetime, pd.Timestamp)):
                r[k] = v.isoformat()
            elif hasattr(v, "isoformat"):
                try:
                    r[k] = v.isoformat()
                except Exception:
                    r[k] = str(v)
    for r in recs:
        for k, v in list(r.items()):
            try:
                if pd.isna(v) and v is not None:
                    r[k] = None
            except Exception:
                pass
    return recs


def _to_date(v: str) -> _date:
    return _date(*[int(x) for x in v.split("-")])


def fetch_profile(symbol_f: str) -> pd.DataFrame:
    """One row from stock_basic."""
    row = _run(_fetchrow("SELECT * FROM stock_basic WHERE symbol = $1 LIMIT 1", symbol_f))
    if row is None:
        return pd.DataFrame()
    return pd.DataFrame([dict(row)])


def fetch_industry_valuation(
    index_code: str | None, start_date: str, end_date: str, limit: int
) -> pd.DataFrame:
    """Industry index daily bars with PB/PE."""
    if index_code:
        rows = _run(_fetch(
            "SELECT trade_date, index_code, open, high, low, close, volume, amount,"
            " pb, pe FROM industry_daily WHERE index_code = $1"
            " AND trade_date >= $2 AND trade_date <= $3"
            " ORDER BY trade_date DESC LIMIT $4",
            index_code, _to_date(start_date), _to_date(end_date), limit,
        ))
    else:
        rows = _run(_fetch(
            "SELECT trade_date, index_code, close, pb, pe FROM industry_daily"
            " WHERE trade_date >= $1 AND trade_date <= $2"
            " ORDER BY trade_date DESC, index_code LIMIT $3",
            _to_date(start_date), _to_date(end_date), limit,
        ))
    if not rows:
        return pd.DataFrame(columns=["trade_date", "index_code", "close", "pb", "pe"])
    return pd.DataFrame([dict(r) for r in rows])


def fetch_sector_flow(trade_date: str | None, limit: int) -> pd.DataFrame:
    """Sector fund-flow snapshot."""
    if trade_date:
        rows = _run(_fetch(
            "SELECT * FROM akshare_sector_fund_flow_daily WHERE trade_date = $1"
            " ORDER BY main_net_amount DESC NULLS LAST LIMIT $2",
            _to_date(trade_date), limit,
        ))
    else:
        rows = _run(_fetch(
            "SELECT * FROM akshare_sector_fund_flow_daily"
            " ORDER BY trade_date DESC, main_net_amount DESC NULLS LAST LIMIT $1",
            limit,
        ))
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(r) for r in rows])


def fetch_lhb(symbol_f: str, limit: int) -> pd.DataFrame:
    """Long-hu-bang records for one stock, newest first."""
    rows = _run(_fetch(
        "SELECT trade_date, security_name, trader_name, flow_mark,"
        " reason_type_name, change_range, buy_amount, sell_amount,"
        " total_amount, total_volume FROM long_hu_bang WHERE market_code = $1"
        " ORDER BY trade_date DESC LIMIT $2",
        symbol_f, limit,
    ))
    if not rows:
        return pd.DataFrame(columns=[
            "trade_date", "security_name", "trader_name", "flow_mark",
            "reason_type_name", "change_range", "buy_amount", "sell_amount",
            "total_amount", "total_volume",
        ])
    return pd.DataFrame([dict(r) for r in rows])


def fetch_block_trade(symbol_f: str, limit: int) -> pd.DataFrame:
    """Block trading records for one stock, newest first."""
    rows = _run(_fetch(
        "SELECT trade_date, b_buyer_name, b_seller_name, b_share_price,"
        " b_share_volume, b_share_amount FROM block_trading WHERE market_code = $1"
        " ORDER BY trade_date DESC LIMIT $2",
        symbol_f, limit,
    ))
    if not rows:
        return pd.DataFrame(columns=[
            "trade_date", "b_buyer_name", "b_seller_name", "b_share_price",
            "b_share_volume", "b_share_amount",
        ])
    return pd.DataFrame([dict(r) for r in rows])


def fetch_margin(symbol_f: str, limit: int) -> pd.DataFrame:
    """Margin trading daily detail for one stock, newest first."""
    rows = _run(_fetch(
        "SELECT trade_date, borrow_money_balance, purch_with_borrow_money,"
        " repayment_of_borrow_money, sec_lending_balance, sales_of_borrowed_sec,"
        " repayment_of_borrow_sec, margin_trade_balance"
        " FROM margin_detail_daily WHERE market_code = $1"
        " ORDER BY trade_date DESC LIMIT $2",
        symbol_f, limit,
    ))
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(r) for r in rows])


def fetch_statements(table: str, symbol_f: str, period: str, limit: int) -> pd.DataFrame:
    """Latest N reporting periods (newest first).

    statement_type='1' = consolidated. period 'annual' -> Dec rows only.
    """
    if period == "annual":
        rows = _run(_fetch(
            f"SELECT * FROM {table} WHERE symbol = $1 AND statement_type = '1'"
            " AND EXTRACT(MONTH FROM reporting_period) = 12"
            " ORDER BY reporting_period DESC LIMIT $2",
            symbol_f, limit,
        ))
    else:
        rows = _run(_fetch(
            f"SELECT * FROM {table} WHERE symbol = $1 AND statement_type = '1'"
            " ORDER BY reporting_period DESC LIMIT $2",
            symbol_f, limit,
        ))
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(r) for r in rows])
