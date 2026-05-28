"""Tests for IntervalBoundaryChecker.

测试周期边界检查器的各项功能。
"""

from datetime import date

from galaxy_db_sync.shared_kernel.enums.interval import Interval
from galaxy_db_sync.shared_kernel.utils.interval_boundary_checker import IntervalBoundaryChecker


class TestIntervalBoundaryCheckerInit:
    """测试初始化。"""

    def test_init_with_trading_calendar(self, mock_trading_calendar):
        """测试使用提供的交易日历初始化。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)
        assert checker.trading_calendar is mock_trading_calendar

    def test_init_without_trading_calendar(self):
        """测试不提供交易日历时自动创建。"""
        checker = IntervalBoundaryChecker()
        assert checker.trading_calendar is not None


class TestIsLongInterval:
    """测试长周期判断。"""

    def test_week_is_long_interval(self, mock_trading_calendar):
        """周线是长周期。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)
        assert checker.is_long_interval(Interval.WEEK) is True

    def test_month_is_long_interval(self, mock_trading_calendar):
        """月线是长周期。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)
        assert checker.is_long_interval(Interval.MONTH) is True

    def test_season_is_long_interval(self, mock_trading_calendar):
        """季线是长周期。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)
        assert checker.is_long_interval(Interval.SEASON) is True

    def test_year_is_long_interval(self, mock_trading_calendar):
        """年线是长周期。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)
        assert checker.is_long_interval(Interval.YEAR) is True

    def test_min1_is_not_long_interval(self, mock_trading_calendar):
        """1分钟线不是长周期。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)
        assert checker.is_long_interval(Interval.MIN1) is False

    def test_day_is_not_long_interval(self, mock_trading_calendar):
        """日线不是长周期。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)
        assert checker.is_long_interval(Interval.DAY) is False


class TestWeekIntervalComplete:
    """测试周线周期边界判断。"""

    def test_current_week_not_complete(self, mock_trading_calendar):
        """当前周未结束。"""
        # 假设今天是 2025-03-26（周三）
        today = date(2025, 3, 26)
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2025-03-24 是本周一
        assert checker.is_interval_complete(Interval.WEEK, date(2025, 3, 24), today) is False
        # 2025-03-26 是本周三
        assert checker.is_interval_complete(Interval.WEEK, date(2025, 3, 26), today) is False
        # 2025-03-28 是本周五
        assert checker.is_interval_complete(Interval.WEEK, date(2025, 3, 28), today) is False

    def test_previous_week_complete(self, mock_trading_calendar):
        """上一周已结束。"""
        # 假设今天是 2025-03-26（周三）
        today = date(2025, 3, 26)
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2025-03-17 是上周一
        assert checker.is_interval_complete(Interval.WEEK, date(2025, 3, 17), today) is True
        # 2025-03-21 是上周五
        assert checker.is_interval_complete(Interval.WEEK, date(2025, 3, 21), today) is True

    def test_week_complete_on_monday(self, mock_trading_calendar):
        """周一到来时上周结束。"""
        # 假设今天是 2025-03-31（周一）
        today = date(2025, 3, 31)
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2025-03-24 是上周一，应该已完成
        assert checker.is_interval_complete(Interval.WEEK, date(2025, 3, 24), today) is True
        # 2025-03-31 是本周一，未完成
        assert checker.is_interval_complete(Interval.WEEK, date(2025, 3, 31), today) is False


class TestMonthIntervalComplete:
    """测试月线周期边界判断。"""

    def test_current_month_not_complete(self, mock_trading_calendar):
        """当前月未结束。"""
        # 假设今天是 2025-03-15
        today = date(2025, 3, 15)
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2025-03-01 是本月第一天
        assert checker.is_interval_complete(Interval.MONTH, date(2025, 3, 1), today) is False
        # 2025-03-15 是本月中间
        assert checker.is_interval_complete(Interval.MONTH, date(2025, 3, 15), today) is False
        # 2025-03-31 是本月最后一天
        assert checker.is_interval_complete(Interval.MONTH, date(2025, 3, 31), today) is False

    def test_previous_month_complete(self, mock_trading_calendar):
        """上一月已结束。"""
        # 假设今天是 2025-03-15
        today = date(2025, 3, 15)
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2025-02-01 是上月第一天
        assert checker.is_interval_complete(Interval.MONTH, date(2025, 2, 1), today) is True
        # 2025-02-28 是上月最后一天
        assert checker.is_interval_complete(Interval.MONTH, date(2025, 2, 28), today) is True

    def test_month_complete_on_first_day(self, mock_trading_calendar):
        """下月1日到来时上月结束。"""
        # 假设今天是 2025-04-01（4月1日）
        today = date(2025, 4, 1)
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2025-03-01 是上月第一天，应该已完成
        assert checker.is_interval_complete(Interval.MONTH, date(2025, 3, 1), today) is True
        # 2025-03-31 是上月最后一天，应该已完成
        assert checker.is_interval_complete(Interval.MONTH, date(2025, 3, 31), today) is True
        # 2025-04-01 是本月第一天，未完成
        assert checker.is_interval_complete(Interval.MONTH, date(2025, 4, 1), today) is False

    def test_december_complete_on_january_first(self, mock_trading_calendar):
        """1月1日到来时12月结束。"""
        # 假设今天是 2025-01-01
        today = date(2025, 1, 1)
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2024-12-01 是去年12月第一天，应该已完成
        assert checker.is_interval_complete(Interval.MONTH, date(2024, 12, 1), today) is True
        # 2024-12-31 是去年12月最后一天，应该已完成
        assert checker.is_interval_complete(Interval.MONTH, date(2024, 12, 31), today) is True


class TestSeasonIntervalComplete:
    """测试季线周期边界判断。"""

    def test_q1_not_complete_in_march(self, mock_trading_calendar):
        """3月份Q1未结束。"""
        # 假设今天是 2025-03-15
        today = date(2025, 3, 15)
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # Q1（1-3月）未结束
        assert checker.is_interval_complete(Interval.SEASON, date(2025, 1, 1), today) is False
        assert checker.is_interval_complete(Interval.SEASON, date(2025, 2, 15), today) is False
        assert checker.is_interval_complete(Interval.SEASON, date(2025, 3, 31), today) is False

    def test_q4_complete_in_january(self, mock_trading_calendar):
        """1月份Q4已结束。"""
        # 假设今天是 2025-01-15
        today = date(2025, 1, 15)
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # Q4（10-12月）已结束
        assert checker.is_interval_complete(Interval.SEASON, date(2024, 10, 1), today) is True
        assert checker.is_interval_complete(Interval.SEASON, date(2024, 11, 15), today) is True
        assert checker.is_interval_complete(Interval.SEASON, date(2024, 12, 31), today) is True
        # Q1（1-3月）未结束
        assert checker.is_interval_complete(Interval.SEASON, date(2025, 1, 1), today) is False

    def test_q2_starts_on_april_first(self, mock_trading_calendar):
        """4月1日Q2开始，Q1结束。"""
        # 假设今天是 2025-04-01
        today = date(2025, 4, 1)
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # Q1（1-3月）已结束
        assert checker.is_interval_complete(Interval.SEASON, date(2025, 1, 1), today) is True
        assert checker.is_interval_complete(Interval.SEASON, date(2025, 3, 31), today) is True
        # Q2（4-6月）未结束
        assert checker.is_interval_complete(Interval.SEASON, date(2025, 4, 1), today) is False


class TestYearIntervalComplete:
    """测试年线周期边界判断。"""

    def test_current_year_not_complete(self, mock_trading_calendar):
        """当前年未结束。"""
        # 假设今天是 2025-06-15
        today = date(2025, 6, 15)
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2025年未结束
        assert checker.is_interval_complete(Interval.YEAR, date(2025, 1, 1), today) is False
        assert checker.is_interval_complete(Interval.YEAR, date(2025, 6, 15), today) is False
        assert checker.is_interval_complete(Interval.YEAR, date(2025, 12, 31), today) is False

    def test_previous_year_complete(self, mock_trading_calendar):
        """上一年已结束。"""
        # 假设今天是 2025-06-15
        today = date(2025, 6, 15)
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2024年已结束
        assert checker.is_interval_complete(Interval.YEAR, date(2024, 1, 1), today) is True
        assert checker.is_interval_complete(Interval.YEAR, date(2024, 6, 15), today) is True
        assert checker.is_interval_complete(Interval.YEAR, date(2024, 12, 31), today) is True

    def test_year_complete_on_january_first(self, mock_trading_calendar):
        """1月1日到来时上年结束。"""
        # 假设今天是 2025-01-01
        today = date(2025, 1, 1)
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2024年已结束
        assert checker.is_interval_complete(Interval.YEAR, date(2024, 12, 31), today) is True
        # 2025年未结束
        assert checker.is_interval_complete(Interval.YEAR, date(2025, 1, 1), today) is False


class TestShortIntervalComplete:
    """测试短周期始终返回 True。"""

    def test_min1_always_complete(self, mock_trading_calendar):
        """1分钟线始终完成。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        assert checker.is_interval_complete(Interval.MIN1, date(2025, 3, 26)) is True
        assert checker.is_interval_complete(Interval.MIN1, date(2025, 12, 31)) is True

    def test_day_always_complete(self, mock_trading_calendar):
        """日线始终完成。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        assert checker.is_interval_complete(Interval.DAY, date(2025, 3, 26)) is True
        assert checker.is_interval_complete(Interval.DAY, date(2025, 12, 31)) is True


class TestGetWeekEndDate:
    """测试获取周结束日期。"""

    def test_week_end_from_monday(self, mock_trading_calendar):
        """从周一开始获取周结束日期。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2025-03-24 是周一
        # 周末是 2025-03-30（周日），最后一个交易日是 2025-03-28（周五）
        result = checker.get_interval_end_date(Interval.WEEK, date(2025, 3, 24))
        assert result == date(2025, 3, 28)

    def test_week_end_from_friday(self, mock_trading_calendar):
        """从周五获取周结束日期。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2025-03-28 是周五
        result = checker.get_interval_end_date(Interval.WEEK, date(2025, 3, 28))
        assert result == date(2025, 3, 28)

    def test_week_end_from_sunday(self, mock_trading_calendar):
        """从周日获取周结束日期（应该返回同一周的周五）。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2025-03-30 是周日
        result = checker.get_interval_end_date(Interval.WEEK, date(2025, 3, 30))
        assert result == date(2025, 3, 28)


