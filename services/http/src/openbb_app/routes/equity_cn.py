from fastapi import APIRouter, Query
from openbb_app.core.registry import register_widget
from fastapi import Depends

from openbb_app.core.auth import get_current_user

equity_cn_router = APIRouter()

@register_widget({
    "name": "财务指标",
    "description": "获取A股的财务指标",
    "category": "Equity",
    "subcategory": "Financials",
    "type": "table",
    "widgetId": "cn/financial_data",
    "endpoint": "/api/v1/cn/financial_data",
    "gridData": {
        "w": 80,
        "h": 12
    },
    "data": {
        "table": {
            "showAll": True
        }
    },
    "source": "A股",
    "params": [
        {
            "type": "endpoint",
            "paramName": "ticker",
            "label": "Symbol",
            "value": "600325",
            "description": "Stock ticker",
            "optionsEndpoint": "/api/v1/cn/tickers"
        }
    ]
})
@equity_cn_router.get("/financial_data")
def get_financial_data(
    ticker: str,
    token: str = Depends(get_current_user)
):
    """Financial facts (pure-amazingdata: profile single row; peer comparison removed with akshare)."""
    from openbb_app.core.financials import get_info

    info = get_info(ticker)
    return [{"fact": k, "value": v} for k, v in info.to_dict().items()]

@register_widget({
    "name": "利润表",
    "description": "Financial statements that provide information about a company's revenues, expenses, and profits over a specific period.",
    "category": "Equity",
    "subcategory": "Financials",
    "type": "table",
    "widgetId": "cn/income",
    "endpoint": "/api/v1/cn/income",
    "gridData": {
        "w": 80,
        "h": 12
    },
    "data": {
        "table": {
            "showAll": True,
            "columnsDefs": [
                {
                    "field": "period_ending",
                    "headerName": "报告日期",
                    "cellDataType": "text",
                    "formatterFn": "none",
                    "pinned": "left"
                },
                {
                    "field": "fiscal_period",
                    "headerName": "报告类型",
                    "headerTooltip": "Total Value Locked",
                    "cellDataType": "text",
                    "formatterFn": "none"
                }
            ]
        }
    },
    "source": "A股",
    "params": [
        {
            "type": "endpoint",
            "paramName": "ticker",
            "label": "Symbol",
            "value": "600325",
            "description": "Ticker to get 利润表 for (Free tier: AAPL, MSFT, TSLA)",
            "optionsEndpoint": "/api/v1/cn/tickers"
        },
        {
            "type": "text",
            "value": "annual",
            "paramName": "period",
            "label": "Period",
            "description": "Period to get statements from",
            "options": [
                {"value": "annual", "label": "Annual"},
                {"value": "quarter", "label": "Quarterly"},
                {"value": "ttm", "label": "TTM"}
            ]
        },
        {
            "type": "number",
            "paramName": "limit",
            "label": "Number of Statements",
            "value": "10",
            "description": "Number of statements to display"
        }
    ]
})
@equity_cn_router.get("/income")
def get_cn_income(ticker: str, period: str, limit: int, token: str = Depends(get_current_user)):
    """Get 利润表"""
    from openbb_app.core.financials import get_income
    income_data = get_income(ticker, period, limit)
    income_data = income_data.fillna(0)
    #logger.info(f"Income data for {ticker}, period: {period}, limit: {limit}: {income_data}")
    return income_data.to_dict(orient="records")

