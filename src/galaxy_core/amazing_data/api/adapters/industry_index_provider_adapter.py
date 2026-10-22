"""行业指数数据提供者适配器 — 包装 AmazingDataClient 为 IndustryIndexProviderPort.

asyncio.to_thread() 集中在此 adapter 层，应用层代码完全异步。
本适配器为薄封装：返回原始 SDK DataFrame，DataFrame→dataclass 转换由 store adapter 完成。

所有 to_thread 调用都包 asyncio.wait_for(timeout=self._api_timeout) 超时保护
(AGENTS.md 2026-07-14 P1 + 2026-07-11「修复 3」要求所有 adapter to_thread 必须包;
原 industry adapter 整个漏了)。SDK 端挂起(hrtimer sleep)时协程无限阻塞,
会卡死整 industry job + scheduler 调用链。超时即 raise TimeoutError 传到
sync_with_retry 触发重试。注:超时只取消主任务 await,to_thread 启动的线程
无法取消(SDK 线程继续跑到自行结束),但控制流已返回。
"""

import asyncio
import logging
from pathlib import Path

import pandas as pd

from galaxy_core.amazing_data.api.client import AmazingDataClient
from galaxy_core.shared_kernel.utils.config_loader import get_section

logger = logging.getLogger(__name__)


class IndustryIndexProviderAdapter:
    """IndustryIndexProviderPort 实现 — 包装 AmazingDataClient 行业指数接口."""

    def __init__(self, client: AmazingDataClient) -> None:
        self._client = client
        # SDK 阻塞型调用的 asyncio.wait_for 超时上限。防止 to_thread 包装的
        # SDK 调用无限阻塞(AGENTS.md 2026-07-11「修复 3」、2026-07-14 P1)。
        # 默认 600s(覆盖 industry_weight 全量 511 只 × 大窗口的正常响应)。
        self._api_timeout = get_section("amazing_data").get("api_timeout_seconds", 600)

    def _get_local_path(self) -> str:
        """从配置获取本地缓存绝对路径（SDK 要求绝对路径）."""
        raw_cache = get_section("amazing_data").get("local_path", "./data/local_cache/")
        local_path = str(Path(raw_cache).resolve())
        if raw_cache.endswith("/"):
            local_path += "/"
        return local_path

    async def get_industry_base_info(
        self,
        local_path: str,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """获取行业指数基本信息（纯目录数据，无 code_list）."""
        data: pd.DataFrame = await asyncio.wait_for(
            asyncio.to_thread(
                self._client.get_industry_base_info,
                local_path=local_path,
                is_local=is_local,
            ),
            timeout=self._api_timeout,
        )
        logger.debug(f"获取到行业指数基本信息: {0 if data is None else len(data)} 行")
        return data if isinstance(data, pd.DataFrame) else pd.DataFrame()

    async def get_industry_constituent(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """获取行业指数成分股."""
        data: dict[str, pd.DataFrame] = await asyncio.wait_for(
            asyncio.to_thread(
                self._client.get_industry_constituent,
                code_list=code_list,
                local_path=local_path,
                is_local=is_local,
            ),
            timeout=self._api_timeout,
        )
        data = data if isinstance(data, dict) else {}

        logger.debug(f"获取到 {len(data)} 个指数数据")

        return data

    async def get_industry_weight(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        """获取行业指数日权重."""
        kwargs_iw: dict[str, object] = {
            "code_list": code_list,
            "local_path": local_path,
            "is_local": is_local,
        }
        if begin_date is not None:
            kwargs_iw["begin_date"] = begin_date
        if end_date is not None:
            kwargs_iw["end_date"] = end_date
        data: dict[str, pd.DataFrame] = await asyncio.wait_for(
            asyncio.to_thread(self._client.get_industry_weight, **kwargs_iw),
            timeout=self._api_timeout,
        )
        data = data if isinstance(data, dict) else {}

        logger.debug(f"获取到 {len(data)} 个指数数据")

        return data

    async def get_industry_daily(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        """获取行业指数日行情（含 PB/PE/市值，行业指数唯一行情源）."""
        kwargs_d: dict[str, object] = {
            "code_list": code_list,
            "local_path": local_path,
            "is_local": is_local,
        }
        if begin_date is not None:
            kwargs_d["begin_date"] = begin_date
        if end_date is not None:
            kwargs_d["end_date"] = end_date
        data: dict[str, pd.DataFrame] = await asyncio.wait_for(
            asyncio.to_thread(self._client.get_industry_daily, **kwargs_d),
            timeout=self._api_timeout,
        )
        data = data if isinstance(data, dict) else {}

        logger.debug(f"获取到 {len(data)} 个指数数据")

        return data

    async def get_industry_index_codes(self, local_path: str) -> list[str]:
        """获取行业指数代码列表（从 get_industry_base_info 提取 INDEX_CODE）.

        Args:
            local_path: 本地缓存绝对路径

        Returns:
            行业指数代码列表
        """
        df = await self.get_industry_base_info(local_path=local_path, is_local=True)
        if df is None or df.empty or "INDEX_CODE" not in df.columns:
            return []
        return df["INDEX_CODE"].dropna().astype(str).unique().tolist()