class TestGetMonthEndDate:
    """测试获取月结束日期。"""

    def test_month_end_february_non_leap_year(self, mock_trading_calendar):
        """非闰年2月结束日期。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2025-02 有 28 天，最后一天是周五
        result = checker.get_interval_end_date(Interval.MONTH, date(2025, 2, 15))
        assert result == date(2025, 2, 28)

    def test_month_end_february_leap_year(self, mock_trading_calendar):
        """闰年2月结束日期。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2024-02 有 29 天，最后一天是周四
        result = checker.get_interval_end_date(Interval.MONTH, date(2024, 2, 15))
        assert result == date(2024, 2, 29)

    def test_month_end_31_days(self, mock_trading_calendar):
        """31天的月份结束日期。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2025-03 有 31 天，最后一天是周一
        result = checker.get_interval_end_date(Interval.MONTH, date(2025, 3, 15))
        assert result == date(2025, 3, 31)

    def test_month_end_30_days(self, mock_trading_calendar):
        """30天的月份结束日期。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2025-04 有 30 天，最后一天是周三
        result = checker.get_interval_end_date(Interval.MONTH, date(2025, 4, 15))
        assert result == date(2025, 4, 30)


class TestGetSeasonEndDate:
    """测试获取季结束日期。"""

    def test_q1_end_date(self, mock_trading_calendar):
        """Q1结束日期（3月31日）。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2025 Q1 结束日期
        result = checker.get_interval_end_date(Interval.SEASON, date(2025, 1, 15))
        assert result == date(2025, 3, 31)

    def test_q2_end_date(self, mock_trading_calendar):
        """Q2结束日期（6月30日）。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2025 Q2 结束日期
        result = checker.get_interval_end_date(Interval.SEASON, date(2025, 4, 15))
        assert result == date(2025, 6, 30)

    def test_q3_end_date(self, mock_trading_calendar):
        """Q3结束日期（9月30日）。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2025 Q3 结束日期
        result = checker.get_interval_end_date(Interval.SEASON, date(2025, 7, 15))
        assert result == date(2025, 9, 30)

    def test_q4_end_date(self, mock_trading_calendar):
        """Q4结束日期（12月31日）。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2025 Q4 结束日期
        result = checker.get_interval_end_date(Interval.SEASON, date(2025, 10, 15))
        assert result == date(2025, 12, 31)


