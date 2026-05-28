"""K 线非交易日行为测试."""

import unittest
from datetime import date
from unittest.mock import patch

from galaxy_db_bridge.database.services.kline_completeness_checker import (
    CompletenessResult,
)
from galaxy_db_bridge.application.kline.command import handle_kline_command
import argparse


class TestKlineNonTradingDay(unittest.TestCase):
    """测试非交易日不会触发同步."""

    def test_checker_treats_no_trading_days_as_complete(self):
        """测试完整性检查在无交易日范围内返回完整."""
        result = CompletenessResult(
            is_complete=True,
            missing_count=0,
            total_count=0,
            coverage_ratio=1.0,
            missing_ranges=[],
            check_method="short_period_trading_day",
        )

        self.assertTrue(result.is_complete)
        self.assertEqual(result.total_count, 0)
        self.assertEqual(result.missing_ranges, [])

    def test_command_skips_sync_for_non_trading_day_window(self):
        """测试命令层在非交易日时间窗内不触发同步."""
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


if __name__ == "__main__":
    unittest.main()
