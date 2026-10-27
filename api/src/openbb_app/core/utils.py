import logging
import random
import re
import string
import time
from typing import Dict, List, Optional

import pandas as pd
from mysharelib.tools import setup_logger
from openbb_ai.models import LlmMessage  # type: ignore[import-untyped]


setup_logger(__name__)
logger = logging.getLogger(__name__)

# Stock quote cache with TTL (Time-To-Live)
# Format: {symbol: {data: {...}, timestamp: float}}
_stock_quote_cache: Dict[str, dict] = {}
_STOCK_QUOTE_CACHE_TTL = 60  # Cache for 60 seconds


def invalidate_stock_quote_cache(symbol: Optional[str] = None) -> None:
    """
    Invalidate stock quote cache.
    
    Args:
        symbol: If provided, invalidate only this symbol's cache. 
                If None, invalidate the entire cache.
    """
    global _stock_quote_cache
    if symbol:
        if symbol in _stock_quote_cache:
            del _stock_quote_cache[symbol]
            logger.info(f"Invalidated cache for symbol: {symbol}")
    else:
        _stock_quote_cache.clear()
        logger.info("Invalidated entire stock quote cache")


def validate_api_key(token: str, api_key: str) -> bool:
    """Validate API key in header against pre-defined list of keys."""
    if not token:
        return False
    if token.replace("Bearer ", "").strip() == api_key:
        return True
    return False


async def sanitize_message(message: str) -> str:
    """Sanitize a message by escaping forbidden characters."""
    cleaned_message = re.sub(r"(?<!\{)\{(?!{)", "{{", message)
    cleaned_message = re.sub(r"(?<!\})\}(?!})", "}}", cleaned_message)
    return cleaned_message


async def is_last_message(message: LlmMessage, messages: list[LlmMessage]) -> bool:
    """Check if the message is the last human message in the conversation."""
    human_messages = [msg for msg in messages if msg.role == "human"]
    return message == human_messages[-1] if human_messages else False


async def generate_id(length: int = 2) -> str:
    """Generate a unique ID with a total length of 4 characters."""
    timestamp = int(time.time() * 1000) % 1000

    base36_chars = string.digits + string.ascii_lowercase

    def to_base36(num):
        result = ""
        while num > 0:
            result = base36_chars[num % 36] + result
            num //= 36
        return result.zfill(2)

    random_suffix = "".join(random.choices(base36_chars, k=length))
    return to_base36(timestamp) + random_suffix


def check_api_keys() -> None:
    """纯 AmazingData:无需外部 provider key,空实现(保留入口兼容 main 调用)."""
    logger.info("AmazingData-only mode: no external API keys required.")


BUY = "买入"
SELL = "卖出"
HOLD = "持有"


def get_strategies(w52low: float, w52high: float, price: float, rate: float) -> str:
    """
    52周价格策略
        - 买入: 当前价格 <= 52周最低价 * (1 + rate)
        - 卖出: 当前价格 >= 52周最高价 * (1 - rate)
        - 持有: 其他情况
    """
    adjusted_low = w52low * (1 + rate)
    adjusted_high = w52high * (1 - rate)
    if price <= adjusted_low:
        return BUY
    elif price >= adjusted_high:
        return SELL
    else:
        return HOLD


def get_tvlink(symbol: str) -> str:
    """
    Generate TradingView link for the stock.

    Args:
        symbol: Stock symbol in format like 000001.SZ, 600000.SH, 00700.HK

    Returns:
        TradingView link as string
    """
    from mysharelib.tools import get_exchange, normalize_symbol

    symbol_b, _, _ = normalize_symbol(symbol)
    return f"https://cn.tradingview.com/chart/?symbol={get_exchange(str(symbol_b))}:{int(symbol_b)}"


def get_quote(symbols: str) -> List[dict]:
    all_data = []
    list = symbols.split(",")
    for symbol in list:
        try:
            data = get_stock_quote(symbol)
            data["symbol"] = symbol
            all_data.append(data)
        except Exception as e:
            print(f"Error fetching data for symbol {symbol}: {e}")
            continue
    return all_data


def get_stock_quote(symbol: str) -> dict:
    """
    Quote from AmazingData local daily bars (last bar + trailing 52w range).

    Args:
        symbol: Stock symbol (bare code or with .SH/.SZ suffix)

    Returns:
        Dictionary with financial metrics
    """
    global _stock_quote_cache

    # Check cache first
    now = time.time()
    cached = _stock_quote_cache.get(symbol)
    if cached and (now - cached["timestamp"]) < _STOCK_QUOTE_CACHE_TTL:
        logger.debug(f"Using cached quote data for {symbol}")
        return cached["data"]

    try:
        from datetime import date as _date, timedelta as _td

        from openbb_app.core.amazingdata_source import AmazingDataSource

        src = AmazingDataSource()
        end = _date.today().isoformat()
        start = (_date.today() - _td(days=400)).isoformat()
        bars = src.get_historical_data(symbol, start, end, "1d")
        if not bars:
            raise ValueError(f"amazingdata has no bars for {symbol}")
        closes = [b["close"] for b in bars if b.get("close") is not None]
        lows = [b["low"] for b in bars if b.get("low") is not None]
        highs = [b["high"] for b in bars if b.get("high") is not None]
        vols = [b["volume"] for b in bars if b.get("volume") is not None]
        result = {
            "current_price": float(closes[-1]),
            "fifty_two_week_low": float(min(lows[-250:])),
            "fifty_two_week_high": float(max(highs[-250:])),
            "volume": int(vols[-1]) if vols else 0,
            "dividend_yield": 0,
            "latest_dividend": 0,
        }

        # Cache the result
        _stock_quote_cache[symbol] = {
            "data": result,
            "timestamp": now
        }

        logger.info(f"Fetched and cached amazingdata quote for {symbol}")
        return result
    except Exception as e:
        logger.error(f"Error fetching amazingdata quote for {symbol}: {e}")
        # Return fallback values
        return {
            "current_price": 0,
            "fifty_two_week_low": 0,
            "fifty_two_week_high": 0,
            "volume": 0,
            "dividend_yield": 0,
            "latest_dividend": 0,
        }


