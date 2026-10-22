"""SYNC-05 CLI E2E 回归测试 -- handle_kline_command_async 调用链路验证.

使用 unittest.mock 的 AsyncMock/MagicMock + patch 测试 CLI 入口的完整行为：
- 日常 CLI 调用
- SecurityType 展开
- 空结果处理
- 无效 interval 返回错误码
"""

import argparse
import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock AmazingData SDK before any galaxy_core imports
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

# Mock config_loader — 返回默认值而非空 dict，避免污染集成测试
config_loader_mock = types.ModuleType("galaxy_core.shared_kernel.utils.config_loader")

def _mock_get_config(*args, **kwargs):
    if len(args) >= 3:
        return args[2]
    return kwargs.get("default")

config_loader_mock.get_config = _mock_get_config
config_loader_mock.get_section = lambda *args, **kwargs: {}
config_loader_mock.load_config_dict = lambda *args, **kwargs: {}
sys.modules["galaxy_core.shared_kernel.utils.config_loader"] = config_loader_mock

from galaxy_core.application.kline.command import handle_kline_command_async
from galaxy_core.domain.value_objects import Interval
from galaxy_core.services.kline_data_service import SyncResult


def _make_mock_trading_calendar_service():
    """创建 mock TradingCalendarService."""
    mock_tcs = MagicMock()
    return mock_tcs


