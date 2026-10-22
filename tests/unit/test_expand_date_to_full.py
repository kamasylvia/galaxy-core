"""expand_date_to_full() 统一日期扩展函数测试.

覆盖各种周期和边界情况：年、月、季、日、周、闰年等。
"""

import pytest

from galaxy_core.shared_kernel.utils.time_parser import expand_date_to_full


class TestExpandDateToFullYear:
    """测试年周期日期扩展."""

    def test_year_start(self):
        """年周期开始日期 → YYYY0101."""
        assert expand_date_to_full("2024", "year", False) == "20240101"

    def test_year_end(self):
        """年周期结束日期 → YYYY1231."""
        assert expand_date_to_full("2024", "year", True) == "20241231"

    def test_year_none_input(self):
        """None 输入应返回 None."""
        assert expand_date_to_full(None, "year") is None


class TestExpandDateToFullMonth:
    """测试月周期日期扩展."""

    def test_month_6digit_start(self):
        """6 位月份开始日期 → YYYYMM01."""
        assert expand_date_to_full("202403", "month", False) == "20240301"

    def test_month_6digit_end(self):
        """6 位月份结束日期 → YYYYMM+月末."""
        assert expand_date_to_full("202403", "month", True) == "20240331"

    def test_month_leap_year_end(self):
        """闰年 2 月结束日期 → 2月29日."""
        assert expand_date_to_full("202402", "month", True) == "20240229"

    def test_month_non_leap_year_end(self):
        """非闰年 2 月结束日期 → 2月28日."""
        assert expand_date_to_full("202302", "month", True) == "20230228"

    def test_month_4digit_start(self):
        """4 位年份作为月周期开始 → YYYY0101."""
        assert expand_date_to_full("2024", "month", False) == "20240101"

    def test_month_4digit_end(self):
        """4 位年份作为月周期结束 → YYYY1231."""
        assert expand_date_to_full("2024", "month", True) == "20241231"


class TestExpandDateToFullSeason:
    """测试季周期日期扩展."""

    def test_season_6digit_start(self):
        """6 位季开始日期 → YYYYMM01."""
        assert expand_date_to_full("202403", "season", False) == "20240301"

    def test_season_6digit_end(self):
        """6 位季结束日期 → YYYYMM+月末."""
        assert expand_date_to_full("202403", "season", True) == "20240331"

    def test_season_4digit_start(self):
        """4 位年份作为季开始 → YYYY0101."""
        assert expand_date_to_full("2024", "season", False) == "20240101"


class TestExpandDateToFullDay:
    """测试日周期日期扩展."""

    def test_day_8digit(self):
        """8 位日期原样返回."""
        assert expand_date_to_full("20240315", "day", False) == "20240315"

    def test_day_6digit_start(self):
        """6 位月份作为日周期开始 → YYYYMM01."""
        assert expand_date_to_full("202403", "day", False) == "20240301"

    def test_day_6digit_end(self):
        """6 位月份作为日周期结束 → YYYYMM+月末."""
        assert expand_date_to_full("202403", "day", True) == "20240331"

    def test_day_4digit_start(self):
        """4 位年份作为日周期开始 → YYYY0101."""
        assert expand_date_to_full("2024", "day", False) == "20240101"

    def test_day_4digit_end(self):
        """4 位年份作为日周期结束 → YYYY1231."""
        assert expand_date_to_full("2024", "day", True) == "20241231"

    def test_day_none_input(self):
        """None 输入应返回 None."""
        assert expand_date_to_full(None, "day") is None


class TestExpandDateToFullWeek:
    """测试周周期日期扩展."""

    def test_week_8digit(self):
        """8 位日期原样返回."""
        assert expand_date_to_full("20240315", "week", False) == "20240315"

    def test_week_6digit_start(self):
        """6 位月份作为周周期开始 → YYYYMM01."""
        assert expand_date_to_full("202403", "week", False) == "20240301"

    def test_week_4digit_end(self):
        """4 位年份作为周周期结束 → YYYY1231."""
        assert expand_date_to_full("2024", "week", True) == "20241231"


class TestExpandDateToFullMinInterval:
    """测试分钟周期日期扩展."""

    def test_min_8digit(self):
        """8 �日期原样返回."""
        assert expand_date_to_full("20240315", "min1", False) == "20240315"

    def test_min_4digit_start(self):
        """4 位年份作为分钟周期开始 → YYYY0101."""
        assert expand_date_to_full("2024", "min1", False) == "20240101"
