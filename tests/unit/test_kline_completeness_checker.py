"""K 线数据完整性检查器单元测试."""

import unittest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from galaxy_db_sync.database.services.kline_completeness_checker import (
    CompletenessResult,
    KlineCompletenessChecker,
    LongPeriodChecker,
    ShortPeriodChecker,
    kline_completeness_checker,
)
from galaxy_db_sync.shared_kernel.enums.interval import Interval


class TestCompletenessResult(unittest.TestCase):
    """CompletenessResult 数据类测试."""

    def test_str_representation(self):
        """测试字符串表示."""
        result = CompletenessResult(
            is_complete=True,
            missing_count=0,
            total_count=100,
            coverage_ratio=1.0,
            missing_ranges=[],
            check_method="test_method",
        )
        str_repr = str(result)
        self.assertIn("complete=True", str_repr)
        self.assertIn("coverage=100.00%", str_repr)
        self.assertIn("method=test_method", str_repr)


class TestLongPeriodChecker(unittest.TestCase):
    """长周期检查器测试."""

    def setUp(self):
        """设置测试环境."""
        self.checker = LongPeriodChecker()

    @patch(
        "galaxy_db_sync.database.services.kline_completeness_checker.trading_calendar_service"
    )
    @patch(
        "galaxy_db_sync.database.services.kline_completeness_checker.kline_service"
    )
    def test_month_data_complete(self, mock_kline_service, mock_calendar_service):
        """测试月线数据完整的情况."""
        # 模拟数据库返回的数据（使用每月第一个交易日）
        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.index = [
            datetime(2024, 1, 2),
            datetime(2024, 2, 1),
            datetime(2024, 3, 1),
        ]
        mock_kline_service.query_kline_from_db.return_value = {"000001.SZ": mock_df}
        mock_calendar_service.get_trading_days.side_effect = [
            [date(2024, 1, 2), date(2024, 1, 31)],
            [date(2024, 2, 1), date(2024, 2, 29)],
            [date(2024, 3, 1), date(2024, 3, 29)],
        ]

        result = self.checker.check(
            symbol="000001.SZ",
            interval=Interval.MONTH,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
        )

        self.assertTrue(result.is_complete)
        self.assertEqual(result.missing_count, 0)
        self.assertEqual(result.check_method, "long_period_continuity")

    @patch(
        "galaxy_db_sync.database.services.kline_completeness_checker.trading_calendar_service"
    )
    @patch(
        "galaxy_db_sync.database.services.kline_completeness_checker.kline_service"
    )
    def test_month_data_missing(self, mock_kline_service, mock_calendar_service):
        """测试月线数据缺失的情况."""
        # 模拟数据库返回的数据（缺少 2 月第一个交易日）
        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.index = [datetime(2024, 1, 2), datetime(2024, 3, 1)]
        mock_kline_service.query_kline_from_db.return_value = {"000001.SZ": mock_df}
        mock_calendar_service.get_trading_days.side_effect = [
            [date(2024, 1, 2), date(2024, 1, 31)],
            [date(2024, 2, 1), date(2024, 2, 29)],
            [date(2024, 3, 1), date(2024, 3, 29)],
        ]

        result = self.checker.check(
            symbol="000001.SZ",
            interval=Interval.MONTH,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
        )

        self.assertFalse(result.is_complete)
        self.assertGreater(result.missing_count, 0)
        self.assertLess(result.coverage_ratio, 1.0)

    @patch(
        "galaxy_db_sync.database.services.kline_completeness_checker.trading_calendar_service"
    )
    @patch(
        "galaxy_db_sync.database.services.kline_completeness_checker.kline_service"
    )
    def test_year_data(self, mock_kline_service, mock_calendar_service):
        """测试年线数据."""
        mock_df = MagicMock()
        mock_df.empty = False
        # 年线数据库存储的是每年第一个交易日
        mock_df.index = [datetime(2023, 1, 3), datetime(2024, 1, 2)]
        mock_kline_service.query_kline_from_db.return_value = {"000001.SZ": mock_df}
        mock_calendar_service.get_trading_days.side_effect = [
            [date(2023, 1, 3), date(2023, 12, 29)],
            [date(2024, 1, 2), date(2024, 12, 31)],
        ]

        result = self.checker.check(
            symbol="000001.SZ",
            interval=Interval.YEAR,
            start_date=date(2023, 1, 1),
            end_date=date(2024, 12, 31),
        )

        self.assertTrue(result.is_complete)
        self.assertEqual(result.total_count, 2)  # 2023 和 2024 两年

    @patch(
        "galaxy_db_sync.database.services.kline_completeness_checker.trading_calendar_service"
    )
    @patch(
        "galaxy_db_sync.database.services.kline_completeness_checker.kline_service"
    )
    def test_month_expected_dates_use_last_trading_day(
        self, mock_kline_service, mock_calendar_service
    ):
        """测试月线期望日期使用第一个交易日而非自然月初."""
        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.index = [datetime(2024, 1, 2), datetime(2024, 2, 1)]
        mock_kline_service.query_kline_from_db.return_value = {"000001.SZ": mock_df}
        mock_calendar_service.get_trading_days.side_effect = [
            [date(2024, 1, 2), date(2024, 1, 31)],
            [date(2024, 2, 1), date(2024, 2, 28)],
        ]

        result = self.checker.check(
            symbol="000001.SZ",
            interval=Interval.MONTH,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 29),
        )

        self.assertTrue(result.is_complete)
        self.assertEqual(mock_calendar_service.get_trading_days.call_count, 2)

    @patch(
        "galaxy_db_sync.database.services.kline_completeness_checker.trading_calendar_service"
    )
    def test_generate_expected_periods_month(self, mock_calendar_service):
        """测试生成月线期望周期."""
        mock_calendar_service.get_trading_days.side_effect = [
            [date(2024, 1, 2), date(2024, 1, 31)],
            [date(2024, 2, 1), date(2024, 2, 29)],
            [date(2024, 3, 1), date(2024, 3, 29)],
        ]
        periods = self.checker._generate_expected_periods(
            Interval.MONTH, date(2024, 1, 1), date(2024, 3, 31)
        )
        self.assertEqual(len(periods), 3)
        # 验证周期格式为 (周期开始, 周期结束, 第一个交易日)
        # period_end 是日历最后一天，first_trading_day 是第一个交易日
        self.assertEqual(periods[0], (date(2024, 1, 1), date(2024, 1, 31), date(2024, 1, 2)))
        self.assertEqual(periods[1], (date(2024, 2, 1), date(2024, 2, 29), date(2024, 2, 1)))
        self.assertEqual(periods[2], (date(2024, 3, 1), date(2024, 3, 31), date(2024, 3, 1)))

    @patch(
        "galaxy_db_sync.database.services.kline_completeness_checker.trading_calendar_service"
    )
    def test_generate_expected_periods_year(self, mock_calendar_service):
        """测试生成年线期望周期."""
        mock_calendar_service.get_trading_days.side_effect = [
            [date(2022, 12, 30)],
            [date(2023, 12, 29)],
            [date(2024, 12, 31)],
        ]
        periods = self.checker._generate_expected_periods(
            Interval.YEAR, date(2022, 1, 1), date(2024, 12, 31)
        )
        self.assertEqual(len(periods), 3)
        # 验证周期格式为 (年初, 年末, 第一个交易日)
        # period_end 是日历年末 (12-31)，first_trading_day 是该年第一个交易日
        self.assertEqual(periods[0], (date(2022, 1, 1), date(2022, 12, 31), date(2022, 12, 30)))
        self.assertEqual(periods[1], (date(2023, 1, 1), date(2023, 12, 31), date(2023, 12, 29)))
        self.assertEqual(periods[2], (date(2024, 1, 1), date(2024, 12, 31), date(2024, 12, 31)))

    @patch(
        "galaxy_db_sync.database.services.kline_completeness_checker.trading_calendar_service"
    )
    def test_merge_to_ranges_uses_period_start(self, mock_calendar_service):
        """测试合并范围使用周期边界作为范围."""
        # 模拟3个月的周期
        mock_calendar_service.get_trading_days.side_effect = [
            [date(2024, 1, 2), date(2024, 1, 31)],
            [date(2024, 2, 1), date(2024, 2, 29)],
            [date(2024, 3, 1), date(2024, 3, 29)],
        ]

        # 先生成周期列表
        periods = self.checker._generate_expected_periods(
            Interval.MONTH, date(2024, 1, 1), date(2024, 3, 31)
        )

        # 构建第一个交易日到周期边界的映射
        first_trading_day_to_period = {ftd: (ps, pe) for ps, pe, ftd in periods}

        # 模拟缺失1月和3月的数据（使用第一个交易日）
        # 故意跳过2月，测试非连续范围
        missing_dates = [date(2024, 1, 2), date(2024, 3, 1)]

        # 测试合并范围
        ranges = self.checker._merge_to_ranges(missing_dates, first_trading_day_to_period)

        # 验证范围：由于1月和3月不连续（中间有2月），应该分成2个范围
        # 范围使用周期边界 (period_start, period_end)，不是第一个交易日
        self.assertEqual(len(ranges), 2)
        self.assertEqual(ranges[0], (date(2024, 1, 1), date(2024, 1, 31)))  # 1月缺失范围（月初到月末）
        self.assertEqual(ranges[1], (date(2024, 3, 1), date(2024, 3, 31)))  # 3月缺失范围（月初到月末）


