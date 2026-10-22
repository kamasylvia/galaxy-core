"""行业指数数据提供者端口 — 对接 3.5.13 接口.

提供行业指数基本信息/成分股/日权重/日行情四个能力的 async 契约。
行业指数日行情是行业指数唯一的 OHLCV 源（不通过 query_kline）。
"""

from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class IndustryIndexProviderPort(Protocol):
    """行业指数数据提供者接口（async，to_thread 集中在 adapter）."""

    async def get_industry_base_info(
        self,
        local_path: str,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """获取行业指数基本信息（纯目录数据，无 code_list 参数）.

        Args:
            local_path: 本地缓存绝对路径
            is_local: True 仅本地缓存；False 强制服务器获取（首次必须 False）

        Returns:
            DataFrame，列为 INDEX_CODE/INDUSTRY_CODE/LEVEL_TYPE/LEVEL*_NAME/IS_PUB/CHANGE_REASON
        """
        ...

    async def get_industry_constituent(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """获取行业指数成分股.

        Args:
            code_list: 行业指数代码列表（仅取自 get_industry_base_info 返回的 INDEX_CODE）
            local_path: 本地缓存绝对路径
            is_local: 本地缓存方案开关

        Returns:
            {index_code: DataFrame}，列为 INDEX_CODE/CON_CODE/INDATE/OUTDATE/INDEX_NAME
        """
        ...

    async def get_industry_weight(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        """获取行业指数成分股日权重.

        Args:
            code_list: 行业指数代码列表
            local_path: 本地缓存绝对路径
            is_local: 本地缓存方案开关
            begin_date: 起始交易日期 YYYYMMDD（增量同步用）
            end_date: 截止交易日期 YYYYMMDD

        Returns:
            {index_code: DataFrame}，列为 WEIGHT/CON_CODE/TRADE_DATE/INDEX_CODE
        """
        ...

    async def get_industry_daily(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        """获取行业指数日行情（含 PB/PE/市值，行业指数唯一行情源）.

        Args:
            code_list: 行业指数代码列表
            local_path: 本地缓存绝对路径
            is_local: 本地缓存方案开关
            begin_date: 起始交易日期 YYYYMMDD（增量同步用）
            end_date: 截止交易日期 YYYYMMDD

        Returns:
            {index_code: DataFrame}，列为 OPEN/HIGH/CLOSE/LOW/AMOUNT/VOLUME/PB/PE/TOTAL_CAP 等
        """
        ...

    async def get_industry_index_codes(self, local_path: str) -> list[str]:
        """获取行业指数代码列表（从 get_industry_base_info 提取 INDEX_CODE）.

        用于驱动成分股/权重/日行情同步的 code_list。

        Args:
            local_path: 本地缓存绝对路径

        Returns:
            行业指数代码列表
        """
        ...
