"""Async CLI 入口测试模块.

测试 application/cli/commands 模块的异步 CLI 功能，包括：
- async_main() 函数行为
- handle_kline_command_async() 异步命令处理
- asyncio.run() 包装正确性
- 退出码语义（成功 0，失败 1）
- async database initialization 被调用
- sync operations 被 asyncio.to_thread 正确包装
"""

import argparse
import asyncio
import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

if "AmazingData" not in sys.modules:
    sys.modules["AmazingData"] = types.SimpleNamespace(
        login=lambda **kwargs: None,
        logout=lambda *args, **kwargs: None,
        BaseData=lambda: types.SimpleNamespace(get_calendar=lambda *args, **kwargs: []),
        InfoData=lambda: types.SimpleNamespace(),
        MarketData=lambda calendar: types.SimpleNamespace(query_kline=lambda **kwargs: {}),
    )

if "akshare" not in sys.modules:
    sys.modules["akshare"] = types.SimpleNamespace()

if "tgw" not in sys.modules:
    sys.modules["tgw"] = types.SimpleNamespace()

# Mock config_loader before importing galaxy_db_sync (override if exists)
config_loader_mock = types.ModuleType("galaxy_db_sync.shared_kernel.utils.config_loader")
config_loader_mock.get_config = lambda *args, **kwargs: {}
config_loader_mock.get_section = lambda *args, **kwargs: {}
sys.modules["galaxy_db_sync.shared_kernel.utils.config_loader"] = config_loader_mock

from galaxy_db_sync.application.cli.commands import async_main, main
from galaxy_db_sync.application.kline.command import handle_kline_command_async
from galaxy_db_sync.database.services.kline_completeness_checker import (
    CompletenessResult,
)


