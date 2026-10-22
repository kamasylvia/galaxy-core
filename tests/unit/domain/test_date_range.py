"""Domain 层日期范围合并纯函数单元测试.

测试 date_range/merger.py 的纯函数行为。
"""

from datetime import date

from galaxy_core.domain.date_range.merger import merge_dates_to_ranges, merge_small_gaps


class TestMergeDatesToRanges:
    """merge_dates_to_ranges 测试."""

    def test_short_period_mode(self):
        """短周期模式：连续日期合并."""
        dates = [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)]
        ranges = merge_dates_to_ranges(dates)
        assert len(ranges) == 2
        assert ranges[0] == (date(2025, 1, 2), date(2025, 1, 3))
        assert ranges[1] == (date(2025, 1, 6), date(2025, 1, 6))

    def test_long_period_mode(self):
        """长周期模式：使用周期边界合并."""
        dates = [date(2025, 1, 2), date(2025, 2, 3)]
        date_to_period = {
            date(2025, 1, 2): (date(2025, 1, 1), date(2025, 1, 31)),
            date(2025, 2, 3): (date(2025, 2, 1), date(2025, 2, 28)),
        }
        ranges = merge_dates_to_ranges(dates, date_to_period)
        assert len(ranges) == 1
        assert ranges[0] == (date(2025, 1, 1), date(2025, 2, 28))

    def test_empty_list(self):
        """空列表返回空."""
        assert merge_dates_to_ranges([]) == []

    def test_single_date(self):
        """单个日期."""
        ranges = merge_dates_to_ranges([date(2025, 1, 2)])
        assert ranges == [(date(2025, 1, 2), date(2025, 1, 2))]

    def test_unsorted_input(self):
        """无需预先排序."""
        dates = [date(2025, 1, 6), date(2025, 1, 2), date(2025, 1, 3)]
        ranges = merge_dates_to_ranges(dates)
        assert len(ranges) == 2


class TestMergeSmallGaps:
    """merge_small_gaps 测试."""

    def test_small_gap_merge(self):
        """小间隔合并."""
        ranges = [
            (date(2025, 1, 1), date(2025, 1, 5)),
            (date(2025, 1, 8), date(2025, 1, 10)),  # gap=2
        ]
        merged = merge_small_gaps(ranges, max_gap_days=5, min_ranges_to_trigger=1)
        assert len(merged) == 1
        assert merged[0] == (date(2025, 1, 1), date(2025, 1, 10))

    def test_large_gap_no_merge(self):
        """大间隔不合并."""
        ranges = [
            (date(2025, 1, 1), date(2025, 1, 5)),
            (date(2025, 1, 20), date(2025, 1, 25)),  # gap=14
        ]
        merged = merge_small_gaps(ranges, max_gap_days=5, min_ranges_to_trigger=1)
        assert len(merged) == 2

    def test_below_threshold(self):
        """低于阈值不合并."""
        ranges = [
            (date(2025, 1, 1), date(2025, 1, 5)),
            (date(2025, 1, 8), date(2025, 1, 10)),
        ]
        merged = merge_small_gaps(ranges, max_gap_days=5, min_ranges_to_trigger=10)
        assert len(merged) == 2  # 不合并，因为只有2个区间 < 10

    def test_empty_ranges(self):
        """空列表."""
        merged = merge_small_gaps([])
        assert merged == []