class TestGetYearEndDate:
    """测试获取年结束日期。"""

    def test_year_end_date(self, mock_trading_calendar):
        """年结束日期（12月31日）。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        result = checker.get_interval_end_date(Interval.YEAR, date(2025, 6, 15))
        assert result == date(2025, 12, 31)


class TestGetLastCompleteIntervalEnd:
    """测试获取最后一个已结束周期的结束日期。"""

    def test_last_complete_week_in_mid_week(self, mock_trading_calendar):
        """周中获取上周结束日期。"""
        # 假设今天是 2025-03-26（周三）
        today = date(2025, 3, 26)
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 上周结束日期应该是 2025-03-21（周五）
        result = checker.get_last_complete_interval_end(Interval.WEEK, reference_date=today, today=today)
        assert result == date(2025, 3, 21)

    def test_last_complete_month_in_mid_month(self, mock_trading_calendar):
        """月中获取上月结束日期。"""
        # 假设今天是 2025-03-15
        today = date(2025, 3, 15)
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 上月结束日期应该是 2025-02-28
        result = checker.get_last_complete_interval_end(Interval.MONTH, reference_date=today, today=today)
        assert result == date(2025, 2, 28)

    def test_last_complete_season_in_q1(self, mock_trading_calendar):
        """Q1获取Q4结束日期。"""
        # 假设今天是 2025-02-15
        today = date(2025, 2, 15)
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # Q4结束日期应该是 2024-12-31
        result = checker.get_last_complete_interval_end(Interval.SEASON, reference_date=today, today=today)
        assert result == date(2024, 12, 31)

    def test_last_complete_year_in_mid_year(self, mock_trading_calendar):
        """年中获取上年结束日期。"""
        # 假设今天是 2025-06-15
        today = date(2025, 6, 15)
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 上年结束日期应该是 2024-12-31
        result = checker.get_last_complete_interval_end(Interval.YEAR, reference_date=today, today=today)
        assert result == date(2024, 12, 31)

    def test_last_complete_interval_with_reference_date(self, mock_trading_calendar):
        """使用参考日期获取已结束周期。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 使用 2025-03-26 作为参考日期和今天
        reference_date = date(2025, 3, 26)
        today = date(2025, 3, 26)

        # 周线：上周结束日期
        result = checker.get_last_complete_interval_end(Interval.WEEK, reference_date, today)
        assert result == date(2025, 3, 21)

        # 月线：上月结束日期
        result = checker.get_last_complete_interval_end(Interval.MONTH, reference_date, today)
        assert result == date(2025, 2, 28)

        # 季线：Q4结束日期
        result = checker.get_last_complete_interval_end(Interval.SEASON, reference_date, today)
        assert result == date(2024, 12, 31)

        # 年线：上年结束日期
        result = checker.get_last_complete_interval_end(Interval.YEAR, reference_date, today)
        assert result == date(2024, 12, 31)


