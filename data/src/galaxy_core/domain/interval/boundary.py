"""周期边界计算纯函数.

从 shared_kernel/utils/interval_boundary_checker.py 提取的纯日期数学函数。
不依赖任何外部库（仅使用 Python 标准库）。
"""

from datetime import date, timedelta
from typing import Optional


# 长周期集合（字符串形式）
LONG_INTERVAL_VALUES = {"week", "month", "season", "year"}


def is_long_interval(interval_value: str) -> bool:
    """判断是否为长周期.

    Args:
        interval_value: 周期类型值 ("week", "month", "season", "year", "day" 等)

    Returns:
        bool: 是否为长周期
    """
    return interval_value in LONG_INTERVAL_VALUES


def is_interval_complete(
    interval_value: str,
    target_date: date,
    today: Optional[date] = None,
) -> bool:
    """判断指定日期所在的周期是否已结束.

    对于非长周期（分钟、小时、日线），始终返回 True。

    Args:
        interval_value: 周期类型值 ("week", "month", "season", "year", "day" 等)
        target_date: 目标日期
        today: 今天的日期，默认为系统当前日期

    Returns:
        bool: 周期是否已结束
    """
    if not is_long_interval(interval_value):
        return True

    if today is None:
        today = date.today()

    if interval_value == "week":
        return _is_week_complete(target_date, today)
    elif interval_value == "month":
        return _is_month_complete(target_date, today)
    elif interval_value == "season":
        return _is_season_complete(target_date, today)
    elif interval_value == "year":
        return _is_year_complete(target_date, today)

    return True


def get_interval_start_date(interval_value: str, target_date: date) -> date:
    """获取指定日期所在周期的开始日期.

    Args:
        interval_value: 周期类型值
        target_date: 目标日期

    Returns:
        date: 周期开始日期
    """
    if interval_value == "week":
        # 周一为一周的开始
        return target_date - timedelta(days=target_date.weekday())
    elif interval_value == "month":
        # 月初为一个月的开始
        return date(target_date.year, target_date.month, 1)
    elif interval_value == "season":
        # 季初为一个季度的开始
        quarter = get_quarter(target_date)
        start_month = _get_quarter_start_month(quarter)
        return date(target_date.year, start_month, 1)
    elif interval_value == "year":
        # 年初为一年的开始
        return date(target_date.year, 1, 1)
    else:
        return target_date


def get_quarter(target_date: date) -> int:
    """获取指定日期所在的季度.

    Args:
        target_date: 目标日期

    Returns:
        int: 季度（1-4）
    """
    return (target_date.month - 1) // 3 + 1


def _get_quarter_start_month(quarter: int) -> int:
    """获取季度的起始月份.

    Args:
        quarter: 季度（1-4）

    Returns:
        int: 起始月份（1, 4, 7, 10）
    """
    return (quarter - 1) * 3 + 1


def _get_quarter_end_month(quarter: int) -> int:
    """获取季度的结束月份.

    Args:
        quarter: 季度（1-4）

    Returns:
        int: 结束月份（3, 6, 9, 12）
    """
    return quarter * 3


def _is_week_complete(target_date: date, today: date) -> bool:
    """判断指定日期所在的周是否已结束.

    周结束的标志是下周一已经到来。

    Args:
        target_date: 目标日期
        today: 今天日期

    Returns:
        bool: 周是否已结束
    """
    # 获取目标日期所在周的周一
    week_start = target_date - timedelta(days=target_date.weekday())
    # 下周一
    next_week_start = week_start + timedelta(days=7)
    # 如果今天 >= 下周一，则本周已结束
    return today >= next_week_start


def _is_month_complete(target_date: date, today: date) -> bool:
    """判断指定日期所在的月是否已结束.

    月结束的标志是下月1日已经到来。

    Args:
        target_date: 目标日期
        today: 今天日期

    Returns:
        bool: 月是否已结束
    """
    # 计算下月1日
    if target_date.month == 12:
        first_of_next_month = date(target_date.year + 1, 1, 1)
    else:
        first_of_next_month = date(target_date.year, target_date.month + 1, 1)
    # 如果今天 >= 下月1日，则本月已结束
    return today >= first_of_next_month


def _is_season_complete(target_date: date, today: date) -> bool:
    """判断指定日期所在的季是否已结束.

    季结束的标志是下季首月1日已经到来。

    Args:
        target_date: 目标日期
        today: 今天日期

    Returns:
        bool: 季是否已结束
    """
    quarter = get_quarter(target_date)

    # 计算下季首月1日
    if quarter == 4:
        first_of_next_quarter = date(target_date.year + 1, 1, 1)
    else:
        first_of_next_quarter = date(target_date.year, _get_quarter_start_month(quarter + 1), 1)

    # 如果今天 >= 下季首月1日，则本季已结束
    return today >= first_of_next_quarter


def _is_year_complete(target_date: date, today: date) -> bool:
    """判断指定日期所在的年是否已结束.

    年结束的标志是下年1月1日已经到来。

    Args:
        target_date: 目标日期
        today: 今天日期

    Returns:
        bool: 年是否已结束
    """
    first_of_next_year = date(target_date.year + 1, 1, 1)
    return today >= first_of_next_year