class TestShortPeriodChecker(unittest.TestCase):
    """短周期检查器测试."""

    def setUp(self):
        """设置测试环境."""
        self.checker = ShortPeriodChecker()

    @patch(
        "galaxy_db_sync.database.services.kline_completeness_checker.trading_calendar_service"
    )
    @patch(
        "galaxy_db_sync.database.services.kline_completeness_checker.kline_service"
    )
    def test_day_data_complete(self, mock_kline_service, mock_calendar_service):
        """测试日线数据完整的情况."""
        # 模拟交易日历
        trading_days = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
        mock_calendar_service.get_trading_days.return_value = trading_days

        # 模拟数据库返回的数据
        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.index = [
            datetime(2024, 1, 2),
            datetime(2024, 1, 3),
            datetime(2024, 1, 4),
        ]
        mock_kline_service.query_kline_from_db.return_value = {"000001.SZ": mock_df}

        result = self.checker.check(
            symbol="000001.SZ",
            interval=Interval.DAY,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 5),
        )

        self.assertTrue(result.is_complete)
        self.assertEqual(result.missing_count, 0)
        self.assertEqual(result.check_method, "short_period_trading_day")

    @patch(
        "galaxy_db_sync.database.services.kline_completeness_checker.trading_calendar_service"
    )
    @patch(
        "galaxy_db_sync.database.services.kline_completeness_checker.kline_service"
    )
    def test_day_data_missing(self, mock_kline_service, mock_calendar_service):
        """测试日线数据缺失的情况."""
        # 模拟交易日历
        trading_days = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
        mock_calendar_service.get_trading_days.return_value = trading_days

        # 模拟数据库返回的数据（缺少 1 月 3 日）
        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.index = [datetime(2024, 1, 2), datetime(2024, 1, 4)]
        mock_kline_service.query_kline_from_db.return_value = {"000001.SZ": mock_df}

        result = self.checker.check(
            symbol="000001.SZ",
            interval=Interval.DAY,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 5),
        )

        self.assertFalse(result.is_complete)
        self.assertEqual(result.missing_count, 1)
        self.assertEqual(len(result.missing_ranges), 1)

    @patch(
        "galaxy_db_sync.database.services.kline_completeness_checker.trading_calendar_service"
    )
    def test_no_trading_days(self, mock_calendar_service):
        """测试没有交易日的情况."""
        mock_calendar_service.get_trading_days.return_value = []

        result = self.checker.check(
            symbol="000001.SZ",
            interval=Interval.DAY,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 1),
        )

        self.assertTrue(result.is_complete)  # 没有交易日视为完整
        self.assertEqual(result.total_count, 0)


