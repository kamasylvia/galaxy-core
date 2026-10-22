"""KlineProviderAdapter 测试."""

import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from galaxy_core.amazing_data.api.adapters.kline_provider_adapter import KlineProviderAdapter
from galaxy_core.domain.ports.kline_provider import KlineProviderPort
from galaxy_core.domain.value_objects import Interval, KlineBar, SecurityType, StockInfo
from galaxy_core.shared_kernel.utils.constants import CST


class TestKlineProviderAdapterProtocol:
    """验证 KlineProviderAdapter 满足 KlineProviderPort Protocol."""

    def test_adapter_is_protocol_instance(self):
        """KlineProviderAdapter 应满足 KlineProviderPort Protocol."""
        mock_client = MagicMock()
        adapter = KlineProviderAdapter(mock_client)
        assert isinstance(adapter, KlineProviderPort)

    def test_adapter_has_async_get_kline(self):
        """get_kline 应为 async 方法."""
        mock_client = MagicMock()
        adapter = KlineProviderAdapter(mock_client)
        import inspect
        assert inspect.iscoroutinefunction(adapter.get_kline)

    def test_adapter_has_async_get_stock_list(self):
        """get_stock_list 应为 async 方法."""
        mock_client = MagicMock()
        adapter = KlineProviderAdapter(mock_client)
        import inspect
        assert inspect.iscoroutinefunction(adapter.get_stock_list)

    def test_adapter_has_async_get_listing_dates(self):
        """get_listing_dates 应为 async 方法."""
        mock_client = MagicMock()
        adapter = KlineProviderAdapter(mock_client)
        import inspect
        assert inspect.iscoroutinefunction(adapter.get_listing_dates)


class TestKlineProviderAdapterGetKline:
    """get_kline 方法测试."""

    def test_returns_kline_bars(self):
        """应返回 KlineBar 列表."""
        mock_client = MagicMock()
        # SDK 返回 dict[str, DataFrame]
        df = pd.DataFrame(
            {
                "open": [10.0, 10.5],
                "high": [11.0, 11.5],
                "low": [9.5, 10.0],
                "close": [10.5, 11.0],
                "volume": [1000, 2000],
                "amount": [10500.0, 22000.0],
            },
            index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
        )
        df.index.name = "trade_time"
        mock_client.get_kline.return_value = {"600000.SH": df}

        adapter = KlineProviderAdapter(mock_client)
        result = asyncio.run(
            adapter.get_kline(["600000.SH"], Interval.DAY, "20240101", "20240131")
        )

        assert len(result) == 2
        assert all(isinstance(bar, KlineBar) for bar in result)
        assert result[0].symbol == "600000.SH"
        # 2026-07-17:trade_time 是 CST aware datetime,比较 wall-clock
        assert result[0].trade_time == datetime(2024, 1, 2, tzinfo=CST)
        assert result[0].open == 10.0

    def test_handles_empty_dataframe(self):
        """空 DataFrame 应返回空列表."""
        mock_client = MagicMock()
        mock_client.get_kline.return_value = {"600000.SH": pd.DataFrame()}

        adapter = KlineProviderAdapter(mock_client)
        result = asyncio.run(
            adapter.get_kline(["600000.SH"], Interval.DAY, "20240101", "20240131")
        )
        assert result == []

    def test_handles_none_dataframe(self):
        """None DataFrame 应跳过."""
        mock_client = MagicMock()
        mock_client.get_kline.return_value = {"600000.SH": None}

        adapter = KlineProviderAdapter(mock_client)
        result = asyncio.run(
            adapter.get_kline(["600000.SH"], Interval.DAY, "20240101", "20240131")
        )
        assert result == []

    def test_calls_to_thread(self):
        """应使用 asyncio.to_thread 包装 SDK 调用."""
        mock_client = MagicMock()
        mock_client.get_kline.return_value = {}

        adapter = KlineProviderAdapter(mock_client)

        async def run():
            with patch("galaxy_core.amazing_data.api.adapters.kline_provider_adapter.asyncio.to_thread") as mock_to_thread:
                mock_to_thread.return_value = {}
                result = await adapter.get_kline(["600000.SH"], Interval.DAY, "20240101", "20240131")
                mock_to_thread.assert_called_once()
                return result

        asyncio.run(run())

    def test_infers_security_type(self):
        """应推断证券类型."""
        mock_client = MagicMock()
        df = pd.DataFrame(
            {"open": [10.0], "high": [11.0], "low": [9.5], "close": [10.5], "volume": [1000], "amount": [10500.0]},
            index=pd.to_datetime(["2024-01-02"]),
        )
        df.index.name = "trade_time"
        mock_client.get_kline.return_value = {"510050.SH": df}

        adapter = KlineProviderAdapter(mock_client)
        result = asyncio.run(
            adapter.get_kline(["510050.SH"], Interval.DAY, "20240101", "20240131")
        )

        assert len(result) == 1
        # 510050.SH 是 ETF
        assert result[0].security_type in (SecurityType.SH_ETF, SecurityType.EXTRA_ETF)


