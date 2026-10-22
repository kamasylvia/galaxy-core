"""ReferenceProviderAdapter 测试."""

import asyncio
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from galaxy_core.amazing_data.api.adapters.reference_provider_adapter import ReferenceProviderAdapter
from galaxy_core.domain.ports.reference_provider import ReferenceProviderPort
from galaxy_core.domain.value_objects import BackwardFactor, StockBasic


class TestReferenceProviderAdapterProtocol:
    """验证 ReferenceProviderAdapter 满足 ReferenceProviderPort Protocol."""

    def test_adapter_is_protocol_instance(self):
        """ReferenceProviderAdapter 应满足 ReferenceProviderPort Protocol."""
        mock_client = MagicMock()
        adapter = ReferenceProviderAdapter(mock_client)
        assert isinstance(adapter, ReferenceProviderPort)

    def test_adapter_has_async_get_stock_basic(self):
        """get_stock_basic 应为 async 方法."""
        mock_client = MagicMock()
        adapter = ReferenceProviderAdapter(mock_client)
        import inspect
        assert inspect.iscoroutinefunction(adapter.get_stock_basic)

    def test_adapter_has_async_get_backward_factor(self):
        """get_backward_factor 应为 async 方法."""
        mock_client = MagicMock()
        adapter = ReferenceProviderAdapter(mock_client)
        import inspect
        assert inspect.iscoroutinefunction(adapter.get_backward_factor)


class TestReferenceProviderAdapterGetStockBasic:
    """get_stock_basic 方法测试."""

    def test_returns_stock_basics(self):
        """应返回 StockBasic 列表."""
        mock_client = MagicMock()
        df = pd.DataFrame(
            {
                "LISTDATE": ["20200101", "20210101"],
                "stock_name": ["华夏上证50ETF", "华泰柏瑞沪深300ETF"],
                "market": ["SH", "SH"],
            },
            index=["510050.SH", "510300.SH"],
        )
        df.index.name = "code"
        mock_client.get_stock_basic.return_value = df

        adapter = ReferenceProviderAdapter(mock_client)
        result = asyncio.run(adapter.get_stock_basic(["510050.SH", "510300.SH"]))

        assert len(result) == 2
        assert all(isinstance(b, StockBasic) for b in result)
        assert result[0].symbol == "510050.SH"
        assert result[0].stock_name == "华夏上证50ETF"

    def test_handles_empty_dataframe(self):
        """空 DataFrame 应返回空列表."""
        mock_client = MagicMock()
        mock_client.get_stock_basic.return_value = pd.DataFrame()

        adapter = ReferenceProviderAdapter(mock_client)
        result = asyncio.run(adapter.get_stock_basic(["510050.SH"]))
        assert result == []


class TestReferenceProviderAdapterGetBackwardFactor:
    """get_backward_factor 方法测试."""

    def test_returns_backward_factors(self):
        """应返回 BackwardFactor 列表."""
        mock_client = MagicMock()
        # SDK 返回 DataFrame: index=日期, columns=股票代码
        df = pd.DataFrame(
            {
                "510050.SH": [1.0, 1.05, 1.10],
                "510300.SH": [1.0, 1.02, 1.08],
            },
            index=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
        )
        df.index.name = "trade_date"
        mock_client.get_backward_factor.return_value = df

        adapter = ReferenceProviderAdapter(mock_client)
        result = asyncio.run(adapter.get_backward_factor(["510050.SH", "510300.SH"]))

        # 3 天 x 2 只股票 = 6 条
        assert len(result) == 6
        assert all(isinstance(f, BackwardFactor) for f in result)

    def test_handles_empty_dataframe(self):
        """空 DataFrame 应返回空列表."""
        mock_client = MagicMock()
        mock_client.get_backward_factor.return_value = pd.DataFrame()

        adapter = ReferenceProviderAdapter(mock_client)
        result = asyncio.run(adapter.get_backward_factor(["510050.SH"]))
        assert result == []

    def test_handles_none_dataframe(self):
        """None DataFrame 应返回空列表."""
        mock_client = MagicMock()
        mock_client.get_backward_factor.return_value = None

        adapter = ReferenceProviderAdapter(mock_client)
        result = asyncio.run(adapter.get_backward_factor(["510050.SH"]))
        assert result == []

    def test_calls_to_thread(self):
        """应使用 asyncio.to_thread 包装 SDK 调用."""
        mock_client = MagicMock()
        mock_client.get_backward_factor.return_value = pd.DataFrame()

        adapter = ReferenceProviderAdapter(mock_client)

        async def run():
            with patch("galaxy_core.amazing_data.api.adapters.reference_provider_adapter.asyncio.to_thread") as mock_to_thread:
                mock_to_thread.return_value = pd.DataFrame()
                await adapter.get_backward_factor(["510050.SH"])
                mock_to_thread.assert_called_once()

        asyncio.run(run())


class TestReferenceProviderAdapterApiTimeout:
    """SDK 阻塞型调用超时测试（AGENTS.md 2026-07-07）.

    get_code_info / get_stock_basic_df 用 asyncio.wait_for 包裹 to_thread，
    SDK 阻塞超过 self._api_timeout 秒应 raise asyncio.TimeoutError，
    避免 scheduler 调用链被无限挂起（如 EXTRA_INDEX_A 曾观察的 SDK 端阻塞）。
    """

    def test_get_code_info_raises_on_timeout(self):
        """get_code_info SDK 阻塞超 self._api_timeout → raise TimeoutError."""
        mock_client = MagicMock()

        async def slow_coro(*args, **kwargs):
            """模拟 SDK 阻塞型调用的 awaitable."""
            await asyncio.sleep(1)
            return pd.DataFrame()

        async def run():
            adapter = ReferenceProviderAdapter(mock_client)
            adapter._api_timeout = 0.01  # 测试用极短超时

            with patch(
                "galaxy_core.amazing_data.api.adapters.reference_provider_adapter.asyncio.to_thread",
                side_effect=slow_coro,
            ):
                with pytest.raises(asyncio.TimeoutError):
                    await adapter.get_code_info("EXTRA_INDEX_A")

        asyncio.run(run())

    def test_get_stock_basic_df_raises_on_timeout(self):
        """get_stock_basic_df SDK 阻塞超 self._api_timeout → raise TimeoutError."""
        mock_client = MagicMock()

        async def slow_coro(*args, **kwargs):
            await asyncio.sleep(1)
            return pd.DataFrame()

        async def run():
            adapter = ReferenceProviderAdapter(mock_client)
            adapter._api_timeout = 0.01

            with patch(
                "galaxy_core.amazing_data.api.adapters.reference_provider_adapter.asyncio.to_thread",
                side_effect=slow_coro,
            ):
                with pytest.raises(asyncio.TimeoutError):
                    await adapter.get_stock_basic_df(["600000.SH"])

        asyncio.run(run())

    def test_get_code_info_returns_df_within_timeout(self):
        """SDK 在超时内返回 → 正常返回 DataFrame（不 raise）。"""
        mock_client = MagicMock()
        expected_df = pd.DataFrame(
            {"symbol": ["A50华宝"], "list_day": ["20240318"]},
            index=pd.Index(["159596.SZ"], name="code_market"),
        )

        async def run():
            adapter = ReferenceProviderAdapter(mock_client)
            adapter._api_timeout = 5  # 足够长

            with patch(
                "galaxy_core.amazing_data.api.adapters.reference_provider_adapter.asyncio.to_thread",
                return_value=expected_df,
            ):
                result = await adapter.get_code_info("EXTRA_ETF")
                assert result is expected_df

        asyncio.run(run())
