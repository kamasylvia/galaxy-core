"""A-share statements/profile from local TimescaleDB (pure AmazingData)."""

import logging

logger = logging.getLogger(__name__)

import pandas as pd
from mysharelib.tools import normalize_symbol

from openbb_app.core import galaxy_db as _db

_AMAZINGDATA_MARKETS = ("SH", "SZ", "BJ")


def get_news(ticker: str, limit: int = 10) -> pd.DataFrame:
    """个股新闻:东财搜索接口直调(纯 HTTP,无 akshare 依赖).详见 utils.get_news."""
    from openbb_app.core.utils import get_news as _get_news

    return _get_news(ticker, limit)


def get_tickers(exchange: str = "") -> list[dict]:
    """Available tickers, amazingdata only (local stock_basic)."""
    from openbb_app.core.utils import get_symbols

    return get_symbols(exchange)


_STATEMENT_COLS = {
    "income": ["period_ending", "fiscal_period", "总营收", "营业利润", "净利润", "基本每股收益"],
    "balance_sheet": ["period_ending", "fiscal_period", "股东权益", "总负债", "总资产"],
    "cash_flow": ["period_ending", "fiscal_period", "营业性现金流", "投资性现金流", "融资性现金流"],
}

_ALIAS = {
    "period_ending": "reporting_period",
    "fiscal_period": "statement_type",
    # income
    "总营收": "tot_opera_rev",
    "营业利润": "opera_profit",
    "净利润": "net_pro_excl_min_int_inc",
    "基本每股收益": "basic_eps",
    # balance
    "股东权益": "tot_share_equity_incl_min_int",
    "总负债": "total_liab",
    "总资产": "total_assets",
    # cash
    "营业性现金流": "net_cash_flows_opera_act",
    "投资性现金流": "net_cash_flows_inv_act",
    "融资性现金流": "net_cash_flows_fin_act",
}


def _fetch_statements(table: str, symbol_f: str, period: str, limit: int) -> pd.DataFrame:
    # 单出口通道(2026-10-27):财务三表优先走 OpenBB provider(唯一转换层),
    # 失败回落 SQL 直读。obb 通道输出列 period_ending/fiscal_period + A 股原列名,
    # 与 SQL 路径经 _ALIAS 反向 rename 后的形态一致。
    df = None
    try:
        from openbb_app.core.amazingdata_source import get_statements_via_openbb

        df = pd.DataFrame(get_statements_via_openbb(table, symbol_f, period, limit))
    except Exception as exc:  # noqa: BLE001 - fallback by design
        logger.warning("OpenBB provider channel failed, fallback to SQL: %s", exc, exc_info=exc)
    if df is None or df.empty:
        df = _db.fetch_statements(table, symbol_f, period, limit)
    if df.empty:
        return df
    rename = {v: k for k, v in _ALIAS.items() if v in df.columns}
    df = df.rename(columns=rename)
    return df


def get_income(ticker: str, period: str, limit: int) -> pd.DataFrame:
    _, symbol_f, market = normalize_symbol(ticker)
    if market not in _AMAZINGDATA_MARKETS:
        raise ValueError(f"pure-amazingdata mode: no HK/overseas data for {ticker}")
    df = _fetch_statements("income", symbol_f, period, limit)
    cols = [c for c in _STATEMENT_COLS["income"] if c in df.columns]
    return df[cols] if cols else df


def get_balance(ticker: str, period: str, limit: int) -> pd.DataFrame:
    _, symbol_f, market = normalize_symbol(ticker)
    if market not in _AMAZINGDATA_MARKETS:
        raise ValueError(f"pure-amazingdata mode: no HK/overseas data for {ticker}")
    df = _fetch_statements("balance_sheet", symbol_f, period, limit)
    cols = [c for c in _STATEMENT_COLS["balance_sheet"] if c in df.columns]
    return df[cols] if cols else df


def get_cash_flow(ticker: str, period: str, limit: int) -> pd.DataFrame:
    _, symbol_f, market = normalize_symbol(ticker)
    if market not in _AMAZINGDATA_MARKETS:
        raise ValueError(f"pure-amazingdata mode: no HK/overseas data for {ticker}")
    df = _fetch_statements("cash_flow", symbol_f, period, limit)
    cols = [c for c in _STATEMENT_COLS["cash_flow"] if c in df.columns]
    return df[cols] if cols else df


_PROFILE_FIELDS = {
    "symbol": "symbol",
    "公司名称": "comp_name",
    "证券简称": "security_name",
    "上市日期": "list_date",
    "退市日期": "delist_date",
    "板块": "listplate_name",
    "在市": "is_listed",
}