@register_widget({
    "name": "资产负债表",
    "description": "A financial statement that summarizes a company's assets, liabilities and shareholders' equity at a specific point in time.",
    "category": "Equity",
    "subcategory": "Financials",
    "type": "table",
    "widgetId": "cn/balance",
    "endpoint": "/api/v1/cn/balance",
    "gridData": {
        "w": 80,
        "h": 12
    },
    "data": {
        "table": {
            "showAll": True,
            "columnsDefs": [
                {
                    "field": "period_ending",
                    "headerName": "报告日期",
                    "cellDataType": "text",
                    "formatterFn": "none",
                    "pinned": "left"
                },
                {
                    "field": "fiscal_period",
                    "headerName": "报告类型",
                    "headerTooltip": "Total Value Locked",
                    "cellDataType": "text",
                    "formatterFn": "none"
                }
            ]
        }
    },
    "source": "A股",
    "params": [
        {
            "type": "endpoint",
            "paramName": "ticker",
            "label": "Symbol",
            "value": "600325",
            "description": "Ticker to get 资产负债表 for (Free tier: AAPL, MSFT, TSLA)",
            "optionsEndpoint": "/api/v1/cn/tickers"
        },
        {
            "type": "text",
            "value": "annual",
            "paramName": "period",
            "label": "Period",
            "description": "Period to get statements from",
            "options": [
                {"value": "annual", "label": "Annual"},
                {"value": "quarter", "label": "Quarterly"},
                {"value": "ttm", "label": "TTM"}
            ]
        },
        {
            "type": "number",
            "paramName": "limit",
            "label": "Number of Statements",
            "value": "10",
            "description": "Number of statements to display"
        }
    ]
})
@equity_cn_router.get("/balance")
def get_cn_balance(ticker: str, period: str, limit: int, token: str = Depends(get_current_user)):
    """Get 资产负债表"""
    from openbb_app.core.financials import get_balance
    balance_data = get_balance(ticker, period, limit)
    balance_data = balance_data.fillna(0)
    return balance_data.to_dict(orient="records")

@register_widget({
    "name": "现金流量表",
    "description": "Financial statements that provide information about a company's cash inflows and outflows over a specific period.",
    "category": "Equity",
    "subcategory": "Financials",
    "type": "table",
    "widgetId": "cn/cash_flow",
    "endpoint": "/api/v1/cn/cash_flow",
    "gridData": {
        "w": 80,
        "h": 12
    },
    "data": {
        "table": {
            "showAll": True,
            "columnsDefs": [
                {
                    "field": "period_ending",
                    "headerName": "报告日期",
                    "cellDataType": "text",
                    "formatterFn": "none",
                    "pinned": "left"
                },
                {
                    "field": "fiscal_period",
                    "headerName": "报告类型",
                    "headerTooltip": "Total Value Locked",
                    "cellDataType": "text",
                    "formatterFn": "none"
                }
            ]
        }
    },
    "source": "A股",
    "params": [
        {
            "type": "endpoint",
            "paramName": "ticker",
            "label": "Symbol",
            "value": "600325",
            "description": "Ticker to get 现金流量表 for (Free tier: AAPL, MSFT, TSLA)",
            "optionsEndpoint": "/api/v1/cn/tickers"
        },
        {
            "type": "text",
            "value": "annual",
            "paramName": "period",
            "label": "Period",
            "description": "Period to get statements from",
            "options": [
                {"value": "annual", "label": "Annual"},
                {"value": "quarter", "label": "Quarterly"},
                {"value": "ttm", "label": "TTM"}
            ]
        },
        {
            "type": "number",
            "paramName": "limit",
            "label": "Number of Statements",
            "value": "10",
            "description": "Number of statements to display"
        }
    ]
})
@equity_cn_router.get("/cash_flow")
def get_cn_cash_flow(ticker: str, period: str, limit: int, token: str = Depends(get_current_user)):
    """Get 现金流量表"""
    from openbb_app.core.financials import get_cash_flow
    cash_data = get_cash_flow(ticker, period, limit)
    cash_data = cash_data.fillna(0)
    return cash_data.to_dict(orient="records")

