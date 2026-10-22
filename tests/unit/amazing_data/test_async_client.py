"""测试 AmazingDataClient 的异步方法."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest


class TestAsyncAPIMethods:
    """测试异步 API 包装方法."""

    @pytest.mark.asyncio
    async def test_get_kline_async_calls_sync_method(self):
        """验证 get_kline_async 调用同步方法并返回结果."""
        from galaxy_core.amazing_data.api.client import AmazingDataClient

        # 创建模拟客户端
        client = AmazingDataClient.__new__(AmazingDataClient)
        client._is_logged_in = True
        client._ad = MagicMock()
        client._calendar = MagicMock()

        # 模拟同步方法的返回值
        mock_result = {
            "600000.SH": pd.DataFrame({
                "open": [10.0, 11.0],
                "close": [10.5, 11.5],
            })
        }

        with patch.object(client, "get_kline", return_value=mock_result) as mock_sync:
            result = await client.get_kline_async(
                code_list=["600000.SH"],
                begin_date=20230101,
                end_date=20231231,
                interval="day",
            )

            # 验证同步方法被调用
            mock_sync.assert_called_once_with(
                code_list=["600000.SH"],
                begin_date=20230101,
                end_date=20231231,
                interval="day",
                begin_time=None,
                end_time=None,
            )

            # 验证返回值
            assert result == mock_result
            assert "600000.SH" in result

    @pytest.mark.asyncio
    async def test_get_kline_async_with_optional_params(self):
        """验证 get_kline_async 正确传递可选参数."""
        from galaxy_core.amazing_data.api.client import AmazingDataClient

        client = AmazingDataClient.__new__(AmazingDataClient)
        client._is_logged_in = True

        mock_result = {}

        with patch.object(client, "get_kline", return_value=mock_result) as mock_sync:
            await client.get_kline_async(
                code_list=["600000.SH"],
                begin_date=20230101,
                end_date=20231231,
                interval="day",
                begin_time=93000000,
                end_time=150000000,
            )

            mock_sync.assert_called_once_with(
                code_list=["600000.SH"],
                begin_date=20230101,
                end_date=20231231,
                interval="day",
                begin_time=93000000,
                end_time=150000000,
            )

    @pytest.mark.asyncio
    async def test_get_stock_list_async_calls_sync_method(self):
        """验证 get_stock_list_async 调用同步方法."""
        from galaxy_core.amazing_data.api.client import AmazingDataClient

        client = AmazingDataClient.__new__(AmazingDataClient)
        client._is_logged_in = True

        mock_result = pd.DataFrame({
            "code": ["600000.SH", "600001.SH"],
            "name": ["浦发银行", "邯郸钢铁"],
        })

        with patch.object(client, "get_stock_list", return_value=mock_result) as mock_sync:
            result = await client.get_stock_list_async(security_type="EXTRA_STOCK_A")

            mock_sync.assert_called_once_with(security_type="EXTRA_STOCK_A")
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_listing_dates_async_calls_sync_method(self):
        """验证 get_listing_dates_async 调用同步方法."""
        from galaxy_core.amazing_data.api.client import AmazingDataClient

        client = AmazingDataClient.__new__(AmazingDataClient)
        client._is_logged_in = True

        mock_result = {"600000.SH": "19991110", "600001.SH": None}

        with patch.object(client, "get_listing_dates", return_value=mock_result) as mock_sync:
            result = await client.get_listing_dates_async(
                symbols=["600000.SH", "600001.SH"],
                security_type="EXTRA_STOCK_A",
            )

            mock_sync.assert_called_once_with(
                symbols=["600000.SH", "600001.SH"],
                security_type="EXTRA_STOCK_A",
            )
            assert result["600000.SH"] == "19991110"
            assert result["600001.SH"] is None

    @pytest.mark.asyncio
    async def test_get_hist_code_list_async_calls_sync_method(self):
        """验证 get_hist_code_list_async 调用同步方法."""
        from galaxy_core.amazing_data.api.client import AmazingDataClient

        client = AmazingDataClient.__new__(AmazingDataClient)
        client._is_logged_in = True

        mock_result = ["600000.SH", "600001.SH"]

        with patch.object(client, "get_hist_code_list", return_value=mock_result) as mock_sync:
            result = await client.get_hist_code_list_async(
                security_type="EXTRA_STOCK_A",
                start_date=20230101,
                end_date=20231231,
                local_path="/tmp/test",
            )

            mock_sync.assert_called_once_with(
                security_type="EXTRA_STOCK_A",
                start_date=20230101,
                end_date=20231231,
                local_path="/tmp/test",
            )
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_async_methods_do_not_block_event_loop(self):
        """验证异步方法不阻塞事件循环.

        通过并发执行多个异步调用来验证。
        """
        from galaxy_core.amazing_data.api.client import AmazingDataClient

        client = AmazingDataClient.__new__(AmazingDataClient)
        client._is_logged_in = True

        call_count = 0

        def mock_query(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # 模拟一些处理时间
            import time
            time.sleep(0.01)
            return {"600000.SH": pd.DataFrame()}

        with patch.object(client, "get_kline", side_effect=mock_query):
            # 并发执行3个调用
            results = await asyncio.gather(
                client.get_kline_async(
                    code_list=["600000.SH"],
                    begin_date=20230101,
                    end_date=20230131,
                    interval="day",
                ),
                client.get_kline_async(
                    code_list=["600001.SH"],
                    begin_date=20230101,
                    end_date=20230131,
                    interval="day",
                ),
                client.get_kline_async(
                    code_list=["600002.SH"],
                    begin_date=20230101,
                    end_date=20230131,
                    interval="day",
                ),
            )

            # 验证所有调用都完成
            assert len(results) == 3
            assert call_count == 3