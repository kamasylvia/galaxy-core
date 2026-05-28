"""K 线命令测试模块.

测试 application/kline/command 模块的命令层功能，包括：
- CLI 解析器
- 命令处理流程
- 参数验证
- 周期值解析
"""

import argparse
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd

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

from galaxy_db_sync.application.kline.command import (
    KLineCommandService,
    handle_kline_command,
)
from galaxy_db_sync.application.kline.parser import (
    IntervalOption,
    create_kline_parser,
    get_sdk_interval_value,
)
from galaxy_db_sync.database.services.kline_completeness_checker import (
    CompletenessResult,
)
from galaxy_db_sync.shared_kernel.enums.interval import Interval


class TestKlineCommand(unittest.TestCase):
    """K 线命令测试类."""

    def setUp(self):
        """测试前置设置."""
        root_parser = argparse.ArgumentParser(prog="test")
        subparsers = root_parser.add_subparsers(dest="command")
        self.parser = create_kline_parser(subparsers)

    def test_create_kline_parser(self):
        """测试 kline 命令解析器创建."""
        self.assertEqual(self.parser.prog, "test kline")
        self.assertIn("--interval", self.parser._option_string_actions)
        self.assertIn("--start", self.parser._option_string_actions)
        self.assertIn("--end", self.parser._option_string_actions)

        positionals = [
            action for action in self.parser._actions
            if not action.option_strings and action.dest != "help"
        ]
        self.assertEqual([action.dest for action in positionals], ["symbols"])
        self.assertEqual(
            self.parser._option_string_actions["--interval"].default,
            "day",
        )
        self.assertEqual(
            self.parser._option_string_actions["--interval"].choices,
            [p.name.lower() for p in IntervalOption],
        )

    def test_handle_kline_command_invalid_interval(self):
        """测试处理 kline 命令时传入无效 interval 参数."""
        args = argparse.Namespace()
        args.symbols = "600000.SH"
        args.interval = "invalid_interval"
        args.start = None
        args.end = None

        result = handle_kline_command(args)

        self.assertEqual(result, 1)

    @patch("galaxy_db_sync.database.core.connection.db_manager.initialize")
    def test_handle_kline_command_invalid_interval_does_not_initialize_database(
        self, mock_initialize
    ):
        """测试无效 interval 参数时不会先初始化数据库."""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval="invalid_interval",
            start=None,
            end=None,
        )

        result = handle_kline_command(args)

        self.assertEqual(result, 1)
        mock_initialize.assert_not_called()

    def test_handle_kline_command_uses_last_complete_year_end_when_end_omitted(self):
        """测试长周期未传 end 时使用最后一个已完成周期的结束日期。"""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval="year",
            start=None,
            end=None,
        )

        with (
            patch(
                "galaxy_db_sync.application.kline.command.db_manager.initialize"
            ) as mock_initialize,
            patch(
                "galaxy_db_sync.application.kline.command.parse_symbols",
                return_value=[("symbol", "600000.SH")],
            ),
            patch(
                "galaxy_db_sync.application.kline.command.get_valid_symbols_from_input",
                return_value=["600000.SH"],
            ) as mock_get_valid_symbols,
            patch(
                "galaxy_db_sync.application.kline.command.resolve_default_start_date_for_interval",
                side_effect=["2013", "2013"],
            ) as mock_resolve_start,
            patch(
                "galaxy_db_sync.application.kline.command.resolve_default_end_date_for_interval",
                return_value="2024",
            ) as mock_resolve_end,
            patch(
                "galaxy_db_sync.application.kline.command.validate_date_range",
                return_value=[],
            ),
            patch(
                "galaxy_db_sync.application.kline.command.get_sdk_interval_value",
                return_value=10012,
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
                    total_count=1,
                    coverage_ratio=1.0,
                    missing_ranges=[],
                    check_method="long_period",
                ),
            ),
            patch(
                "galaxy_db_sync.application.kline.command.sync_kline_data"
            ) as mock_sync_data,
        ):
            result = handle_kline_command(args)

        self.assertEqual(result, 0)
        mock_initialize.assert_called_once()
        mock_get_valid_symbols.assert_called_once_with(["600000.SH"], "20130101", "20241231")
        self.assertEqual(mock_resolve_start.call_count, 2)
        mock_resolve_start.assert_any_call(["600000.SH"], "year", None)
        mock_resolve_end.assert_called_once_with("year", None)
        mock_sync_data.assert_not_called()

    def test_handle_kline_command_derives_default_start_for_omitted_start(self):
        """测试 start 省略时会按证券类型推导默认起始日期."""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval="day",
            start=None,
            end="20231231",
        )

        with (
            patch(
                "galaxy_db_sync.application.kline.command.parse_symbols",
                return_value=[("symbol", "600000.SH")],
            ),
            patch(
                "galaxy_db_sync.application.kline.command.get_valid_symbols_from_input",
                return_value=["600000.SH"],
            ) as mock_get_valid_symbols,
            patch(
                "galaxy_db_sync.application.kline.command.resolve_default_start_date_for_interval",
                side_effect=["20130101", "20130101"],
            ) as mock_resolve_start,
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
                "galaxy_db_sync.application.kline.command.sync_kline_data"
            ) as mock_sync_data,
        ):
            result = handle_kline_command(args)

        self.assertEqual(result, 0)
        mock_get_valid_symbols.assert_called_once_with(["600000.SH"], "20130101", "20231231")
        self.assertEqual(mock_resolve_start.call_count, 2)
        mock_resolve_start.assert_any_call(["600000.SH"], "day", None)
        mock_sync_data.assert_not_called()

    def test_handle_kline_command_uses_latest_default_start_for_mixed_symbols(self):
        """测试混合 symbol 时使用较晚的默认起始日期."""
        args = argparse.Namespace(
            symbols="[600000.SH, 10003737.OPTION]",
            interval="day",
            start=None,
            end="20231231",
        )

        with (
            patch(
                "galaxy_db_sync.application.kline.command.parse_symbols",
                return_value=[("symbol", "600000.SH"), ("symbol", "10003737.OPTION")],
            ),
            patch(
                "galaxy_db_sync.application.kline.command.get_valid_symbols_from_input",
                return_value=["600000.SH", "10003737.OPTION"],
            ) as mock_get_valid_symbols,
            patch(
                "galaxy_db_sync.application.kline.command.resolve_default_start_date_for_interval",
                side_effect=["20150101", "20150101"],
            ) as mock_resolve_start,
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
                "galaxy_db_sync.application.kline.command.sync_kline_data"
            ) as mock_sync_data,
        ):
            result = handle_kline_command(args)

        self.assertEqual(result, 0)
        mock_get_valid_symbols.assert_called_once_with(
            ["600000.SH", "10003737.OPTION"], "20150101", "20231231"
        )
        self.assertEqual(mock_resolve_start.call_count, 2)
        mock_resolve_start.assert_any_call(["600000.SH", "10003737.OPTION"], "day", None)
        mock_sync_data.assert_not_called()

    def test_handle_kline_command_returns_failure_when_default_start_cannot_be_inferred(self):
        """测试 start 省略且默认开始日期推导失败时命令失败."""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval="day",
            start=None,
            end="20231231",
        )

        with (
            patch(
                "galaxy_db_sync.application.kline.command.parse_symbols",
                return_value=[("symbol", "600000.SH")],
            ),
            patch(
                "galaxy_db_sync.application.kline.command.resolve_default_start_date_for_interval",
                side_effect=ValueError("无法推断证券类型"),
            ),
        ):
            result = handle_kline_command(args)

        self.assertEqual(result, 1)

    def test_handle_kline_command_skips_sync_when_complete(self):
        """测试数据完整时命令层直接返回，不触发同步."""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval="day",
            start="20230101",
            end="20231231",
        )

        with (
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
                side_effect=["20230101", "20230101"],
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
                "galaxy_db_sync.application.kline.command.sync_kline_data"
            ) as mock_sync_data,
        ):
            result = handle_kline_command(args)

        self.assertEqual(result, 0)
        mock_sync_data.assert_not_called()

    def test_get_kline_derives_default_start_when_omitted(self):
        """测试兼容入口在 start_date 缺失时也会推导默认起点."""
        with (
            patch(
                "galaxy_db_sync.database.core.connection.db_manager.initialize"
            ),
            patch(
                "galaxy_db_sync.application.kline.command.get_sdk_interval_value",
                return_value=10008,
            ),
            patch(
                "galaxy_db_sync.application.kline.command.resolve_default_start_date_for_interval",
                return_value="20130101",
            ) as mock_resolve_default_start,
            patch(
                "galaxy_db_sync.application.kline.command.execute_kline_query",
                return_value={"600000.SH": pd.DataFrame()},
            ) as mock_execute,
        ):
            service = KLineCommandService()
            result = service.get_kline(
                symbol="600000.SH",
                interval=Interval.DAY,
                start_date=None,
                end_date="20231231",
            )

        mock_resolve_default_start.assert_called_once_with(["600000.SH"], "day", None)
        mock_execute.assert_called_once_with(
            symbol_list=["600000.SH"],
            interval="day",
            start_date="20130101",
            end_date="20231231",
            interval_value=10008,
        )
        self.assertEqual(result["start_date"], "20130101")
        self.assertEqual(result["end_date"], "20231231")

    def test_get_kline_preserves_explicit_start(self):
        """测试兼容入口显式 start_date 时保持原值."""
        with (
            patch(
                "galaxy_db_sync.database.core.connection.db_manager.initialize"
            ),
            patch(
                "galaxy_db_sync.application.kline.command.get_sdk_interval_value",
                return_value=10008,
            ),
            patch(
                "galaxy_db_sync.application.kline.command.resolve_default_start_date_for_interval",
                return_value="20200101",
            ) as mock_resolve_default_start,
            patch(
                "galaxy_db_sync.application.kline.command.execute_kline_query",
                return_value={"600000.SH": pd.DataFrame()},
            ) as mock_execute,
        ):
            service = KLineCommandService()
            result = service.get_kline(
                symbol="600000.SH",
                interval=Interval.DAY,
                start_date="20200101",
                end_date="20231231",
            )

        mock_resolve_default_start.assert_called_once_with(["600000.SH"], "day", "20200101")
        mock_execute.assert_called_once_with(
            symbol_list=["600000.SH"],
            interval="day",
            start_date="20200101",
            end_date="20231231",
            interval_value=10008,
        )
        self.assertEqual(result["start_date"], "20200101")
        self.assertEqual(result["end_date"], "20231231")

    def test_get_sdk_interval_value_uses_sdk_constant(self):
        """测试周期值来自 AmazingData SDK 常量，而不是本地兜底."""
        fake_period = SimpleNamespace(
            min1=SimpleNamespace(value=10100),
            min3=SimpleNamespace(value=10101),
            min5=SimpleNamespace(value=10102),
            min10=SimpleNamespace(value=10103),
            min15=SimpleNamespace(value=10104),
            min30=SimpleNamespace(value=10105),
            min60=SimpleNamespace(value=10106),
            min120=SimpleNamespace(value=10107),
            day=SimpleNamespace(value=10108),
            week=SimpleNamespace(value=10109),
            month=SimpleNamespace(value=10110),
            season=SimpleNamespace(value=10111),
            year=SimpleNamespace(value=10112),
        )
        fake_ad = SimpleNamespace(constant=SimpleNamespace(Period=fake_period))

        with patch("galaxy_db_sync.application.kline.parser.ad", fake_ad):
            self.assertEqual(get_sdk_interval_value(IntervalOption.DAY), 10108)

    def test_get_sdk_interval_value_raises_when_sdk_constant_namespace_missing(self):
        """测试缺失 ad.constant 时直接报错，不再兜底到 DAY."""
        fake_ad = SimpleNamespace()

        with (
            patch("galaxy_db_sync.application.kline.parser.ad", fake_ad),
            self.assertRaisesRegex(RuntimeError, "missing ad.constant"),
        ):
            get_sdk_interval_value(IntervalOption.DAY)

    def test_get_sdk_interval_value_raises_when_sdk_period_enum_missing(self):
        """测试缺失 ad.constant.Period 时直接报错，不再兜底到 DAY."""
        fake_ad = SimpleNamespace(constant=SimpleNamespace())

        with (
            patch("galaxy_db_sync.application.kline.parser.ad", fake_ad),
            self.assertRaisesRegex(RuntimeError, "missing ad.constant.Period"),
        ):
            get_sdk_interval_value(IntervalOption.DAY)

    def test_get_sdk_interval_value_raises_when_specific_sdk_period_missing(self):
        """测试缺失具体周期成员时直接报错."""
        fake_period = SimpleNamespace(
            min1=SimpleNamespace(value=10100),
            min3=SimpleNamespace(value=10101),
            min5=SimpleNamespace(value=10102),
            min10=SimpleNamespace(value=10103),
            min15=SimpleNamespace(value=10104),
            min30=SimpleNamespace(value=10105),
            min60=SimpleNamespace(value=10106),
            min120=SimpleNamespace(value=10107),
            week=SimpleNamespace(value=10109),
            month=SimpleNamespace(value=10110),
            season=SimpleNamespace(value=10111),
            year=SimpleNamespace(value=10112),
        )
        fake_ad = SimpleNamespace(constant=SimpleNamespace(Period=fake_period))

        with (
            patch("galaxy_db_sync.application.kline.parser.ad", fake_ad),
            self.assertRaisesRegex(RuntimeError, "ad.constant.Period.day"),
        ):
            get_sdk_interval_value(IntervalOption.DAY)

    def test_handle_kline_command_returns_failure_when_sdk_interval_resolution_fails(self):
        """测试周期解析阶段失败时命令直接返回失败码."""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval="day",
            start="20230101",
            end="20231231",
        )

        with (
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
                "galaxy_db_sync.application.kline.command.validate_date_range",
                return_value=[],
            ),
            patch(
                "galaxy_db_sync.application.kline.command.get_sdk_interval_value",
                side_effect=RuntimeError("AmazingData SDK constants are unavailable"),
            ),
            patch(
                "galaxy_db_sync.application.kline.command.sync_kline_data"
            ) as mock_sync_data,
        ):
            result = handle_kline_command(args)

        self.assertEqual(result, 1)
        mock_sync_data.assert_not_called()

    def test_handle_kline_command_triggers_sync_when_incomplete(self):
        """测试缺失交易日数据时会触发同步."""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval="day",
            start="20230101",
            end="20231231",
        )

        with (
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
                    is_complete=False,
                    missing_count=2,
                    total_count=10,
                    coverage_ratio=0.8,
                    missing_ranges=[],
                    check_method="short_period_trading_day",
                ),
            ) as mock_check,
            patch(
                "galaxy_db_sync.application.kline.command.sync_kline_data"
            ) as mock_sync_data,
        ):
            mock_sync_result = MagicMock()
            mock_sync_result.success_count = 1
            mock_sync_result.synced_records = 2
            mock_sync_result.failed_codes = []
            mock_sync_data.return_value = mock_sync_result

            result = handle_kline_command(args)

        self.assertEqual(result, 0)
        mock_sync_data.assert_called_once_with(
            completeness_results={
                "600000.SH": mock_check.return_value,
            },
            interval="day",
            interval_value="10008",
            full_start="20230101",
            full_end="20231231",
        )

    def test_handle_kline_command_non_trading_range_skips_sync(self):
        """测试非交易日范围不会触发同步."""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval="day",
            start="20240106",
            end="20240107",
        )

        with (
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
                return_value="20240106",
            ),
            patch(
                "galaxy_db_sync.application.kline.command.resolve_default_end_date_for_interval",
                return_value="20240107",
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
                    total_count=0,
                    coverage_ratio=1.0,
                    missing_ranges=[],
                    check_method="short_period_trading_day",
                ),
            ),
            patch(
                "galaxy_db_sync.application.kline.command.sync_kline_data"
            ) as mock_sync_data,
        ):
            result = handle_kline_command(args)

        self.assertEqual(result, 0)
        mock_sync_data.assert_not_called()

    def test_handle_kline_command_invalid_symbols(self):
        """测试处理 kline 命令时传入无效证券代码."""
        args = argparse.Namespace()
        args.symbols = "INVALID_SYMBOL"
        args.interval = "day"
        args.start = "20230101"
        args.end = "20231231"

        with (
            patch(
                "galaxy_db_sync.application.kline.command.parse_symbols"
            ) as mock_parse_symbols,
            patch(
                "galaxy_db_sync.application.kline.command.get_valid_symbols_from_input"
            ) as mock_get_valid_symbols,
            patch(
                "galaxy_db_sync.application.kline.command.resolve_default_start_date_for_interval"
            ) as mock_validate_period,
            patch(
                "galaxy_db_sync.application.kline.command.validate_date_range"
            ) as mock_validate_range,
        ):
            mock_parse_symbols.return_value = [("symbol", "INVALID_SYMBOL")]
            mock_get_valid_symbols.return_value = []
            mock_validate_period.return_value = "20230101"
            mock_validate_range.return_value = []

            result = handle_kline_command(args)

            self.assertEqual(result, 1)

    def test_handle_kline_command_invalid_date_range(self):
        """测试处理 kline 命令时传入无效日期范围."""
        args = argparse.Namespace()
        args.symbols = "600000.SH"
        args.interval = "day"
        args.start = "20230101"
        args.end = "20221231"

        with (
            patch(
                "galaxy_db_sync.application.kline.command.parse_symbols"
            ) as mock_parse_symbols,
            patch(
                "galaxy_db_sync.application.kline.command.get_valid_symbols_from_input"
            ) as mock_get_valid_symbols,
            patch(
                "galaxy_db_sync.application.kline.command.resolve_default_start_date_for_interval"
            ) as mock_validate_period,
            patch(
                "galaxy_db_sync.application.kline.command.validate_date_range"
            ) as mock_validate_range,
        ):
            mock_parse_symbols.return_value = [("symbol", "600000.SH")]
            mock_get_valid_symbols.return_value = ["600000.SH"]
            mock_validate_period.return_value = "20230101"
            mock_validate_range.return_value = [
                "开始日期 (20230101) 晚于结束日期 (20221231)"
            ]

            result = handle_kline_command(args)

            self.assertEqual(result, 1)

    @patch("logging.Logger.error")
    def test_handle_kline_command_exception_handling(self, mock_logger_error):
        """测试处理 kline 命令时异常处理."""
        args = argparse.Namespace()
        args.symbols = "600000.SH"
        args.interval = "day"
        args.start = "20230101"
        args.end = "20231231"

        with patch(
            "galaxy_db_sync.application.kline.command.parse_symbols"
        ) as mock_parse_symbols:
            mock_parse_symbols.side_effect = Exception("Test exception")

            result = handle_kline_command(args)

            self.assertEqual(result, 1)
            mock_logger_error.assert_called()


if __name__ == "__main__":
    unittest.main()
