"""测试日期区间合并工具函数."""

from datetime import date

from galaxy_core.shared_kernel.utils.date_range_utils import merge_dates_to_ranges


class TestMergeDatesToRanges:
    """测试 merge_dates_to_ranges 函数."""

    def test_empty_list(self):
        """空列表应返回空列表."""
        assert merge_dates_to_ranges([]) == []

    def test_single_date(self):
        """单个日期应返回一个区间."""
        d = date(2024, 1, 15)
        assert merge_dates_to_ranges([d]) == [(d, d)]

    def test_consecutive_dates(self):
        """连续日期应合并为一个区间."""
        dates = [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)]
        assert merge_dates_to_ranges(dates) == [(date(2024, 1, 1), date(2024, 1, 3))]

    def test_non_consecutive_dates(self):
        """不连续日期应分为多个区间."""
        dates = [
            date(2024, 1, 1),
            date(2024, 1, 2),
            date(2024, 1, 5),
            date(2024, 1, 6),
            date(2024, 1, 10),
        ]
        result = merge_dates_to_ranges(dates)
        expected = [
            (date(2024, 1, 1), date(2024, 1, 2)),
            (date(2024, 1, 5), date(2024, 1, 6)),
            (date(2024, 1, 10), date(2024, 1, 10)),
        ]
        assert result == expected

    def test_unsorted_input(self):
        """无序输入应自动排序后合并."""
        dates = [date(2024, 1, 3), date(2024, 1, 1), date(2024, 1, 2)]
        assert merge_dates_to_ranges(dates) == [(date(2024, 1, 1), date(2024, 1, 3))]

    def test_long_period_mode(self):
        """长周期模式应使用周期边界合并."""
        dates = [date(2024, 1, 2), date(2024, 2, 1), date(2024, 3, 1)]
        date_to_period = {
            date(2024, 1, 2): (date(2024, 1, 1), date(2024, 1, 31)),
            date(2024, 2, 1): (date(2024, 2, 1), date(2024, 2, 29)),
            date(2024, 3, 1): (date(2024, 3, 1), date(2024, 3, 31)),
        }
        result = merge_dates_to_ranges(dates, date_to_period)
        # 三个周期连续，应合并为一个区间
        expected = [(date(2024, 1, 1), date(2024, 3, 31))]
        assert result == expected

    def test_long_period_mode_with_gap(self):
        """长周期模式下不连续的周期应分为多个区间."""
        dates = [date(2024, 1, 2), date(2024, 3, 1)]
        date_to_period = {
            date(2024, 1, 2): (date(2024, 1, 1), date(2024, 1, 31)),
            date(2024, 3, 1): (date(2024, 3, 1), date(2024, 3, 31)),
        }
        result = merge_dates_to_ranges(dates, date_to_period)
        # 中间缺少2月，应分为两个区间
        expected = [
            (date(2024, 1, 1), date(2024, 1, 31)),
            (date(2024, 3, 1), date(2024, 3, 31)),
        ]
        assert result == expected

    def test_long_period_mode_empty_list(self):
        """长周期模式下空列表应返回空列表."""
        assert merge_dates_to_ranges([], date_to_period={}) == []

    def test_long_period_mode_missing_mapping(self):
        """长周期模式下缺少映射的日期应被跳过."""
        dates = [date(2024, 1, 2), date(2024, 2, 1)]
        date_to_period = {
            date(2024, 1, 2): (date(2024, 1, 1), date(2024, 1, 31)),
            # date(2024, 2, 1) 不在映射中
        }
        result = merge_dates_to_ranges(dates, date_to_period)
        expected = [(date(2024, 1, 1), date(2024, 1, 31))]
        assert result == expected

    def test_long_period_mode_single_date(self):
        """长周期模式下单个日期应返回一个区间."""
        d = date(2024, 1, 2)
        date_to_period = {d: (date(2024, 1, 1), date(2024, 1, 31))}
        assert merge_dates_to_ranges([d], date_to_period) == [(date(2024, 1, 1), date(2024, 1, 31))]

    def test_gap_of_exactly_one_day(self):
        """间隔恰好为1天的日期不应合并."""
        dates = [date(2024, 1, 1), date(2024, 1, 3)]
        result = merge_dates_to_ranges(dates)
        expected = [
            (date(2024, 1, 1), date(2024, 1, 1)),
            (date(2024, 1, 3), date(2024, 1, 3)),
        ]
        assert result == expected

    def test_long_period_mode_adjacent_periods(self):
        """长周期模式下相邻周期（period_start == current_range_end + 1天）应合并."""
        dates = [date(2024, 1, 31), date(2024, 2, 1)]
        date_to_period = {
            date(2024, 1, 31): (date(2024, 1, 1), date(2024, 1, 31)),
            date(2024, 2, 1): (date(2024, 2, 1), date(2024, 2, 29)),
        }
        result = merge_dates_to_ranges(dates, date_to_period)
        # period_start(2024-02-01) == current_range_end(2024-01-31) + 1天，应合并
        expected = [(date(2024, 1, 1), date(2024, 2, 29))]
        assert result == expected