@register_widget({
    "name": "基本信息",
    "description": "Get key company information including name, CIK, market cap, total employees, website URL, and more.",
    "category": "Equity",
    "subcategory": "Company Info",
    "type": "markdown",
    "widgetId": "cn/key_metrics",
    "endpoint": "/api/v1/cn/key_metrics",
    "gridData": {
        "w": 40,
        "h": 12
    },
    "data": {
        "table": {
            "showAll": True,
            "columns": [
                {"field": "fact", "headerName": "Fact", "width": 200},
                {"field": "value", "headerName": "Value", "width": 200}
            ]
        }
    },
    "source": "A股",
    "params": [
        {
            "type": "endpoint",
            "paramName": "ticker",
            "label": "Symbol",
            "value": "600325",
            "description": "Ticker to get company facts for (Free tier: AAPL, MSFT, TSLA)",
            "optionsEndpoint": "/api/v1/cn/tickers"
        }
    ]
})
@equity_cn_router.get("/key_metrics")
def get_cn_key_metrics(
    ticker: str, 
    token: str = Depends(get_current_user)
    ):
    """Get company facts for a ticker"""
    from openbb_app.core.financials import get_info
    key_metrics = get_info(ticker)
    key_metrics.name = key_metrics["证券简称"]
    return key_metrics.to_markdown()

@register_widget({
    "name": "相关新闻",
    "description": "Get recent news articles for stocks, including headlines, publish dates, and article summaries.",
    "category": "Equity",
    "subcategory": "News",
    "type": "table",
    "widgetId": "cn/news",
    "endpoint": "/api/v1/cn/news",
    "gridData": {
        "w": 40,
        "h": 8
    },
    "data": {
        "table": {
            "showAll": True,
            "columnsDefs": [
                {"field": "date", "headerName": "Date", "width": 180, "cellDataType": "text", "pinned": "left"},
                {"field": "title", "headerName": "Title", "width": 300, "cellDataType": "text"},
                {"field": "source", "headerName": "Source", "width": 150, "cellDataType": "text"},
                {"field": "author", "headerName": "Author", "width": 150, "cellDataType": "text"},
                {"field": "sentiment", "headerName": "Sentiment", "width": 120, "cellDataType": "text"},
                {"field": "url", "headerName": "URL", "width": 200, "cellDataType": "text"}
            ]
        }
    },
    "source": "A股",
    "params": [
        {
            "type": "endpoint",
            "paramName": "ticker",
            "label": "Symbol",
            "value": "600325",
            "description": "Stock ticker to get news for (Free tier: AAPL, MSFT, TSLA)",
            "multiSelect": False,
            "optionsEndpoint": "/api/v1/cn/tickers"
        },
        {
            "type": "number",
            "paramName": "limit",
            "label": "Number of Articles",
            "value": "10",
            "description": "Maximum number of news articles to display"
        }
    ]
})
@equity_cn_router.get("/news")
async def get_cn_news(ticker: str = Query(..., description="Stock ticker"), 
                         limit: int = 10, token: str = Depends(get_current_user)):
    """Get news articles for a stock"""
    from openbb_app.core.financials import get_news
    return get_news(ticker, limit).to_dict(orient="records")

