"""财务数据提供者端口."""

from typing import Protocol, runtime_checkable

from galaxy_core.domain.value_objects import FinancialRecord


@runtime_checkable
class FinancialDataProviderPort(Protocol):
    """财务数据提供者接口 — 对接 AmazingData SDK（async，to_thread 集中在 adapter）.

    6 个查询方法对应 6 个 InfoData API 接口：
    - get_balance_sheet: 资产负债表
    - get_cash_flow: 现金流量表
    - get_income_statement: 利润表
    - get_profit_express: 业绩快报
    - get_profit_notice: 业绩预告
    - get_dividend: 分红配送

    参数:
        symbols: 代码列表（如 ["600000.SH", "000001.SZ"]）
        begin_date: 报告期起始，YYYYMMDD 格式字符串
        end_date: 报告期结束，YYYYMMDD 格式字符串
    """

    async def get_balance_sheet(
        self,
        symbols: list[str],
        begin_date: str,
        end_date: str,
    ) -> list[FinancialRecord]: ...

    async def get_cash_flow(
        self,
        symbols: list[str],
        begin_date: str,
        end_date: str,
    ) -> list[FinancialRecord]: ...

    async def get_income_statement(
        self,
        symbols: list[str],
        begin_date: str,
        end_date: str,
    ) -> list[FinancialRecord]: ...

    async def get_profit_express(
        self,
        symbols: list[str],
        begin_date: str,
        end_date: str,
    ) -> list[FinancialRecord]: ...

    async def get_profit_notice(
        self,
        symbols: list[str],
        begin_date: str,
        end_date: str,
    ) -> list[FinancialRecord]: ...

    async def get_dividend(
        self,
        symbols: list[str],
        begin_date: str,
        end_date: str,
    ) -> list[FinancialRecord]: ...