class TestKlineProviderAdapterMarketGrouping:
    """按市场分组(SH/SZ/BJ)测试 — 2026-08-06 SDK 对混合市场 code_list 静默丢 codes."""

    def test_group_by_market_splits_markets(self):
        """混合市场应拆为 SH/SZ/BJ 三组,保持顺序."""
        adapter = KlineProviderAdapter(MagicMock())
        groups = adapter._group_by_market(
            ["600000.SH", "000001.SZ", "873124.BJ", "600001.SH"]
        )
        assert list(groups.keys()) == ["SH", "SZ", "BJ"]
        assert groups["SH"] == ["600000.SH", "600001.SH"]
        assert groups["SZ"] == ["000001.SZ"]
        assert groups["BJ"] == ["873124.BJ"]

    def test_single_market_does_not_split(self):
        """纯沪深 code_list 保持单次调用(不拆)."""
        mock_client = MagicMock()
        mock_client.get_kline.return_value = {}
        adapter = KlineProviderAdapter(mock_client)

        async def run():
            with patch("galaxy_core.amazing_data.api.adapters.kline_provider_adapter.asyncio.to_thread") as mock_to_thread:
                mock_to_thread.return_value = {}
                await adapter.get_kline(
                    ["600000.SH", "600001.SH"], Interval.DAY, "20240101", "20240131"
                )
                # 单市场 → 只调一次 SDK
                mock_to_thread.assert_called_once()

        asyncio.run(run())

    def test_mixed_market_calls_sdk_per_group(self):
        """沪深+BJ 混合应每市场独立调 SDK(3 次)."""
        mock_client = MagicMock()
        df = pd.DataFrame(
            {"open": [10.0], "high": [11.0], "low": [9.5], "close": [10.5],
             "volume": [1000], "amount": [10500.0]},
            index=pd.to_datetime(["2026-08-05"]),
        )
        df.index.name = "trade_time"
        # SDK 每市场返回对应 code 数据
        def fake_get_kline(code_list, **kwargs):
            return {code: df for code in code_list}

        mock_client.get_kline.side_effect = fake_get_kline
        adapter = KlineProviderAdapter(mock_client)

        result = asyncio.run(
            adapter.get_kline(
                ["600000.SH", "000001.SZ", "873124.BJ"],
                Interval.DAY, "20260805", "20260805",
            )
        )

        # 3 个市场组 → SDK 调 3 次
        assert mock_client.get_kline.call_count == 3
        calls = [c.kwargs["code_list"] for c in mock_client.get_kline.call_args_list]
        assert calls == [["600000.SH"], ["000001.SZ"], ["873124.BJ"]]
        assert len(result) == 3

    def test_mixed_market_group_failure_raises(self):
        """某市场组失败应 raise(不静默丢),让上层重试."""
        mock_client = MagicMock()
        df = pd.DataFrame(
            {"open": [10.0], "high": [11.0], "low": [9.5], "close": [10.5],
             "volume": [1000], "amount": [10500.0]},
            index=pd.to_datetime(["2026-08-05"]),
        )
        df.index.name = "trade_time"

        def fake_get_kline(code_list, **kwargs):
            if code_list[0].endswith(".BJ"):
                raise TimeoutError("SDK 挂起")
            return {code: df for code in code_list}

        mock_client.get_kline.side_effect = fake_get_kline
        adapter = KlineProviderAdapter(mock_client)

        with pytest.raises(TimeoutError):
            asyncio.run(
                adapter.get_kline(
                    ["600000.SH", "873124.BJ"], Interval.DAY, "20260805", "20260805"
                )
            )


class TestKlineProviderAdapterGetStockList:
    """get_stock_list 方法测试."""

    def test_returns_stock_infos(self):
        """应返回 StockInfo 列表."""
        mock_client = MagicMock()
        df = pd.DataFrame(
            {"LISTDATE": ["20200101", "20210101"]},
            index=["510050.SH", "510300.SH"],
        )
        df.index.name = "code"
        mock_client.get_stock_list.return_value = df

        adapter = KlineProviderAdapter(mock_client)
        result = asyncio.run(adapter.get_stock_list("EXTRA_ETF"))

        assert len(result) == 2
        assert all(isinstance(info, StockInfo) for info in result)

    def test_handles_empty_dataframe(self):
        """空 DataFrame 应返回空列表."""
        mock_client = MagicMock()
        mock_client.get_stock_list.return_value = pd.DataFrame()

        adapter = KlineProviderAdapter(mock_client)
        result = asyncio.run(adapter.get_stock_list("EXTRA_ETF"))
        assert result == []


class TestKlineProviderAdapterGetListingDates:
    """get_listing_dates 方法测试."""

    def test_returns_dates_dict(self):
        """应返回 {symbol: date} 字典."""
        mock_client = MagicMock()
        mock_client.get_listing_dates.return_value = {
            "510050.SH": "20200101",
            "510300.SH": None,
        }

        adapter = KlineProviderAdapter(mock_client)
        result = asyncio.run(adapter.get_listing_dates(["510050.SH", "510300.SH"]))

        assert "510050.SH" in result
        assert result["510050.SH"].year == 2020
        # None 日期不应出现在结果中
        assert "510300.SH" not in result
