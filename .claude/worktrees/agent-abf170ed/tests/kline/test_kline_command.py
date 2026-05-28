"""K 线命令测试模块."""

import unittest
import argparse
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pandas as pd

from galaxy_db_bridge.application.kline.command import (
    IntervalOption,
    KLineCommandService,
    create_kline_parser,
    execute_kline_query,
    get_sdk_interval_value,
    handle_kline_command,
)
from galaxy_db_bridge.database.services.kline_completeness_checker import (
    CompletenessResult,
)
from galaxy_db_bridge.shared_kernel.enums.interval import Interval


class TestKlineCommand(unittest.TestCase):
    """K 线命令测试类."""

    def setUp(self):
        """测试前置设置."""
        self.parser = create_kline_parser(MagicMock())

    def test_create_kline_parser(self):
        """测试 kline 命令解析器创建."""
        self.assertIsNotNone(self.parser)
        # 验证必选参数
        self.assertTrue(hasattr(self.parser._actions[-1], "dest"))

    def test_handle_kline_command_invalid_interval(self):
        """测试处理 kline 命令时传入无效 interval 参数."""
        # 创建一个具有无效 interval 参数的 mock args 对象
        args = argparse.Namespace()
        args.symbols = "600000.SH"
        args.interval = "invalid_interval"  # 无效的 interval
        args.start = None
        args.end = None

        # 调用 handle_kline_command 函数
        result = handle_kline_command(args)

        # 验证返回值为 1（表示错误）
        self.assertEqual(result, 1)

    @patch("galaxy_db_bridge.database.core.connection.db_manager.initialize")
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

        """测试处理 kline 命令时传入有效参数."""
        args = argparse.Namespace()
        args.symbols = "600000.SH"
        args.interval = "day"
        args.start = "20230101"
        args.end = "20231231"

        with (
            patch(
                "galaxy_db_bridge.application.kline.command.parse_symbols"
            ) as mock_parse_symbols,
            patch(
                "galaxy_db_bridge.application.kline.command.get_valid_symbols_from_input"
            ) as mock_get_valid_symbols,
            patch(
                "galaxy_db_bridge.application.kline.command.validate_start_end_by_period"
            ) as mock_validate_period,
            patch(
                "galaxy_db_bridge.application.kline.command.validate_date_range"
            ) as mock_validate_range,
            patch(
                "galaxy_db_bridge.application.kline.command.kline_completeness_checker.check"
            ) as mock_check,
            patch(
                "galaxy_db_bridge.application.kline.command._sync_kline_data"
            ) as mock_sync_data,
        ):
            mock_parse_symbols.return_value = [("symbol", "600000.SH")]
            mock_get_valid_symbols.return_value = ["600000.SH"]
            mock_validate_period.return_value = ("20230101", "20231231")
            mock_validate_range.return_value = []
            mock_check.return_value = CompletenessResult(
                is_complete=False,
                missing_count=1,
                total_count=10,
                coverage_ratio=0.9,
                missing_ranges=[],
                check_method="short_period_trading_day",
            )

            mock_sync_result = MagicMock()
            mock_sync_result.success_count = 1
            mock_sync_result.synced_records = 100
            mock_sync_result.failed_codes = []
            mock_sync_data.return_value = mock_sync_result

            result = handle_kline_command(args)

            self.assertEqual(result, 0)
            mock_parse_symbols.assert_called_once_with("600000.SH")
            mock_get_valid_symbols.assert_called_once_with(
                ["600000.SH"], "20230101", "20231231"
            )
            mock_validate_period.assert_called_once_with("day", "20230101", "20231231")
            mock_validate_range.assert_called_once_with("20230101", "20231231", "day")
            mock_sync_data.assert_called_once_with(
                completeness_results={
                    "600000.SH": mock_check.return_value,
                },
                interval="day",
                interval_value=10008,
            )

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
                "galaxy_db_bridge.application.kline.command.parse_symbols",
                return_value=[("symbol", "600000.SH")],
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.get_valid_symbols_from_input",
                return_value=["600000.SH"],
            ) as mock_get_valid_symbols,
            patch(
                "galaxy_db_bridge.application.kline.command.validate_start_end_by_period",
                side_effect=[("20130101", "20231231"), ("20130101", "20231231")],
            ) as mock_validate_period,
            patch(
                "galaxy_db_bridge.application.kline.command.validate_date_range",
                return_value=[],
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.kline_completeness_checker.check",
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
                "galaxy_db_bridge.application.kline.command._sync_kline_data"
            ) as mock_sync_data,
        ):
            result = handle_kline_command(args)

        self.assertEqual(result, 0)
        mock_get_valid_symbols.assert_called_once_with(["600000.SH"], "20130101", "20231231")
        self.assertEqual(mock_validate_period.call_count, 2)
        mock_validate_period.assert_any_call("day", "20130101", "20231231")
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
                "galaxy_db_bridge.application.kline.command.parse_symbols",
                return_value=[("symbol", "600000.SH"), ("symbol", "10003737.OPTION")],
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.get_valid_symbols_from_input",
                return_value=["600000.SH", "10003737.OPTION"],
            ) as mock_get_valid_symbols,
            patch(
                "galaxy_db_bridge.application.kline.command.validate_start_end_by_period",
                side_effect=[("20150101", "20231231"), ("20150101", "20231231")],
            ) as mock_validate_period,
            patch(
                "galaxy_db_bridge.application.kline.command.validate_date_range",
                return_value=[],
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.kline_completeness_checker.check",
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
                "galaxy_db_bridge.application.kline.command._sync_kline_data"
            ) as mock_sync_data,
        ):
            result = handle_kline_command(args)

        self.assertEqual(result, 0)
        mock_get_valid_symbols.assert_called_once_with(
            ["600000.SH", "10003737.OPTION"], "20150101", "20231231"
        )
        self.assertEqual(mock_validate_period.call_count, 2)
        mock_validate_period.assert_any_call("day", "20150101", "20231231")
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
                "galaxy_db_bridge.application.kline.command.parse_symbols",
                return_value=[("symbol", "600000.SH")],
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.resolve_default_start_date",
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
                "galaxy_db_bridge.application.kline.command.parse_symbols",
                return_value=[("symbol", "600000.SH")],
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.get_valid_symbols_from_input",
                return_value=["600000.SH"],
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.validate_start_end_by_period",
                return_value=("20230101", "20231231"),
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.validate_date_range",
                return_value=[],
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.kline_completeness_checker.check",
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
                "galaxy_db_bridge.application.kline.command._sync_kline_data"
            ) as mock_sync_data,
        ):
            result = handle_kline_command(args)

        self.assertEqual(result, 0)
        mock_sync_data.assert_not_called()

    def test_get_kline_derives_default_start_when_omitted(self):
        """测试兼容入口在 start_date 缺失时也会推导默认起点."""
        with (
            patch(
                "galaxy_db_bridge.database.core.connection.db_manager.initialize"
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.get_sdk_interval_value",
                return_value=10008,
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.resolve_default_start_date",
                return_value="20130101",
            ) as mock_resolve_default_start,
            patch(
                "galaxy_db_bridge.application.kline.command.validate_start_end_by_period",
                return_value=("20130101", "20231231"),
            ) as mock_validate_period,
            patch(
                "galaxy_db_bridge.application.kline.command.execute_kline_query",
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

        mock_resolve_default_start.assert_called_once_with(["600000.SH"], None)
        mock_validate_period.assert_called_once_with("day", "20130101", "20231231")
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
                "galaxy_db_bridge.database.core.connection.db_manager.initialize"
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.get_sdk_interval_value",
                return_value=10008,
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.resolve_default_start_date",
                return_value="20200101",
            ) as mock_resolve_default_start,
            patch(
                "galaxy_db_bridge.application.kline.command.validate_start_end_by_period",
                return_value=("20200101", "20231231"),
            ) as mock_validate_period,
            patch(
                "galaxy_db_bridge.application.kline.command.execute_kline_query",
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

        mock_resolve_default_start.assert_called_once_with(["600000.SH"], "20200101")
        mock_validate_period.assert_called_once_with("day", "20200101", "20231231")
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

        with patch("galaxy_db_bridge.application.kline.command.ad", fake_ad):
            self.assertEqual(get_sdk_interval_value(IntervalOption.DAY), 10108)

    def test_get_sdk_interval_value_raises_when_sdk_constant_namespace_missing(self):
        """测试缺失 ad.constant 时直接报错，不再兜底到 DAY."""
        fake_ad = SimpleNamespace()

        with patch("galaxy_db_bridge.application.kline.command.ad", fake_ad):
            with self.assertRaisesRegex(RuntimeError, "missing ad.constant"):
                get_sdk_interval_value(IntervalOption.DAY)

    def test_get_sdk_interval_value_raises_when_sdk_period_enum_missing(self):
        """测试缺失 ad.constant.Period 时直接报错，不再兜底到 DAY."""
        fake_ad = SimpleNamespace(constant=SimpleNamespace())

        with patch("galaxy_db_bridge.application.kline.command.ad", fake_ad):
            with self.assertRaisesRegex(RuntimeError, "missing ad.constant.Period"):
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

        with patch("galaxy_db_bridge.application.kline.command.ad", fake_ad):
            with self.assertRaisesRegex(RuntimeError, "ad.constant.Period.day"):
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
                "galaxy_db_bridge.application.kline.command.parse_symbols",
                return_value=[("symbol", "600000.SH")],
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.get_valid_symbols_from_input",
                return_value=["600000.SH"],
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.validate_start_end_by_period",
                return_value=("20230101", "20231231"),
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.validate_date_range",
                return_value=[],
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.get_sdk_interval_value",
                side_effect=RuntimeError("AmazingData SDK constants are unavailable"),
            ),
            patch(
                "galaxy_db_bridge.application.kline.command._sync_kline_data"
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
                "galaxy_db_bridge.application.kline.command.parse_symbols",
                return_value=[("symbol", "600000.SH")],
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.get_valid_symbols_from_input",
                return_value=["600000.SH"],
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.validate_start_end_by_period",
                return_value=("20230101", "20231231"),
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.validate_date_range",
                return_value=[],
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.kline_completeness_checker.check",
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
                "galaxy_db_bridge.application.kline.command._sync_kline_data"
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
            interval_value=10008,
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
                "galaxy_db_bridge.application.kline.command.parse_symbols",
                return_value=[("symbol", "600000.SH")],
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.get_valid_symbols_from_input",
                return_value=["600000.SH"],
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.validate_start_end_by_period",
                return_value=("20240106", "20240107"),
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.validate_date_range",
                return_value=[],
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.kline_completeness_checker.check",
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
                "galaxy_db_bridge.application.kline.command._sync_kline_data"
            ) as mock_sync_data,
        ):
            result = handle_kline_command(args)

        self.assertEqual(result, 0)
        mock_sync_data.assert_not_called()

    def test_handle_kline_command_invalid_symbols(self):
        """测试处理 kline 命令时传入无效证券代码."""
        # 创建一个具有有效参数的 mock args 对象
        args = argparse.Namespace()
        args.symbols = "INVALID_SYMBOL"
        args.interval = "day"
        args.start = "20230101"
        args.end = "20231231"

        # 模拟 symbol_validator 和其他依赖
        with (
            patch(
                "galaxy_db_bridge.application.kline.command.parse_symbols"
            ) as mock_parse_symbols,
            patch(
                "galaxy_db_bridge.application.kline.command.get_valid_symbols_from_input"
            ) as mock_get_valid_symbols,
            patch(
                "galaxy_db_bridge.application.kline.command.validate_start_end_by_period"
            ) as mock_validate_period,
            patch(
                "galaxy_db_bridge.application.kline.command.validate_date_range"
            ) as mock_validate_range,
        ):

            # 设置模拟返回值
            mock_parse_symbols.return_value = [("symbol", "INVALID_SYMBOL")]
            mock_get_valid_symbols.return_value = []  # 返回空列表表示无效符号
            mock_validate_period.return_value = ("20230101", "20231231")
            mock_validate_range.return_value = []

            # 调用 handle_kline_command 函数
            result = handle_kline_command(args)

            # 验证返回值为 1（表示错误）
            self.assertEqual(result, 1)

    def test_handle_kline_command_invalid_date_range(self):
        """测试处理 kline 命令时传入无效日期范围."""
        # 创建一个具有有效参数的 mock args 对象
        args = argparse.Namespace()
        args.symbols = "600000.SH"
        args.interval = "day"
        args.start = "20230101"
        args.end = "20221231"  # 结束日期早于开始日期

        # 模拟 symbol_validator 和其他依赖
        with (
            patch(
                "galaxy_db_bridge.application.kline.command.parse_symbols"
            ) as mock_parse_symbols,
            patch(
                "galaxy_db_bridge.application.kline.command.get_valid_symbols_from_input"
            ) as mock_get_valid_symbols,
            patch(
                "galaxy_db_bridge.application.kline.command.validate_start_end_by_period"
            ) as mock_validate_period,
            patch(
                "galaxy_db_bridge.application.kline.command.validate_date_range"
            ) as mock_validate_range,
        ):

            # 设置模拟返回值
            mock_parse_symbols.return_value = [("symbol", "600000.SH")]
            mock_get_valid_symbols.return_value = ["600000.SH"]
            mock_validate_period.return_value = ("20230101", "20221231")
            mock_validate_range.return_value = [
                "开始日期 (20230101) 晚于结束日期 (20221231)"
            ]  # 返回错误信息

            # 调用 handle_kline_command 函数
            result = handle_kline_command(args)

            # 验证返回值为 1（表示错误）
            self.assertEqual(result, 1)

    @patch("logging.Logger.error")
    def test_handle_kline_command_exception_handling(self, mock_logger_error):
        """测试处理 kline 命令时异常处理."""
        # 创建一个具有有效参数的 mock args 对象
        args = argparse.Namespace()
        args.symbols = "600000.SH"
        args.interval = "day"
        args.start = "20230101"
        args.end = "20231231"

        # 模拟抛出异常的情况
        with patch(
            "galaxy_db_bridge.application.kline.command.parse_symbols"
        ) as mock_parse_symbols:
            mock_parse_symbols.side_effect = Exception("Test exception")

            # 调用 handle_kline_command 函数
            result = handle_kline_command(args)

            # 验证返回值为 1（表示错误）
            self.assertEqual(result, 1)
            # 验证错误日志被记录
            mock_logger_error.assert_called()
    def test_execute_kline_query_merges_multiple_missing_ranges_for_same_symbol(self):
        """测试 execute_kline_query 会合并同一代码多个缺失区间的 API 结果."""
        db_df = pd.DataFrame(
            {"close": [10.0]},
            index=pd.to_datetime(["2024-01-02"]),
        )

        api_df_first = pd.DataFrame(
            {"close": [11.0]},
            index=pd.to_datetime(["2024-01-03"]),
        )
        api_df_second = pd.DataFrame(
            {"close": [12.0]},
            index=pd.to_datetime(["2024-01-05"]),
        )

        with (
            patch(
                "galaxy_db_bridge.database.services.kline.kline_service.query_kline_from_db",
                return_value={"600000.SH": db_df},
            ),
            patch(
                "galaxy_db_bridge.database.services.kline.kline_service.merge_db_and_api_data"
            ) as mock_merge,
            patch(
                "galaxy_db_bridge.application.kline.command.kline_completeness_checker.check",
                return_value=CompletenessResult(
                    is_complete=False,
                    missing_count=2,
                    total_count=3,
                    coverage_ratio=1 / 3,
                    missing_ranges=[
                        (pd.Timestamp("2024-01-03").date(), pd.Timestamp("2024-01-03").date()),
                        (pd.Timestamp("2024-01-05").date(), pd.Timestamp("2024-01-05").date()),
                    ],
                    check_method="short_period_trading_day",
                ),
            ),
            patch(
                "galaxy_db_bridge.application.kline.command.query_kline_with_results"
            ) as mock_query,
        ):
            mock_query.side_effect = [
                MagicMock(
                    results={
                        "600000.SH": MagicMock(success=True, data=api_df_first)
                    }
                ),
                MagicMock(
                    results={
                        "600000.SH": MagicMock(success=True, data=api_df_second)
                    }
                ),
            ]
            mock_merge.side_effect = lambda db_data, api_data: api_data

            result = execute_kline_query(
                symbol_list=["600000.SH"],
                interval="day",
                start_date="20240101",
                end_date="20240110",
                interval_value=10008,
            )

        self.assertIn("600000.SH", result)
        self.assertEqual(len(result["600000.SH"]), 2)
        self.assertListEqual(
            [ts.strftime("%Y-%m-%d") for ts in result["600000.SH"].index],
            ["2024-01-03", "2024-01-05"],
        )
        mock_query.assert_called()
    def test_sync_kline_data_passes_interval_to_client_wrapper(self):
        """测试同步层调用包装器时使用 interval 参数名，而不是 SDK 的 period."""
        fake_df = pd.DataFrame(
            {"close": [123.45]},
            index=pd.to_datetime(["2017-04-05"]),
        )

        with (
            patch(
                "galaxy_db_bridge.database.services.kline_data_sync.parse_date_to_datetime",
                side_effect=[date(2017, 4, 5), date(2017, 4, 7)],
            ),
            patch(
                "galaxy_db_bridge.database.services.kline_data_sync.kline_completeness_checker.check",
                return_value=CompletenessResult(
                    is_complete=False,
                    missing_count=3,
                    total_count=3,
                    coverage_ratio=0.0,
                    missing_ranges=[(date(2017, 4, 5), date(2017, 4, 7))],
                    check_method="short_period_trading_day",
                ),
            ),
            patch(
                "galaxy_db_bridge.database.services.kline_data_sync.amazing_data_client.query_kline",
                return_value={"600519.SH": fake_df},
            ) as mock_query_kline,
            patch(
                "galaxy_db_bridge.database.services.kline_data_sync.infer_security_type",
                return_value="stock",
            ),
            patch(
                "galaxy_db_bridge.database.services.kline_data_sync.kline_service.save_kline_to_db",
                return_value=1,
            ) as mock_save,
        ):
            from galaxy_db_bridge.database.services.kline_data_sync import (
                kline_data_sync_service,
            )

            synced = kline_data_sync_service.sync_kline_data(
                symbol="600519.SH",
                interval="day",
                start_date="20170405",
                end_date="20170407",
                interval_value=10008,
            )

        self.assertEqual(synced, 1)
        mock_query_kline.assert_called_once_with(
            code_list=["600519.SH"],
            begin_date=20170405,
            end_date=20170407,
            interval=10008,
        )
        self.assertEqual(mock_query_kline.call_args.kwargs.get("period"), None)
        mock_save.assert_called_once()

    @patch("galaxy_db_bridge.database.services.trading_calendar.logger")
    @patch("galaxy_db_bridge.database.services.trading_calendar.db_manager")
    def test_get_trading_days_logs_cache_hit(self, mock_db_manager, mock_logger):
        """测试交易日历完整命中缓存时会输出命中日志."""
        session = MagicMock()
        mock_db_manager.get_session.return_value = session
        session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            SimpleNamespace(trade_date=date(2017, 4, 5), is_trading_day=True),
            SimpleNamespace(trade_date=date(2017, 4, 6), is_trading_day=True),
            SimpleNamespace(trade_date=date(2017, 4, 7), is_trading_day=True),
        ]

        with patch(
            "galaxy_db_bridge.database.services.trading_calendar.AkshareMarket.get_normalized_market",
            return_value="SSE",
        ):
            from galaxy_db_bridge.database.services.trading_calendar import (
                trading_calendar_service,
            )

            result = trading_calendar_service.get_trading_days(
                date(2017, 4, 5),
                date(2017, 4, 7),
                market="SSE",
            )

        self.assertEqual(
            result,
            [date(2017, 4, 5), date(2017, 4, 6), date(2017, 4, 7)],
        )
        mock_logger.info.assert_any_call(
            "交易日历缓存命中: market=SSE, range=2017-04-05~2017-04-07, calendar_rows=3, trading_days=3"
        )
        session.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