class TestAsyncCLIEntry(unittest.TestCase):
    """异步 CLI 入口测试类."""

    def test_handle_kline_command_async_returns_0_on_success(self):
        """Test async handler returns 0 on successful execution."""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval="day",
            start="20230101",
            end="20231231",
        )

        with (
            patch(
                "galaxy_db_sync.application.kline.command.async_db_manager.initialize"
            ) as mock_async_db_init,
            patch(
                "galaxy_db_sync.application.kline.command.parse_symbols",
                return_value=[("symbol", "600000.SH")],
            ),
            patch(
                "galaxy_db_sync.application.kline.command.get_valid_symbols_from_input",
                return_value=["600000.SH"],
            ),
            patch(
                "galaxy_db_sync.application.kline.command.resolve_default_start_date_for_interval",
                return_value="20230101",
            ),
            patch(
                "galaxy_db_sync.application.kline.command.resolve_default_end_date_for_interval",
                return_value="20231231",
            ),
            patch(
                "galaxy_db_sync.application.kline.command.validate_date_range",
                return_value=[],
            ),
            patch(
                "galaxy_db_sync.application.kline.command.get_sdk_interval_value",
                return_value=10008,
            ),
            patch(
                "galaxy_db_sync.application.kline.command._get_listing_dates",
                return_value={},
            ),
            patch(
                "galaxy_db_sync.application.kline.command.kline_completeness_checker.check",
                return_value=CompletenessResult(
                    is_complete=True,
                    missing_count=0,
                    total_count=10,
                    coverage_ratio=1.0,
                    missing_ranges=[],
                    check_method="short_period_trading_day",
                ),
            ),
            patch(
                "galaxy_db_sync.application.kline.command.sync_kline_data_async"
            ) as mock_sync_data,
        ):
            result = asyncio.run(handle_kline_command_async(args))

        self.assertEqual(result, 0)
        mock_async_db_init.assert_called_once()
        mock_sync_data.assert_not_called()

    def test_handle_kline_command_async_returns_1_on_error(self):
        """Test async handler returns 1 on failure."""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval="invalid_interval",
            start=None,
            end=None,
        )

        result = asyncio.run(handle_kline_command_async(args))

        self.assertEqual(result, 1)

    def test_handle_kline_command_async_wraps_sync_sdk_calls(self):
        """Test async handler wraps sync SDK calls with asyncio.to_thread."""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval="day",
            start="20230101",
            end="20231231",
        )

        with (
            patch(
                "galaxy_db_sync.application.kline.command.async_db_manager.initialize"
            ),
            patch(
                "galaxy_db_sync.application.kline.command.parse_symbols",
                return_value=[("symbol", "600000.SH")],
            ),
            patch(
                "galaxy_db_sync.application.kline.command.get_valid_symbols_from_input",
                return_value=["600000.SH"],
            ),
            patch(
                "galaxy_db_sync.application.kline.command.resolve_default_start_date_for_interval",
                return_value="20230101",
            ),
            patch(
                "galaxy_db_sync.application.kline.command.resolve_default_end_date_for_interval",
                return_value="20231231",
            ),
            patch(
                "galaxy_db_sync.application.kline.command.validate_date_range",
                return_value=[],
            ),
            patch(
                "galaxy_db_sync.application.kline.command.get_sdk_interval_value",
                return_value=10008,
            ),
            patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread,
            patch(
                "galaxy_db_sync.application.kline.command.sync_kline_data_async"
            ) as mock_sync,
        ):
            # Setup mock to_thread to return appropriate values
            mock_to_thread.side_effect = [
                {},  # _get_listing_dates returns empty dict
                CompletenessResult(
                    is_complete=True,
                    missing_count=0,
                    total_count=10,
                    coverage_ratio=1.0,
                    missing_ranges=[],
                    check_method="short_period_trading_day",
                ),  # completeness checker result
            ]

            result = asyncio.run(handle_kline_command_async(args))

        self.assertEqual(result, 0)
        # Verify to_thread was called for _get_listing_dates
        self.assertTrue(mock_to_thread.call_count >= 1)
        mock_sync.assert_not_called()

    def test_handle_kline_command_async_triggers_sync_when_incomplete(self):
        """Test async handler triggers async sync when data incomplete."""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval="day",
            start="20230101",
            end="20231231",
        )

        mock_sync_result = MagicMock()
        mock_sync_result.success_count = 1
        mock_sync_result.synced_records = 100
        mock_sync_result.failed_codes = []

        with (
            patch(
                "galaxy_db_sync.application.kline.command.async_db_manager.initialize"
            ),
            patch(
                "galaxy_db_sync.application.kline.command.parse_symbols",
                return_value=[("symbol", "600000.SH")],
            ),
            patch(
                "galaxy_db_sync.application.kline.command.get_valid_symbols_from_input",
                return_value=["600000.SH"],
            ),
            patch(
                "galaxy_db_sync.application.kline.command.resolve_default_start_date_for_interval",
                return_value="20230101",
            ),
            patch(
                "galaxy_db_sync.application.kline.command.resolve_default_end_date_for_interval",
                return_value="20231231",
            ),
            patch(
                "galaxy_db_sync.application.kline.command.validate_date_range",
                return_value=[],
            ),
            patch(
                "galaxy_db_sync.application.kline.command.get_sdk_interval_value",
                return_value=10008,
            ),
            patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread,
            patch(
                "galaxy_db_sync.application.kline.command.sync_kline_data_async",
                new_callable=AsyncMock,
                return_value=mock_sync_result,
            ) as mock_sync,
        ):
            # Setup mock to_thread to return appropriate values
            mock_to_thread.side_effect = [
                {},  # _get_listing_dates
                CompletenessResult(
                    is_complete=False,
                    missing_count=5,
                    total_count=10,
                    coverage_ratio=0.5,
                    missing_ranges=[],
                    check_method="short_period_trading_day",
                ),  # completeness checker result - incomplete
            ]

            result = asyncio.run(handle_kline_command_async(args))

        self.assertEqual(result, 0)
        mock_sync.assert_called_once()

    def test_main_wraps_async_main_with_asyncio_run(self):
        """Test main() correctly wraps async_main with asyncio.run."""
        with (
            patch("asyncio.run", return_value=0) as mock_run,
            patch(
                "galaxy_db_sync.application.cli.commands.async_main",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            result = main()

        mock_run.assert_called_once()
        self.assertEqual(result, 0)

    def test_async_main_returns_1_when_no_command(self):
        """Test async_main returns 1 when no command provided."""
        with patch("sys.argv", ["galaxy-data-ingest"]):
            result = asyncio.run(async_main())

        self.assertEqual(result, 1)

    def test_async_main_dispatches_kline_to_async_handler(self):
        """Test async_main dispatches kline command to async handler."""
        args = argparse.Namespace(
            command="kline",
            symbols="600000.SH",
            interval="day",
            start="20230101",
            end="20231231",
        )

        with (
            patch("argparse.ArgumentParser.parse_args", return_value=args),
            patch(
                "galaxy_db_sync.application.cli.commands.handle_kline_command_async",
                new_callable=AsyncMock,
                return_value=0,
            ) as mock_handle_async,
        ):
            result = asyncio.run(async_main())

        self.assertEqual(result, 0)
        mock_handle_async.assert_called_once_with(args)

    def test_async_main_wraps_calendar_with_to_thread(self):
        """Test async_main wraps calendar command with asyncio.to_thread."""
        args = argparse.Namespace(
            command="calendar",
            year=2024,
        )

        with (
            patch("argparse.ArgumentParser.parse_args", return_value=args),
            patch("asyncio.to_thread", new_callable=AsyncMock, return_value=0) as mock_to_thread,
        ):
            result = asyncio.run(async_main())

        self.assertEqual(result, 0)
        mock_to_thread.assert_called_once()

    def test_handle_kline_command_async_exception_handling(self):
        """Test async handler returns 1 on exception."""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval="day",
            start="20230101",
            end="20231231",
        )

        with (
            patch(
                "galaxy_db_sync.application.kline.command.parse_symbols",
                side_effect=Exception("Test exception"),
            ),
            patch("logging.Logger.error") as mock_logger_error,
        ):
            result = asyncio.run(handle_kline_command_async(args))

        self.assertEqual(result, 1)
        mock_logger_error.assert_called()


class TestSyncKlineDataAsync(unittest.TestCase):
    """测试 sync_kline_data_async 包装函数."""

    def test_sync_kline_data_async_wraps_sync_function(self):
        """Test sync_kline_data_async wraps sync_kline_data with asyncio.to_thread."""
        from galaxy_db_sync.application.kline.command import sync_kline_data_async
        from galaxy_db_sync.application.kline.result import KlineSyncResult

        mock_result = KlineSyncResult(
            success_count=10,
            synced_records=100,
            failed_codes=[],
            message="Success",
        )

        with (
            patch(
                "galaxy_db_sync.application.kline.command.sync_kline_data",
                return_value=mock_result,
            ),
            patch(
                "asyncio.to_thread",
                new_callable=AsyncMock,
                return_value=mock_result,
            ) as mock_to_thread,
        ):
            result = asyncio.run(
                sync_kline_data_async(
                    completeness_results={},
                    interval="day",
                    interval_value="10008",
                    full_start="20230101",
                    full_end="20231231",
                )
            )

        self.assertEqual(result.success_count, 10)
        mock_to_thread.assert_called_once()


if __name__ == "__main__":
    unittest.main()
