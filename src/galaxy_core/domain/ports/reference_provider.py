"""参考数据提供者端口."""

from datetime import date
from typing import Protocol, runtime_checkable

import pandas as pd

from galaxy_core.domain.value_objects import BackwardFactor, StockBasic


@runtime_checkable
class ReferenceProviderPort(Protocol):
    """参考数据提供者接口 — 对接 AmazingData SDK（async，to_thread 集中在 adapter）."""

    async def get_stock_basic(self, symbols: list[str]) -> list[StockBasic]: ...

    async def get_backward_factor(self, symbols: list[str]) -> list[BackwardFactor]: ...

    async def get_delist_date(self, symbol: str) -> date | None:
        """获取证券退市日期.

        Args:
            symbol: 证券代码

        Returns:
            退市日期，未退市则为 None
        """
        ...

    async def update_stock_basic_from_api(self, symbols: list[str]) -> None:
        """从 API 更新 stock_basic 表.

        用于确认流程中发现退市/未上市等情况时，更新 stock_basic 表。

        Args:
            symbols: 需要更新的证券代码列表
        """
        ...

    async def get_hist_code_list(
        self, security_type: str, start_date: int, end_date: int, local_path: str
    ) -> list[str]:
        """获取历史代码表.

        Args:
            security_type: 代码类型（如 EXTRA_ETF）
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            local_path: 本地缓存路径

        Returns:
            历史代码列表
        """
        ...

    async def get_stock_list(self, security_type: str) -> list[str]:
        """获取指定 security_type 的证券代码列表.

        Args:
            security_type: 代码类型名称（如 EXTRA_ETF, EXTRA_STOCK_A）

        Returns:
            code_market 格式的代码列表
        """
        ...

    async def get_listing_dates(
        self, symbols: list[str], security_type: str
    ) -> dict[str, str | None]:
        """获取证券上市日期.

        Args:
            symbols: 证券代码列表
            security_type: 代码类型，用于确定查询范围

        Returns:
            {symbol: YYYYMMDD} 字典，无上市日期则为 None
        """
        ...

    async def get_code_info(self, security_type: str) -> pd.DataFrame:
        """获取指定类型的证券代码信息.

        调用 SDK get_code_info，返回包含证券代码、简称、上市日期等信息的 DataFrame。
        主要用于 ETF 等无法通过 get_stock_basic 获取的类型。

        Args:
            security_type: 证券类型（如 EXTRA_ETF）

        Returns:
            原始 DataFrame（SDK 返回格式，index 为 code_market）
        """
        ...

    async def get_stock_basic_df(self, symbols: list[str]) -> pd.DataFrame:
        """获取证券基础信息原始 DataFrame.

        用于数据库记录构建（stock_basic 表结构）。

        Args:
            symbols: 证券代码列表

        Returns:
            原始 DataFrame（SDK 返回格式）
        """
        ...

    async def get_backward_factor_df(
        self, symbols: list[str], local_path: str
    ) -> pd.DataFrame:
        """获取后复权因子原始 DataFrame.

        用于数据库记录构建（复权因子宽格式）。

        Args:
            symbols: 证券代码列表
            local_path: 本地缓存路径

        Returns:
            原始 DataFrame（宽格式：index=日期, columns=股票代码）
        """
        ...
