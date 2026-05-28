"""K 线完整性检查器异步方法测试."""

import unittest
from datetime import date
from unittest.mock import patch, AsyncMock, MagicMock
import pandas as pd


class TestKlineCompletenessCheckerAsync(unittest.TestCase):
    """完整性检查异步方法测试类."""

    def test_check_async_handles_empty_data(self):
        """测试异步检查处理空数据."""
        async def run_test():
            from galaxy_db_sync.database.services.kline_completeness_checker import (
                KlineCompletenessChecker,
            )
            from galaxy_db_sync.shared_kernel.enums.interval import Interval

            checker = KlineCompletenessChecker()

            # Mock kline_service 返回空数据
            with patch(
                "galaxy_db_sync.database.services.kline_completeness_checker.kline_service.query_kline_from_db",
                return_value={"600519.SH": pd.DataFrame()},
            ):
                # Mock trading_calendar 返回交易日
                with patch(
                    "galaxy_db_sync.database.services.kline_completeness_checker.trading_calendar_service.get_trading_days_async",
                    return_value=[date(2024, 1, 2), date(2024, 1, 3)],
                ):
                    result = await checker.check_async(
                        symbol="600519.SH",
                        interval=Interval.DAY,
                        start_date=date(2024, 1, 1),
                        end_date=date(2024, 1, 5),
                    )
                    return result

        import asyncio
        result = asyncio.run(run_test())

        # 验证结果结构正确
        self.assertIsNotNone(result)
        self.assertIn('is_complete', result.__dict__)
        self.assertIn('missing_count', result.__dict__)

    def test_long_period_checker_async_returns_correct_structure(self):
        """测试长周期异步检查返回正确结构."""
        async def run_test():
            from galaxy_db_sync.database.services.kline_completeness_checker import (
                LongPeriodChecker,
            )
            from galaxy_db_sync.shared_kernel.enums.interval import Interval

            checker = LongPeriodChecker()

            # Mock get_trading_days_async
            with patch(
                "galaxy_db_sync.database.services.kline_completeness_checker.trading_calendar_service.get_trading_days_async",
                return_value=[date(2024, 1, 2)],
            ):
                # Mock kline_service 返回空
                with patch(
                    "galaxy_db_sync.database.services.kline_completeness_checker.kline_service.query_kline_from_db",
                    return_value={"600519.SH": pd.DataFrame()},
                ):
                    result = await checker.check_async(
                        symbol="600519.SH",
                        interval=Interval.MONTH,
                        start_date=date(2024, 1, 1),
                        end_date=date(2024, 1, 31),
                    )
                    return result

        import asyncio
        result = asyncio.run(run_test())

        self.assertIsNotNone(result)
        self.assertEqual(result.check_method, "long_period_continuity_async")


if __name__ == "__main__":
    unittest.main()