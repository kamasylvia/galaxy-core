"""Domain 层周期边界纯函数单元测试.

测试 interval/boundary.py 的纯函数行为。
"""

from datetime import date

from galaxy_core.domain.interval.boundary import (
    is_long_interval,
    is_interval_complete,
    get_interval_start_date,
    get_quarter,
)


class TestIsLongInterval:
    """is_long_interval 测试."""

    def test_week_is_long(self):
        """周线是长周期."""
        assert is_long_interval("week") is True

    def test_month_is_long(self):
        """月线是长周期."""
        assert is_long_interval("month") is True

    def test_season_is_long(self):
        """季线是长周期."""
        assert is_long_interval("season") is True

    def test_year_is_long(self):
        """年线是长周期."""
        assert is_long_interval("year") is True

    def test_day_is_not_long(self):
        """日线不是长周期."""
        assert is_long_interval("day") is False

    def test_min1_is_not_long(self):
        """1分钟线不是长周期."""
        assert is_long_interval("min1") is False


class TestIsIntervalComplete:
    """is_interval_complete 测试."""

    def test_week_complete(self):
        """上周已结束."""
        # 假设今天是 2025-03-26（周三）
        assert is_interval_complete("week", date(2025, 3, 17), date(2025, 3, 26)) is True

    def test_week_not_complete(self):
        """本周未结束."""
        assert is_interval_complete("week", date(2025, 3, 24), date(2025, 3, 26)) is False

    def test_month_complete(self):
        """上月已结束."""
        assert is_interval_complete("month", date(2025, 2, 1), date(2025, 3, 26)) is True

    def test_month_not_complete(self):
        """本月未结束."""
        assert is_interval_complete("month", date(2025, 3, 1), date(2025, 3, 26)) is False

    def test_season_complete(self):
        """上季已结束."""
        assert is_interval_complete("season", date(2024, 10, 1), date(2025, 3, 26)) is True

    def test_season_not_complete(self):
        """本季未结束."""
        assert is_interval_complete("season", date(2025, 1, 1), date(2025, 3, 26)) is False

    def test_year_complete(self):
        """去年已结束."""
        assert is_interval_complete("year", date(2024, 1, 1), date(2025, 3, 26)) is True

    def test_year_not_complete(self):
        """今年未结束."""
        assert is_interval_complete("year", date(2025, 1, 1), date(2025, 3, 26)) is False

    def test_day_always_complete(self):
        """日线始终返回 True."""
        assert is_interval_complete("day", date(2025, 3, 26), date(2025, 3, 26)) is True


class TestGetIntervalStartDate:
    """get_interval_start_date 测试."""

    def test_week_start(self):
        """周一开始."""
        # 2025-03-26 是周三
        assert get_interval_start_date("week", date(2025, 3, 26)) == date(2025, 3, 24)

    def test_month_start(self):
        """月初开始."""
        assert get_interval_start_date("month", date(2025, 3, 26)) == date(2025, 3, 1)

    def test_season_start(self):
        """季初开始."""
        assert get_interval_start_date("season", date(2025, 3, 26)) == date(2025, 1, 1)
        assert get_interval_start_date("season", date(2025, 5, 15)) == date(2025, 4, 1)

    def test_year_start(self):
        """年初开始."""
        assert get_interval_start_date("year", date(2025, 3, 26)) == date(2025, 1, 1)

    def test_day_start(self):
        """日线返回当天."""
        assert get_interval_start_date("day", date(2025, 3, 26)) == date(2025, 3, 26)


class TestGetQuarter:
    """get_quarter 测试."""

    def test_q1(self):
        """第一季度."""
        assert get_quarter(date(2025, 1, 15)) == 1
        assert get_quarter(date(2025, 3, 31)) == 1

    def test_q2(self):
        """第二季度."""
        assert get_quarter(date(2025, 4, 1)) == 2
        assert get_quarter(date(2025, 6, 30)) == 2

    def test_q3(self):
        """第三季度."""
        assert get_quarter(date(2025, 7, 1)) == 3
        assert get_quarter(date(2025, 9, 30)) == 3

    def test_q4(self):
        """第四季度."""
        assert get_quarter(date(2025, 10, 1)) == 4
        assert get_quarter(date(2025, 12, 31)) == 4