class TestKlineCompletenessChecker(unittest.TestCase):
    """KlineCompletenessChecker 主类测试."""

    def setUp(self):
        """设置测试环境."""
        self.checker = KlineCompletenessChecker()

    def test_is_long_period(self):
        """测试长周期判断."""
        self.assertTrue(self.checker._is_long_period(Interval.MONTH))
        self.assertTrue(self.checker._is_long_period(Interval.SEASON))
        self.assertTrue(self.checker._is_long_period(Interval.YEAR))
        self.assertFalse(self.checker._is_long_period(Interval.WEEK))
        self.assertFalse(self.checker._is_long_period(Interval.DAY))
        self.assertFalse(self.checker._is_long_period(Interval.MIN1))

    def test_normalize_interval(self):
        """测试 interval 标准化."""
        self.assertEqual(
            self.checker._normalize_interval(Interval.DAY),
            Interval.DAY,
        )
        self.assertEqual(
            self.checker._normalize_interval("day"),
            Interval.DAY,
        )
        self.assertEqual(
            self.checker._normalize_interval("DAY"),
            Interval.DAY,
        )

    def test_normalize_date(self):
        """测试日期标准化."""
        # date 对象
        d = date(2024, 1, 15)
        self.assertEqual(self.checker._normalize_date(d), d)

        # datetime 对象
        dt = datetime(2024, 1, 15, 10, 30, 0)
        self.assertEqual(self.checker._normalize_date(dt), d)

        # 字符串格式
        self.assertEqual(
            self.checker._normalize_date("20240115"),
            date(2024, 1, 15),
        )
        self.assertEqual(
            self.checker._normalize_date("2024-01-15"),
            date(2024, 1, 15),
        )
        self.assertEqual(
            self.checker._normalize_date("2024/01/15"),
            date(2024, 1, 15),
        )

    def test_normalize_date_invalid(self):
        """测试无效日期格式."""
        with self.assertRaises(ValueError):
            self.checker._normalize_date("invalid")

    @patch.object(LongPeriodChecker, "check")
    def test_check_uses_long_checker_for_month(self, mock_check):
        """测试月线使用长周期检查器."""
        mock_check.return_value = CompletenessResult(
            is_complete=True,
            missing_count=0,
            total_count=12,
            coverage_ratio=1.0,
            missing_ranges=[],
            check_method="long_period_continuity",
        )

        result = self.checker.check(
            symbol="000001.SZ",
            interval=Interval.MONTH,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        mock_check.assert_called_once()
        self.assertTrue(result.is_complete)

    @patch.object(ShortPeriodChecker, "check")
    def test_check_uses_short_checker_for_day(self, mock_check):
        """测试日线使用短周期检查器."""
        mock_check.return_value = CompletenessResult(
            is_complete=True,
            missing_count=0,
            total_count=20,
            coverage_ratio=1.0,
            missing_ranges=[],
            check_method="short_period_trading_day",
        )

        result = self.checker.check(
            symbol="000001.SZ",
            interval=Interval.DAY,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
        )

        mock_check.assert_called_once()
        self.assertTrue(result.is_complete)

    @patch.object(KlineCompletenessChecker, "check")
    def test_get_missing_dates(self, mock_check):
        """测试获取缺失日期列表."""
        mock_check.return_value = CompletenessResult(
            is_complete=False,
            missing_count=2,
            total_count=5,
            coverage_ratio=0.6,
            missing_ranges=[(date(2024, 1, 3), date(2024, 1, 4))],
            check_method="test",
        )

        missing_dates = self.checker.get_missing_dates(
            symbol="000001.SZ",
            interval=Interval.DAY,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 5),
        )

        self.assertEqual(len(missing_dates), 2)
        self.assertIn(date(2024, 1, 3), missing_dates)
        self.assertIn(date(2024, 1, 4), missing_dates)

    @patch.object(KlineCompletenessChecker, "check")
    def test_is_data_complete_with_coverage(self, mock_check):
        """测试覆盖率检查."""
        # 100% 覆盖
        mock_check.return_value = CompletenessResult(
            is_complete=True,
            missing_count=0,
            total_count=100,
            coverage_ratio=1.0,
            missing_ranges=[],
            check_method="test",
        )
        self.assertTrue(
            self.checker.is_data_complete(
                "000001.SZ", Interval.DAY, date(2024, 1, 1), date(2024, 1, 31)
            )
        )

        # 90% 覆盖，要求 95%
        mock_check.return_value = CompletenessResult(
            is_complete=False,
            missing_count=10,
            total_count=100,
            coverage_ratio=0.9,
            missing_ranges=[],
            check_method="test",
        )
        self.assertFalse(
            self.checker.is_data_complete(
                "000001.SZ",
                Interval.DAY,
                date(2024, 1, 1),
                date(2024, 1, 31),
                min_coverage=0.95,
            )
        )

        # 90% 覆盖，要求 85%
        self.assertTrue(
            self.checker.is_data_complete(
                "000001.SZ",
                Interval.DAY,
                date(2024, 1, 1),
                date(2024, 1, 31),
                min_coverage=0.85,
            )
        )


class TestGlobalInstance(unittest.TestCase):
    """测试全局实例."""

    def test_global_instance_exists(self):
        """测试全局实例存在."""
        self.assertIsInstance(kline_completeness_checker, KlineCompletenessChecker)



if __name__ == "__main__":
    unittest.main()