class TestCLIRegression:
    """SYNC-05 CLI E2E 回归测试."""

    def test_cli_kline_day_sync(self):
        """日常 CLI 调用：验证返回 0，sync 被调用一次且 interval 为 DAY."""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval=["day"],
            start="20240101",
            end="20240131",
        )

        mock_kline_service = MagicMock()
        mock_kline_service.sync = AsyncMock(
            return_value=SyncResult(
                success_count=1,
                synced_records=10,
                failed_codes=[],
                total_symbols=1,
            )
        )

        mock_reference = MagicMock()
        mock_reference.get_hist_code_list = AsyncMock(return_value=[])

        mock_db_manager = MagicMock()
        mock_tcs = _make_mock_trading_calendar_service()

        with (
            patch(
                "galaxy_core.application.kline.command.parse_symbols",
                return_value=[("symbol", "600000.SH")],
            ),
            patch(
                "galaxy_core.application.kline.command.resolve_symbols",
                return_value=["600000.SH"],
            ),
            patch(
                "galaxy_core.application.kline.command.validate_date_range",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = asyncio.run(
                handle_kline_command_async(
                    args,
                    kline_service=mock_kline_service,
                    async_db_manager=mock_db_manager,
                    reference_provider=mock_reference,
                    trading_calendar_service=mock_tcs,
                )
            )

        assert result == 0
        mock_kline_service.sync.assert_called_once()
        call_kwargs = mock_kline_service.sync.call_args.kwargs
        assert call_kwargs["interval"] == Interval.DAY
        assert call_kwargs["symbols"] == ["600000.SH"]

    def test_cli_kline_with_security_type_expansion(self):
        """SecurityType 展开：SH_A 展开为具体 symbols，验证返回 0."""
        args = argparse.Namespace(
            symbols="SH_A",
            interval=["day"],
            start=None,
            end=None,
        )

        mock_kline_service = MagicMock()
        mock_kline_service.sync = AsyncMock(
            return_value=SyncResult(
                success_count=2,
                synced_records=20,
                failed_codes=[],
                total_symbols=2,
            )
        )

        mock_reference = MagicMock()
        mock_reference.get_hist_code_list = AsyncMock(
            return_value=["600000.SH", "601398.SH"]
        )

        mock_db_manager = MagicMock()
        mock_tcs = _make_mock_trading_calendar_service()

        with (
            patch(
                "galaxy_core.application.kline.command.parse_symbols",
                return_value=[("symbol", "SH_A")],
            ),
            patch(
                "galaxy_core.application.kline.command.resolve_symbols",
                return_value=["600000.SH", "601398.SH"],
            ),
            patch(
                "galaxy_core.application.kline.command.resolve_default_start_date_for_interval",
                return_value="20240101",
            ),
            patch(
                "galaxy_core.application.kline.command.resolve_default_end_date_for_interval",
                new_callable=AsyncMock,
                return_value="20240131",
            ),
            patch(
                "galaxy_core.application.kline.command.validate_date_range",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = asyncio.run(
                handle_kline_command_async(
                    args,
                    kline_service=mock_kline_service,
                    async_db_manager=mock_db_manager,
                    reference_provider=mock_reference,
                    trading_calendar_service=mock_tcs,
                )
            )

        assert result == 0
        mock_kline_service.sync.assert_called_once()
        call_kwargs = mock_kline_service.sync.call_args.kwargs
        assert "600000.SH" in call_kwargs["symbols"]
        assert "601398.SH" in call_kwargs["symbols"]

    def test_cli_kline_empty_result(self):
        """空结果处理：sync 返回 success_count=0，验证返回 0（空结果不是错误）."""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval=["day"],
            start="20240101",
            end="20240131",
        )

        mock_kline_service = MagicMock()
        mock_kline_service.sync = AsyncMock(
            return_value=SyncResult(
                success_count=0,
                synced_records=0,
                failed_codes=[],
                total_symbols=1,
            )
        )

        mock_reference = MagicMock()
        mock_db_manager = MagicMock()
        mock_tcs = _make_mock_trading_calendar_service()

        with (
            patch(
                "galaxy_core.application.kline.command.parse_symbols",
                return_value=[("symbol", "600000.SH")],
            ),
            patch(
                "galaxy_core.application.kline.command.resolve_symbols",
                return_value=["600000.SH"],
            ),
            patch(
                "galaxy_core.application.kline.command.validate_date_range",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = asyncio.run(
                handle_kline_command_async(
                    args,
                    kline_service=mock_kline_service,
                    async_db_manager=mock_db_manager,
                    reference_provider=mock_reference,
                    trading_calendar_service=mock_tcs,
                )
            )

        assert result == 0
        mock_kline_service.sync.assert_called_once()

    def test_cli_kline_invalid_interval(self):
        """无效 interval 返回错误码 1."""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval="invalid",
            start="20240101",
            end="20240131",
        )

        mock_kline_service = MagicMock()
        mock_reference = MagicMock()
        mock_db_manager = MagicMock()
        mock_tcs = _make_mock_trading_calendar_service()

        result = asyncio.run(
            handle_kline_command_async(
                args,
                kline_service=mock_kline_service,
                async_db_manager=mock_db_manager,
                reference_provider=mock_reference,
                trading_calendar_service=mock_tcs,
            )
        )

        assert result == 1
        mock_kline_service.sync.assert_not_called()

    def test_cli_kline_no_service_returns_1(self):
        """kline_service 未注入时返回 1."""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval=["day"],
            start="20240101",
            end="20240131",
        )

        mock_reference = MagicMock()
        mock_db_manager = MagicMock()
        mock_tcs = _make_mock_trading_calendar_service()

        with (
            patch(
                "galaxy_core.application.kline.command.parse_symbols",
                return_value=[("symbol", "600000.SH")],
            ),
            patch(
                "galaxy_core.application.kline.command.resolve_symbols",
                return_value=["600000.SH"],
            ),
            patch(
                "galaxy_core.application.kline.command.validate_date_range",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = asyncio.run(
                handle_kline_command_async(
                    args,
                    kline_service=None,
                    async_db_manager=mock_db_manager,
                    reference_provider=mock_reference,
                    trading_calendar_service=mock_tcs,
                )
            )

        assert result == 1

    def test_cli_kline_exception_handling(self):
        """异常处理：sync 抛异常时返回 1."""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval=["day"],
            start="20240101",
            end="20240131",
        )

        mock_kline_service = MagicMock()
        mock_kline_service.sync = AsyncMock(side_effect=Exception("sync error"))

        mock_reference = MagicMock()
        mock_db_manager = MagicMock()
        mock_tcs = _make_mock_trading_calendar_service()

        with (
            patch(
                "galaxy_core.application.kline.command.parse_symbols",
                return_value=[("symbol", "600000.SH")],
            ),
            patch(
                "galaxy_core.application.kline.command.resolve_symbols",
                return_value=["600000.SH"],
            ),
            patch(
                "galaxy_core.application.kline.command.validate_date_range",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = asyncio.run(
                handle_kline_command_async(
                    args,
                    kline_service=mock_kline_service,
                    async_db_manager=mock_db_manager,
                    reference_provider=mock_reference,
                    trading_calendar_service=mock_tcs,
                )
            )

        assert result == 1
