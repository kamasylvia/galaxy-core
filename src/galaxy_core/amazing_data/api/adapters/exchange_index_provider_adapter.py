"""交易所指数数据提供者适配器 — 包装 AmazingDataClient 为 ExchangeIndexProviderPort.

asyncio.to_thread() 集中在此 adapter 层，应用层代码完全异步。
本适配器为薄封装：返回原始 SDK DataFrame，DataFrame→dataclass 转换由 store adapter 完成。
"""

import asyncio
import logging
from pathlib import Path

import pandas as pd

from galaxy_core.amazing_data.api.client import AmazingDataClient
from galaxy_core.shared_kernel.utils.config_loader import get_section

logger = logging.getLogger(__name__)


class ExchangeIndexProviderAdapter:
    """ExchangeIndexProviderPort 实现 — 包装 AmazingDataClient 交易所指数接口."""

    def __init__(self, client: AmazingDataClient) -> None:
        self._client = client

    def _get_local_path(self) -> str:
        """从配置获取本地缓存绝对路径（SDK 要求绝对路径）.

        与 ReferenceDataSyncJob/InfoDataProviderAdapter 的 _get_local_path 一致。
        """
        raw_cache = get_section("amazing_data").get("local_path", "./data/local_cache/")
        local_path = str(Path(raw_cache).resolve())
        if raw_cache.endswith("/"):
            local_path += "/"
        return local_path

    async def get_index_constituent(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """获取交易所指数成分股（asyncio.to_thread 包装同步 SDK 调用）."""
        data: dict[str, pd.DataFrame] = await asyncio.to_thread(
            self._client.get_index_constituent,
            code_list=code_list,
            local_path=local_path,
            is_local=is_local,
        )
        data = data if isinstance(data, dict) else {}

        logger.debug(f"获取到 {len(data)} 个指数数据")

        return data

    async def get_index_weight(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        """获取交易所指数日权重（asyncio.to_thread 包装同步 SDK 调用）."""
        kwargs: dict[str, object] = {
            "code_list": code_list,
            "local_path": local_path,
            "is_local": is_local,
        }
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date
        data: dict[str, pd.DataFrame] = await asyncio.to_thread(
            self._client.get_index_weight, **kwargs
        )
        data = data if isinstance(data, dict) else {}

        logger.debug(f"获取到 {len(data)} 个指数数据")

        return data

    async def get_index_code_list(self, security_type: str) -> list[str]:
        """获取交易所指数代码列表（复用 get_stock_list 的 SDK 调用）.

        Args:
            security_type: 代码类型，如 EXTRA_INDEX_A / SH_INDEX / SZ_INDEX

        Returns:
            指数代码列表

        SDK 的 get_code_info 返回 DataFrame，代码在 index（index 名为
        code_market），而非普通列——与 ReferenceProviderAdapter.get_stock_list
        一致。直接取 df.index 即可。
        """
        df: pd.DataFrame = await asyncio.to_thread(
            self._client.get_stock_list,
            security_type=security_type,
        )
        if df is None or df.empty:
            return []

        # code 在 index（code_market），与 reference adapter 同模式
        return df.index.dropna().astype(str).tolist()
