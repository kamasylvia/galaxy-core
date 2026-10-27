"""A-share financial statement fetchers (DB-backed, single-exit channel).

读 income / balance_sheet / cash_flow 三表(statement_type='1' 合并报表;
period=annual 加 12 月过滤,与 api 侧原 SQL 直读路径同语义,2026-10-27 定稿)。

字段设计:``period_ending``/``fiscal_period`` 对齐 OpenBB 标准模型字段;
数值字段用 A 股原列名作为扩展字段(标准 GAAP 字段映射待真有标准消费者
再补,加字段向后兼容)。api 侧经 obb 取数后输出与 SQL 路径同形。
"""

import asyncio
import concurrent.futures
from datetime import date
from typing import Any

import asyncpg
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.balance_sheet import (
    BalanceSheetData,
    BalanceSheetQueryParams,
)
from openbb_core.provider.standard_models.cash_flow import (
    CashFlowStatementData,
    CashFlowStatementQueryParams,
)
from openbb_core.provider.standard_models.income_statement import (
    IncomeStatementData,
    IncomeStatementQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_provider_amazingdata.models.equity_historical import _connect_kwargs

_STATEMENT_SQL = """
SELECT reporting_period AS period_ending,
       statement_type   AS fiscal_period,
       {cols}
FROM {table}
WHERE symbol = $1 AND statement_type = '1'
{annual_filter}
ORDER BY reporting_period DESC
LIMIT $2
"""


async def _fetch_statement_rows(
    table: str, cols: str, symbol: str, limit: int, annual: bool
) -> list[dict[str, Any]]:
    conn = await asyncpg.connect(**_connect_kwargs(None))
    try:
        annual_filter = (
            "AND EXTRACT(MONTH FROM reporting_period) = 12" if annual else ""
        )
        rows = await conn.fetch(
            _STATEMENT_SQL.format(
                cols=cols, table=table, annual_filter=annual_filter
            ),
            symbol,
            limit,
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


def _run_fetch(
    table: str, cols: str, symbol: str, limit: int, annual: bool
) -> list[dict[str, Any]]:
    """Sync entry: fresh loop in a worker thread (uvicorn request-thread safe)."""

    def _run() -> list[dict[str, Any]]:
        return asyncio.run(_fetch_statement_rows(table, cols, symbol, limit, annual))

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run).result()


def _annual(params: Any) -> bool:
    return getattr(params, "period", "annual") == "annual"


class AmazingDataIncomeStatementQueryParams(IncomeStatementQueryParams):
    """A-share income statement query (DB-backed)."""

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}


class AmazingDataIncomeStatementData(IncomeStatementData):
    """A-share income statement.

    标准(生态惯例)字段 = fmp 命名,与 A 股列一一对应、不合成不造数
    (gross_profit/SG&A 合计等需计算的口径不映射);A 股原列名保留为
    扩展字段(api 单出口消费同形)。
    """

    revenue: float | None = Field(default=None, description="营业收入(元)")
    cost_of_revenue: float | None = Field(default=None, description="营业成本(元)")
    ebit: float | None = Field(default=None)
    ebitda: float | None = Field(default=None)
    income_tax_expense: float | None = Field(default=None, description="所得税(元)")
    research_and_development_expense: float | None = Field(default=None, description="研发费用(元)")
    general_and_admin_expense: float | None = Field(default=None, description="管理费用(元)")
    selling_and_marketing_expense: float | None = Field(default=None, description="销售费用(元)")
    consolidated_net_income: float | None = Field(default=None, description="合并净利润(元)")
    bottom_line_net_income: float | None = Field(default=None, description="归母净利润(元)")
    basic_earnings_per_share: float | None = Field(default=None)
    diluted_earnings_per_share: float | None = Field(default=None)
    tot_opera_rev: float | None = Field(default=None, description="营业收入(元)")
    opera_profit: float | None = Field(default=None, description="营业利润(元)")
    net_pro_excl_min_int_inc: float | None = Field(
        default=None, description="净利润(归母,元)"
    )
    basic_eps: float | None = Field(default=None, description="基本每股收益(元)")


class AmazingDataBalanceSheetQueryParams(BalanceSheetQueryParams):
    """A-share balance sheet query (DB-backed)."""

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}


class AmazingDataBalanceSheetData(BalanceSheetData):
    """A-share balance sheet(标准字段 = fmp 惯例命名,A 股原列保留)."""

    total_assets: float | None = Field(default=None, description="资产总计(元)")
    total_liabilities: float | None = Field(default=None, description="负债合计(元)")
    total_equity: float | None = Field(
        default=None, description="股东权益合计(含少数股东,元)"
    )
    total_liab: float | None = Field(default=None, description="负债合计(元)")
    tot_share_equity_incl_min_int: float | None = Field(
        default=None, description="股东权益(含少数股东,元)"
    )


class AmazingDataCashFlowQueryParams(CashFlowStatementQueryParams):
    """A-share cash flow statement query (DB-backed)."""

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}


