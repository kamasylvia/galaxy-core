"""交易所指数数据提供者端口 — 对接 3.5.12 接口.

提供 get_index_constituent / get_index_weight 两个能力的 async 契约。
SDK 调用经 asyncio.to_thread 集中在 adapter 层，本端口不含同步细节。
"""

from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class ExchangeIndexProviderPort(Protocol):
    """交易所指数数据提供者接口（async，to_thread 集中在 adapter）."""

    async def get_index_constituent(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """获取交易所指数成分股.

        Args:
            code_list: 指数代码列表（约 600 只常用指数，不支持则返回空）
            local_path: 本地缓存绝对路径
            is_local: True 仅本地缓存；False 强制从服务器获取（首次必须 False）

        Returns:
            {index_code: DataFrame}，DataFrame 列为 INDEX_CODE/CON_CODE/INDATE/OUTDATE/INDEX_NAME
        """
        ...

    async def get_index_weight(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        """获取交易所指数成分股日权重.

        SDK 硬限制：仅支持 5 个指数
        （000016.SH / 000300.SH / 000905.SH / 000906.SH / 000852.SH）。

        Args:
            code_list: 指数代码列表（必须为上述 5 个之一）
            local_path: 本地缓存绝对路径
            is_local: 本地缓存方案开关
            begin_date: 起始变动日期 YYYYMMDD（增量同步用）
            end_date: 截止变动日期 YYYYMMDD

        Returns:
            {index_code: DataFrame}，列为 INDEX_CODE/CON_CODE/TRADE_DATE/TOTAL_SHARE 等
        """
        ...

    async def get_index_code_list(self, security_type: str) -> list[str]:
        """获取交易所指数代码列表（EXTRA_INDEX_A 等）.

        复用 BaseData.get_code_list 语义，用于驱动成分股同步的 code_list。

        Args:
            security_type: 代码类型，如 EXTRA_INDEX_A / SH_INDEX / SZ_INDEX

        Returns:
            指数代码列表
        """
        ...
