"""日期范围合并纯函数.

从 shared_kernel/utils/date_range_utils.py 和 database/services/kline_data_sync.py 提取。
不依赖任何外部库。
"""

from datetime import date, timedelta


def merge_dates_to_ranges(
    dates: list[date],
    date_to_period: dict[date, tuple[date, date]] | None = None,
) -> list[tuple[date, date]]:
    """将日期列表合并为连续区间.

    支持两种模式：
    - 短周期模式（date_to_period 为 None）：按日期连续性合并，
      相邻日期相差不超过 1 天则视为同一区间。
    - 长周期模式（date_to_period 不为 None）：使用映射中的周期边界
      (period_start, period_end) 作为范围边界进行合并，
      相邻周期的 period_start 与当前 range_end 相差不超过 1 天则合并。

    Args:
        dates: 日期列表，无需预先排序。
        date_to_period: 日期到周期边界的映射，用于长周期模式。
            格式: {date: (period_start, period_end), ...}

    Returns:
        合并后的区间列表 [(range_start, range_end), ...]，按升序排列。
        空列表返回空列表。
    """
    if not dates:
        return []

    sorted_dates = sorted(dates)

    if date_to_period is not None:
        # 长周期模式：使用周期边界合并
        long_ranges: list[tuple[date, date]] = []
        current_range_start: date | None = None
        current_range_end: date | None = None

        for d in sorted_dates:
            if d not in date_to_period:
                continue

            period_start, period_end = date_to_period[d]

            if current_range_start is None:
                current_range_start = period_start
                current_range_end = period_end
            elif current_range_end is not None and period_start <= current_range_end + timedelta(days=1):
                # 当前周期与上一个连续，扩展范围
                current_range_end = period_end
            else:
                # 不连续，保存当前范围并开始新范围
                if current_range_start is not None and current_range_end is not None:
                    long_ranges.append((current_range_start, current_range_end))
                current_range_start = period_start
                current_range_end = period_end

        if current_range_start is not None and current_range_end is not None:
            long_ranges.append((current_range_start, current_range_end))

        return long_ranges

    # 短周期模式：简单连续日期合并
    short_ranges: list[tuple[date, date]] = []
    range_start = sorted_dates[0]
    range_end = sorted_dates[0]

    for current in sorted_dates[1:]:
        if current > range_end + timedelta(days=1):
            short_ranges.append((range_start, range_end))
            range_start = current
        range_end = current

    short_ranges.append((range_start, range_end))
    return short_ranges


def merge_small_gaps(
    missing_ranges: list[tuple[date, date]],
    max_gap_days: int = 5,
    min_ranges_to_trigger: int = 10,
) -> list[tuple[date, date]]:
    """合并间隔较小的缺失区间，减少 API 调用次数.

    当缺失区间数量超过 min_ranges_to_trigger 时，将间隔不超过
    max_gap_days 的相邻区间合并为一个大区间。
    重复数据通过 UPSERT 自动去重，不会重复存储。

    Args:
        missing_ranges: 原始缺失区间列表
        max_gap_days: 允许合并的最大间隔天数（默认 5）
        min_ranges_to_trigger: 触发合并的最小区间数量（默认 10）

    Returns:
        合并后的缺失区间列表
    """
    if len(missing_ranges) <= min_ranges_to_trigger:
        return missing_ranges

    sorted_ranges = sorted(missing_ranges, key=lambda x: x[0])
    merged = [sorted_ranges[0]]

    for current_start, current_end in sorted_ranges[1:]:
        last_start, last_end = merged[-1]
        gap = (current_start - last_end).days

        if gap <= max_gap_days:
            merged[-1] = (last_start, max(last_end, current_end))
        else:
            merged.append((current_start, current_end))

    return merged