@register_widget({
    "name": "历史股价",
    "description": "Get historical price data for stocks with customizable intervals and date ranges.",
    "category": "Equity",
    "subcategory": "Prices",
    "type": "table",
    "widgetId": "cn/prices",
    "endpoint": "/api/v1/cn/prices",
    "gridData": {
        "w": 40,
        "h": 8
    },
    "data": {
        "table": {
            "enableCharts": True,
            "showAll": False,
            "chartView": {
                "enabled": True,
                "chartType": "line"
            },
            "columnsDefs": [
                {"field": "date", "headerName": "Date", "width": 180, "chartDataType": "time"},
                {"field": "open", "headerName": "Open", "width": 120, "cellDataType": "number"},
                {"field": "high", "headerName": "High", "width": 120, "cellDataType": "number"},
                {"field": "low", "headerName": "Low", "width": 120, "cellDataType": "number"},
                {"field": "close", "headerName": "Close", "width": 120, "chartDataType": "series"},
                {"field": "volume", "headerName": "Volume", "width": 120, "cellDataType": "number"}
            ]
        }
    },
    "source": "A股",
    "params": [
        {
            "type": "endpoint",
            "paramName": "ticker",
            "label": "Symbol",
            "value": "600325",
            "description": "Stock ticker to get historical prices for (Free tier: AAPL, MSFT, TSLA)",
            "optionsEndpoint": "/api/v1/cn/tickers"
        },
        {
            "type": "text",
            "value": "day",
            "paramName": "interval",
            "label": "Interval",
            "description": "Time interval for prices",
            "options": [
                {"value": "minute", "label": "Minute"},
                {"value": "day", "label": "Day"},
                {"value": "week", "label": "Week"},
                {"value": "month", "label": "Month"},
                {"value": "year", "label": "Year"}
            ]
        },
        {
            "type": "number",
            "paramName": "interval_multiplier",
            "label": "Interval Multiplier",
            "value": "1",
            "description": "Multiplier for the interval (e.g., 5 for every 5 minutes)"
        },
        {
            "type": "date",
            "paramName": "start_date",
            "label": "Start Date",
            "value": "2024-09-08",
            "description": "Start date for historical data"
        },
        {
            "type": "date",
            "paramName": "end_date",
            "label": "End Date",
            "value": "2025-10-09",
            "description": "End date for historical data"
        }
    ]
})
@equity_cn_router.get("/prices")
def get_cn_prices(
    ticker: str,
    interval: str,
    interval_multiplier: int,
    start_date: str,
    end_date: str, 
    token: str = Depends(get_current_user)
):
    """Get historical stock prices"""
    from openbb_app.core.financials import get_historical_prices
    stock_prices = get_historical_prices(ticker, interval, interval_multiplier, start_date, end_date)
    return stock_prices.reset_index().to_dict(orient="records")

@register_widget({
    "name": "k线图",
    "description": "股价k线图",
    "category": "Equity",
    "type": "chart",
    "endpoint": "/api/v1/cn/candles",
    "widgetId": "cn/candles",
    "gridData": {
        "w": 40,
        "h": 20
    },
    "source": "A股",
    "params": [
        {
            "type": "endpoint",
            "paramName": "ticker",
            "label": "Symbol",
            "value": "600028",
            "description": "Stock ticker (e.g., 600028 for Shanghai Stock Exchange)",
            "optionsEndpoint": "/api/v1/cn/tickers"
        },
        {
            "type": "text",
            "value": "day",
            "paramName": "interval",
            "label": "Interval",
            "description": "Time interval for prices",
            "options": [
                {"value": "minute", "label": "Minute"},
                {"value": "day", "label": "Day"},
                {"value": "week", "label": "Week"},
                {"value": "month", "label": "Month"},
                {"value": "year", "label": "Year"}
            ]
        },
        {
            "type": "number",
            "paramName": "interval_multiplier",
            "label": "Interval Multiplier",
            "value": "1",
            "description": "Multiplier for the interval (e.g., 5 for every 5 minutes)"
        },
        {
            "type": "date",
            "paramName": "start_date",
            "label": "Start Date",
            "value": "2024-09-08",
            "description": "Start date for historical data"
        },
        {
            "type": "date",
            "paramName": "end_date",
            "label": "End Date",
            "value": "2025-10-09",
            "description": "End date for historical data"
        }
    ],
    "data": {"chart": {"type": "candlestick"}},
})
@equity_cn_router.get("/candles")
async def get_candles_cn(
    ticker: str,
    interval: str,
    interval_multiplier: int,
    start_date: str,
    end_date: str,
    token: str = Depends(get_current_user)
):
    from openbb_app.routes.charts import get_chart_data
    return get_chart_data(ticker, interval, interval_multiplier, start_date, end_date)

@equity_cn_router.get("/tickers")
def get_cn_tickers(token: str = Depends(get_current_user)):
    """Get available stock tickers for A-share market"""
    from openbb_app.core.financials import get_tickers
    return get_tickers()