class AmazingDataCashFlowData(CashFlowStatementData):
    """A-share cash flow statement(标准字段 = fmp 惯例命名,A 股原列保留)."""

    net_cash_from_operating_activities: float | None = Field(
        default=None, description="经营活动现金流净额(元)"
    )
    net_cash_from_investing_activities: float | None = Field(
        default=None, description="投资活动现金流净额(元)"
    )
    net_cash_from_financing_activities: float | None = Field(
        default=None, description="筹资活动现金流净额(元)"
    )
    net_cash_flows_opera_act: float | None = Field(
        default=None, description="经营活动现金流净额(元)"
    )
    net_cash_flows_inv_act: float | None = Field(
        default=None, description="投资活动现金流净额(元)"
    )
    net_cash_flows_fin_act: float | None = Field(
        default=None, description="筹资活动现金流净额(元)"
    )


class _StatementFetcherMixin:
    """Shared extract_data: async PG read in a dedicated thread (loop-safe)."""

    _table: str
    _cols: str

    @staticmethod
    def _extract(query, table: str, cols: str) -> list[dict[str, Any]]:
        symbols = query.symbol if isinstance(query.symbol, list) else [query.symbol]
        symbol = symbols[0] if symbols else query.symbol
        annual = getattr(query, "period", "annual") == "annual"

        def _run() -> list[dict[str, Any]]:
            return asyncio.run(
                _fetch_statement_rows(table, cols, symbol, query.limit, annual)
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_run).result()


class AmazingDataIncomeStatementFetcher(
    Fetcher[AmazingDataIncomeStatementQueryParams, list[AmazingDataIncomeStatementData]],
    _StatementFetcherMixin,
):
    @staticmethod
    def transform_query(params: dict[str, Any]) -> AmazingDataIncomeStatementQueryParams:
        return AmazingDataIncomeStatementQueryParams(**params)

    @staticmethod
    def extract_data(query, credentials, **kwargs: Any) -> list[dict]:
        return _StatementFetcherMixin._extract(
            query,
            "income",
            "tot_opera_rev, tot_opera_cost, ebit, ebitda, income_tax, rd_exp,"
            " less_admin_exp, less_selling_exp, net_pro_incl_min_int_inc,"
            " net_pro_excl_min_int_inc, basic_eps, diluted_eps, opera_profit",
        )

    @staticmethod
    def transform_data(query, data: list[dict], **kwargs: Any):
        if not data:
            raise EmptyDataError(f"no income statement rows for {query.symbol}")
        mapped = []
        for r in data:
            r = dict(r)
            r["revenue"] = r.get("tot_opera_rev")
            r["cost_of_revenue"] = r.get("tot_opera_cost")
            r["income_tax_expense"] = r.get("income_tax")
            r["research_and_development_expense"] = r.get("rd_exp")
            r["general_and_admin_expense"] = r.get("less_admin_exp")
            r["selling_and_marketing_expense"] = r.get("less_selling_exp")
            r["consolidated_net_income"] = r.get("net_pro_incl_min_int_inc")
            r["bottom_line_net_income"] = r.get("net_pro_excl_min_int_inc")
            r["basic_earnings_per_share"] = r.get("basic_eps")
            r["diluted_earnings_per_share"] = r.get("diluted_eps")
            mapped.append(AmazingDataIncomeStatementData(**r))
        return mapped


class AmazingDataBalanceSheetFetcher(
    Fetcher[AmazingDataBalanceSheetQueryParams, list[AmazingDataBalanceSheetData]],
    _StatementFetcherMixin,
):
    @staticmethod
    def transform_query(params: dict[str, Any]) -> AmazingDataBalanceSheetQueryParams:
        return AmazingDataBalanceSheetQueryParams(**params)

    @staticmethod
    def extract_data(query, credentials, **kwargs: Any) -> list[dict]:
        return _StatementFetcherMixin._extract(
            query,
            "balance_sheet",
            "total_assets, total_liab, tot_share_equity_incl_min_int",
        )

    @staticmethod
    def transform_data(query, data: list[dict], **kwargs: Any):
        if not data:
            raise EmptyDataError(f"no balance sheet rows for {query.symbol}")
        mapped = []
        for r in data:
            r = dict(r)
            r["total_assets"] = r.get("total_assets")
            r["total_liabilities"] = r.get("total_liab")
            r["total_equity"] = r.get("tot_share_equity_incl_min_int")
            mapped.append(AmazingDataBalanceSheetData(**r))
        return mapped


class AmazingDataCashFlowFetcher(
    Fetcher[AmazingDataCashFlowQueryParams, list[AmazingDataCashFlowData]],
    _StatementFetcherMixin,
):
    @staticmethod
    def transform_query(params: dict[str, Any]) -> AmazingDataCashFlowQueryParams:
        return AmazingDataCashFlowQueryParams(**params)

    @staticmethod
    def extract_data(query, credentials, **kwargs: Any) -> list[dict]:
        return _StatementFetcherMixin._extract(
            query,
            "cash_flow",
            "net_cash_flows_opera_act, net_cash_flows_inv_act, net_cash_flows_fin_act",
        )

    @staticmethod
    def transform_data(query, data: list[dict], **kwargs: Any):
        if not data:
            raise EmptyDataError(f"no cash flow rows for {query.symbol}")
        mapped = []
        for r in data:
            r = dict(r)
            r["net_cash_from_operating_activities"] = r.get("net_cash_flows_opera_act")
            r["net_cash_from_investing_activities"] = r.get("net_cash_flows_inv_act")
            r["net_cash_from_financing_activities"] = r.get("net_cash_flows_fin_act")
            mapped.append(AmazingDataCashFlowData(**r))
        return mapped