class TestGetQuarter:
    """测试季度计算。"""

    def test_q1_months(self, mock_trading_calendar):
        """Q1月份（1-3月）。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        assert checker._get_quarter(date(2025, 1, 15)) == 1
        assert checker._get_quarter(date(2025, 2, 15)) == 1
        assert checker._get_quarter(date(2025, 3, 15)) == 1

    def test_q2_months(self, mock_trading_calendar):
        """Q2月份（4-6月）。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        assert checker._get_quarter(date(2025, 4, 15)) == 2
        assert checker._get_quarter(date(2025, 5, 15)) == 2
        assert checker._get_quarter(date(2025, 6, 15)) == 2

    def test_q3_months(self, mock_trading_calendar):
        """Q3月份（7-9月）。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        assert checker._get_quarter(date(2025, 7, 15)) == 3
        assert checker._get_quarter(date(2025, 8, 15)) == 3
        assert checker._get_quarter(date(2025, 9, 15)) == 3

    def test_q4_months(self, mock_trading_calendar):
        """Q4月份（10-12月）。"""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        assert checker._get_quarter(date(2025, 10, 15)) == 4
        assert checker._get_quarter(date(2025, 11, 15)) == 4
        assert checker._get_quarter(date(2025, 12, 15)) == 4


class TestEdgeCases:
    """测试边界情况。"""

    def test_leap_year_february(self, mock_trading_calendar):
        """闰年2月测试。"""
        # 假设今天是 2024-02-15
        today = date(2024, 2, 15)
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2024-02-29 是闰年2月最后一天
        assert checker.is_interval_complete(Interval.MONTH, date(2024, 2, 15), today) is False

        # 月结束日期应该是 2024-02-29
        result = checker.get_interval_end_date(Interval.MONTH, date(2024, 2, 15))
        assert result == date(2024, 2, 29)

    def test_year_boundary(self, mock_trading_calendar):
        """年边界测试。"""
        # 假设今天是 2025-01-01
        today = date(2025, 1, 1)
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2024年应该已完成
        assert checker.is_interval_complete(Interval.YEAR, date(2024, 12, 31), today) is True
        # 2025年未完成
        assert checker.is_interval_complete(Interval.YEAR, date(2025, 1, 1), today) is False

    def test_week_boundary_sunday_to_monday(self, mock_trading_calendar):
        """周日到周一的周边界测试。"""
        # 假设今天是 2025-03-31（周一）
        today = date(2025, 3, 31)
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        # 2025-03-30 是上周日，所在周应该已完成
        assert checker.is_interval_complete(Interval.WEEK, date(2025, 3, 30), today) is True
        # 2025-03-31 是本周一，所在周未完成
        assert checker.is_interval_complete(Interval.WEEK, date(2025, 3, 31), today) is False


import pytest


class TestIsLastTradingDayOfPeriod:
    """Tests for is_last_trading_day_of_period method."""

    @pytest.mark.asyncio
    async def test_week_last_day_is_last_trading_day(self, mock_trading_calendar):
        """Friday is last trading day of week."""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)
        # 2025-03-28 is Friday, last trading day of that week
        result = await checker.is_last_trading_day_of_period(Interval.WEEK, date(2025, 3, 28))
        assert result is True

    @pytest.mark.asyncio
    async def test_week_midweek_not_last_trading_day(self, mock_trading_calendar):
        """Thursday is not last trading day of week."""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)
        result = await checker.is_last_trading_day_of_period(Interval.WEEK, date(2025, 3, 27))
        assert result is False

    @pytest.mark.asyncio
    async def test_month_last_day_is_last_trading_day(self, mock_trading_calendar):
        """Last trading day of month."""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)
        # 2025-03-31 is Monday, last day of March
        result = await checker.is_last_trading_day_of_period(Interval.MONTH, date(2025, 3, 31))
        assert result is True

    @pytest.mark.asyncio
    async def test_month_mid_month_not_last_trading_day(self, mock_trading_calendar):
        """Mid-month is not last trading day."""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)
        result = await checker.is_last_trading_day_of_period(Interval.MONTH, date(2025, 3, 15))
        assert result is False

    @pytest.mark.asyncio
    async def test_year_last_day_is_last_trading_day(self, mock_trading_calendar):
        """Dec 31 is last trading day of year."""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)
        result = await checker.is_last_trading_day_of_period(Interval.YEAR, date(2025, 12, 31))
        assert result is True

    @pytest.mark.asyncio
    async def test_day_always_true(self, mock_trading_calendar):
        """DAY interval always returns True (sync daily)."""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)
        result = await checker.is_last_trading_day_of_period(Interval.DAY, date(2025, 3, 15))
        assert result is True


class TestGetPeriodsToSyncToday:
    """Tests for get_periods_to_sync_today method."""

    @pytest.mark.asyncio
    async def test_friday_returns_day_and_week(self, mock_trading_calendar):
        """Friday at 23:00 syncs DAY and WEEK."""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)
        result = await checker.get_periods_to_sync_today(date(2025, 3, 28))
        assert Interval.DAY in result
        assert Interval.WEEK in result

    @pytest.mark.asyncio
    async def test_month_end_returns_day_and_month(self, mock_trading_calendar):
        """Month last trading day syncs DAY and MONTH."""
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)
        result = await checker.get_periods_to_sync_today(date(2025, 3, 31))
        assert Interval.DAY in result
        assert Interval.MONTH in result