@register_widget({
    "name": "股价",
    "description": "Get the current prices.",
    "category": "Equity",
    "subcategory": "Prices",
    "type": "table",
    "widgetId": "cn/quote",
    "endpoint": "/api/v1/cn/quote",
    "gridData": {
        "w": 40,
        "h": 8
    },
    "data": {
        "table": {
            "enableCharts": False,
            "showAll": False,
            "columnsDefs": [
                {"field": "代码", "headerName": "代码", 
                 "cellDataType": "text",
                 "width": 80, 
                 "pinned": "left",
                 "renderFn": "cellOnClick",
                 "renderFnParams": {
                        "actionType": "groupBy",
                        "groupByParamName": "ticker"
                    }
                 },
                {"field": "名称", "headerName": "名称", "width": 100, "cellDataType": "text"},
                {"field": "现价", "headerName": "现价", "width": 100, "cellDataType": "number"},
                {"field": "52周最低", "headerName": "52周最低", "width": 100, "cellDataType": "number"},
                {"field": "52周最高", "headerName": "52周最高", "width": 100, "cellDataType": "number"},
                {"field": "成交量", "headerName": "成交量", "width": 100, "cellDataType": "number"},
                {"field": "股息率(TTM)", "headerName": "股息率(TTM)", "width": 100, "cellDataType": "number"},
                {"field": "股息(TTM)", "headerName": "股息(TTM)", "width": 100, "cellDataType": "number"}]
        }
    },
    "source": "A股",
    "params": [
        {
            "paramName": "ticker",
            "description": "Stock ticker to get the current prices.",
            "value": "600028",
            "label": "Symbol",
            "type": "endpoint",
            "optionsEndpoint": "/api/v1/cn/tickers",
            "multiSelect": False,
            "show": True
        },
    ]
})
@equity_cn_router.get("/quote")
def get_cn_quote(
    ticker: str = "600028",
    token: str = Depends(get_current_user)
):
    """Get current stock prices (comma-separated tickers supported)."""
    from openbb_app.core.financials import get_quote
    return get_quote(ticker or "601288,601988,601939,601398,600325,600104,601006,600028")
    from openbb_app.core.financials import get_quote
    return get_quote("601288,601988,601939,601398,600325,600104,601006,600028")


@register_widget({
    "name": "行业估值",
    "description": "申万行业指数日行情与 PB/PE 估值(本地库)",
    "category": "Equity",
    "subcategory": "Industry",
    "type": "table",
    "widgetId": "cn/industry_valuation",
    "endpoint": "/api/v1/cn/industry_valuation",
    "gridData": {"w": 40, "h": 8},
    "data": {"table": {"showAll": False}},
    "source": "A股",
    "params": [
        {"type": "text", "paramName": "index_code", "label": "Index Code",
         "value": "801010.SI", "description": "申万行业指数代码,留空返回全行业"},
        {"type": "date", "paramName": "start_date", "label": "Start Date", "value": "2025-09-01"},
        {"type": "date", "paramName": "end_date", "label": "End Date", "value": "2025-09-30"},
        {"type": "number", "paramName": "limit", "label": "Limit", "value": "20"},
    ]
})
@equity_cn_router.get("/industry_valuation")
def get_cn_industry_valuation(
    index_code: str = "", start_date: str = "2025-09-01", end_date: str = "2025-09-30",
    limit: int = 20, token: str = Depends(get_current_user)
):
    """Industry index valuation (PB/PE)"""
    from openbb_app.core import galaxy_db as _db
    df = _db.fetch_industry_valuation(index_code or None, start_date, end_date, limit)
    return _db.to_records(df)