def get_symbols(exchange: str = "") -> List[dict]:
    """Available tickers, amazingdata only (local stock_basic)."""
    import asyncio
    import concurrent.futures

    import asyncpg

    from openbb_app.core.amazingdata_source import _connect_kwargs

    async def _fetch() -> list[dict]:
        conn = await asyncpg.connect(**_connect_kwargs())
        try:
            rows = await conn.fetch(
                "SELECT symbol, security_name, comp_name FROM stock_basic"
                " WHERE symbol NOT LIKE '159%' AND symbol NOT LIKE '511%'"
                " AND symbol NOT LIKE '512%' AND symbol NOT LIKE '513%'"
                " ORDER BY symbol LIMIT 8000"
            )
            return [dict(r) for r in rows]
        finally:
            await conn.close()

    def _run() -> list[dict]:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, _fetch()).result()
        return asyncio.run(_fetch())

    out: List[dict] = []
    for r in _run():
        code = (r.get("symbol") or "").split(".")[0]
        name = r.get("comp_name") or r.get("security_name") or code
        out.append(
            {
                "label": f"{code} {name}",
                "value": code,
                "extraInfo": {
                    "description": name,
                    "rightOfDescription": r.get("symbol") or "",
                },
            }
        )
    return out


def get_news(symbol: str, limit: int = 10) -> pd.DataFrame:
    """个股新闻:东财搜索接口直调(纯 HTTP,无 akshare 依赖).

    上游: akshare.stock_news_em 逆向的 search-api-web.eastmoney.com JSONP。
    失败(超时/反爬/空) → 空表,不抛(不断 widget)。
    返回列对齐 widget 契约:title/published/summary(+source/url 备用)。
    """
    import json
    import re
    import time

    import requests

    try:
        from mysharelib.tools import normalize_symbol

        symbol_b, _, market = normalize_symbol(symbol)
        if market not in ("SH", "SZ", "BJ"):
            return pd.DataFrame(columns=["title", "published", "summary"])
        code = re.sub(r"\D", "", symbol_b)
    except Exception:
        code = re.sub(r"\D", "", symbol)
    if not code:
        return pd.DataFrame(columns=["title", "published", "summary"])

    empty = pd.DataFrame(columns=["title", "published", "summary"])
    try:
        cb = f"jQuery{int(time.time() * 1000)}"
        inner = {
            "uid": "", "keyword": code, "type": ["cmsArticleWebOld"],
            "client": "web", "clientType": "web", "clientVersion": "curr",
            "param": {"cmsArticleWebOld": {
                "searchScope": "default", "sort": "default",
                "pageIndex": 1, "pageSize": 50,
                "preTag": "<em>", "postTag": "</em>",
            }},
        }
        r = requests.get(
            "https://search-api-web.eastmoney.com/search/jsonp",
            params={"cb": cb, "param": json.dumps(inner, ensure_ascii=False),
                    "_": str(int(time.time() * 1000))},
            headers={
                "Referer": f"https://so.eastmoney.com/news/s?keyword={code}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/142.0.0.0 Safari/537.36",
            },
            timeout=10,
        )
        text = r.text.strip()
        payload = text[len(cb) + 1:-1] if text.startswith(cb) else text
        data = json.loads(payload)
        rows = (data.get("result") or {}).get("cmsArticleWebOld") or []
        if not rows:
            return empty
        try:
            from openbb_app.core.financials import get_info

            info = get_info(symbol)
            names = {
                str(info.get("证券简称") or ""),
                str(info.get("公司名称") or ""),
            } - {""}
        except Exception:
            names = set()
        out = []
        for it in rows:
            title = re.sub(r"</?em>", "", it.get("title") or "")
            content = re.sub(r"</?em>", "", it.get("content") or "")
            if not any(n and n in title for n in names if n):
                continue
            out.append({
                "title": title,
                "published": it.get("date") or "",
                "summary": content[:300],
                "source": it.get("mediaName") or "东方财富",
                "url": f"http://finance.eastmoney.com/a/{it.get('code', '')}.html",
            })
            if len(out) >= limit:
                break
        return pd.DataFrame(out) if out else empty
    except Exception as e:
        logger.warning(f"东财新闻请求失败 {code}: {e}")
        return empty


def get_info(symbol: str) -> pd.DataFrame:
    """基本信息(A股走本地 stock_basic 单行)."""
    import asyncio
    import concurrent.futures

    import asyncpg

    from openbb_app.core.amazingdata_source import _connect_kwargs

    try:
        from mysharelib.tools import normalize_symbol

        _, symbol_f, _ = normalize_symbol(symbol)
    except Exception:
        symbol_f = symbol

    async def _fetch() -> list[dict]:
        conn = await asyncpg.connect(**_connect_kwargs())
        try:
            rows = await conn.fetch(
                "SELECT * FROM stock_basic WHERE symbol = $1 LIMIT 1", symbol_f
            )
            return [dict(r) for r in rows]
        finally:
            await conn.close()

    def _run() -> list[dict]:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, _fetch()).result()
        return asyncio.run(_fetch())

    rows = _run()
    if not rows:
        return pd.DataFrame([{}]).T[0]
    return pd.DataFrame(rows).T[0]