def get_info(ticker: str) -> pd.Series:
    """One-row profile Series (keyed like the legacy akshare frame)."""
    _, symbol_f, market = normalize_symbol(ticker)
    if market not in _AMAZINGDATA_MARKETS:
        raise ValueError(f"pure-amazingdata mode: no HK/overseas data for {ticker}")
    row: dict | None = None
    try:
        from openbb_app.core.amazingdata_source import get_profile_via_openbb

        row = get_profile_via_openbb(symbol_f)
    except Exception as exc:  # noqa: BLE001 - fallback by design
        logger.warning("OpenBB profile channel failed, fallback to SQL: %s", exc, exc_info=exc)
    if not row or not row.get("symbol"):
        df = _db.fetch_profile(symbol_f)
        if df.empty:
            raise ValueError(f"amazingdata has no profile for {ticker}")
        row = df.iloc[0].to_dict()
    out = {cn: row.get(en) for cn, en in _PROFILE_FIELDS.items() if cn == "symbol" or en in row}
    out["symbol"] = row.get("symbol", symbol_f)
    return pd.Series(out, name=row.get("security_name") or symbol_f)


def get_historical_prices(
    ticker: str, interval: str, interval_multiplier: int, start_date: str, end_date: str
) -> pd.DataFrame:
    """History via AmazingDataSource (day/week/month tables)."""
    from openbb_app.core.amazingdata_source import AmazingDataSource

    _, _, market = normalize_symbol(ticker)
    if market not in _AMAZINGDATA_MARKETS:
        raise ValueError(f"pure-amazingdata mode: no HK/overseas data for {ticker}")
    table_interval = {"day": "1d", "week": "1w", "month": "1m"}.get(interval, "1d")
    bars = None
    if table_interval == "1d":
        # 单出口首切(2026-10-27):day 优先走 OpenBB provider(唯一转换层),
        # 失败回落 SQL 直读(week/month 视图未覆盖,恒走 SQL)。
        try:
            from openbb_app.core.amazingdata_source import get_historical_data_via_openbb

            bars = get_historical_data_via_openbb(ticker, start_date, end_date)
        except Exception as exc:  # noqa: BLE001 - fallback by design
            logger.warning("OpenBB provider channel failed, fallback to SQL: %s", exc, exc_info=exc)
            bars = None
    if bars is None:
        bars = AmazingDataSource().get_historical_data(ticker, start_date, end_date, table_interval)
    df = pd.DataFrame(bars)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def get_quote(tickers: str) -> list[dict]:
    """Multi-ticker quote via OpenBB provider, fallback to local daily bars."""
    from openbb_app.core.amazingdata_source import AmazingDataSource

    try:
        from openbb_app.core.amazingdata_source import get_quotes_via_openbb

        quotes = get_quotes_via_openbb(tickers)
        if quotes:
            return quotes
    except Exception as exc:  # noqa: BLE001 - fallback by design
        logger.warning("OpenBB quote channel failed, fallback to SQL: %s", exc, exc_info=exc)

    from datetime import date as _date
    from datetime import timedelta as _td

    src = AmazingDataSource()
    out: list[dict] = []
    for symbol in (t.strip() for t in tickers.split(",")):
        if not symbol:
            continue
        try:
            end = _date.today()
            start = end - _td(days=400)
            bars = src.get_historical_data(symbol, start.isoformat(), end.isoformat(), "1d")
            if not bars:
                raise ValueError(f"amazingdata has no bars for {symbol}")
            closes = [b["close"] for b in bars if b.get("close") is not None]
            lows = [b["low"] for b in bars if b.get("low") is not None]
            highs = [b["high"] for b in bars if b.get("high") is not None]
            vols = [b["volume"] for b in bars if b.get("volume") is not None]
            name = symbol
            try:
                info = get_info(symbol)
                nm = info.get("公司名称") or info.get("名称")
                if nm:
                    name = str(nm)
            except Exception:
                pass
            out.append(
                {
                    "代码": symbol,
                    "名称": name,
                    "现价": float(closes[-1]),
                    "52周最低": float(min(lows[-250:])),
                    "52周最高": float(max(highs[-250:])),
                    "成交量": int(vols[-1]) if vols else 0,
                    "股息率(TTM)": None,
                    "股息(TTM)": None,
                }
            )
        except Exception as e:
            out.append({"代码": symbol, "error": str(e)[:200]})
    return out