@register_widget({
    "name": "板块资金流",
    "description": "板块主力资金净流入(本地库日快照)",
    "category": "Equity",
    "subcategory": "Fund Flow",
    "type": "table",
    "widgetId": "cn/sector_flow",
    "endpoint": "/api/v1/cn/sector_flow",
    "gridData": {"w": 40, "h": 8},
    "data": {"table": {"showAll": False}},
    "source": "A股",
    "params": [
        {"type": "date", "paramName": "trade_date", "label": "Trade Date",
         "value": "", "description": "留空取最近一日"},
        {"type": "number", "paramName": "limit", "label": "Limit", "value": "20"},
    ]
})
@equity_cn_router.get("/sector_flow")
def get_cn_sector_flow(
    trade_date: str = "", limit: int = 20, token: str = Depends(get_current_user)
):
    """Sector fund flow snapshot"""
    from openbb_app.core import galaxy_db as _db
    df = _db.fetch_sector_flow(trade_date or None, limit)
    return _db.to_records(df)


@register_widget({
    "name": "龙虎榜",
    "description": "个股龙虎榜席位买卖明细(本地库)",
    "category": "Equity",
    "subcategory": "Fund Flow",
    "type": "table",
    "widgetId": "cn/lhb",
    "endpoint": "/api/v1/cn/lhb",
    "gridData": {"w": 40, "h": 8},
    "data": {"table": {"showAll": True}},
    "source": "A股",
    "params": [
        {"type": "endpoint", "paramName": "ticker", "label": "Symbol",
         "value": "600325", "description": "Stock ticker", "optionsEndpoint": "/api/v1/cn/tickers"},
        {"type": "number", "paramName": "limit", "label": "Limit", "value": "20"},
    ]
})
@equity_cn_router.get("/lhb")
def get_cn_lhb(
    ticker: str, limit: int = 20, token: str = Depends(get_current_user)
):
    """Long-hu-bang records for one stock"""
    from mysharelib.tools import normalize_symbol
    from openbb_app.core import galaxy_db as _db
    _, symbol_f, _ = normalize_symbol(ticker)
    df = _db.fetch_lhb(symbol_f, limit)
    return _db.to_records(df)


@register_widget({
    "name": "大宗交易",
    "description": "个股大宗交易明细(本地库)",
    "category": "Equity",
    "subcategory": "Fund Flow",
    "type": "table",
    "widgetId": "cn/block_trade",
    "endpoint": "/api/v1/cn/block_trade",
    "gridData": {"w": 40, "h": 8},
    "data": {"table": {"showAll": True}},
    "source": "A股",
    "params": [
        {"type": "endpoint", "paramName": "ticker", "label": "Symbol",
         "value": "600325", "description": "Stock ticker", "optionsEndpoint": "/api/v1/cn/tickers"},
        {"type": "number", "paramName": "limit", "label": "Limit", "value": "20"},
    ]
})
@equity_cn_router.get("/block_trade")
def get_cn_block_trade(
    ticker: str, limit: int = 20, token: str = Depends(get_current_user)
):
    """Block trading records for one stock"""
    from mysharelib.tools import normalize_symbol
    from openbb_app.core import galaxy_db as _db
    _, symbol_f, _ = normalize_symbol(ticker)
    df = _db.fetch_block_trade(symbol_f, limit)
    return _db.to_records(df)


@register_widget({
    "name": "两融余额",
    "description": "个股融资融券每日明细(本地库)",
    "category": "Equity",
    "subcategory": "Margin",
    "type": "table",
    "widgetId": "cn/margin",
    "endpoint": "/api/v1/cn/margin",
    "gridData": {"w": 40, "h": 8},
    "data": {"table": {"showAll": False}},
    "source": "A股",
    "params": [
        {"type": "endpoint", "paramName": "ticker", "label": "Symbol",
         "value": "600325", "description": "Stock ticker", "optionsEndpoint": "/api/v1/cn/tickers"},
        {"type": "number", "paramName": "limit", "label": "Limit", "value": "20"},
    ]
})
@equity_cn_router.get("/margin")
def get_cn_margin(
    ticker: str, limit: int = 20, token: str = Depends(get_current_user)
):
    """Margin trading detail for one stock"""
    from mysharelib.tools import normalize_symbol
    from openbb_app.core import galaxy_db as _db
    _, symbol_f, _ = normalize_symbol(ticker)
    df = _db.fetch_margin(symbol_f, limit)
    return _db.to_records(df)
