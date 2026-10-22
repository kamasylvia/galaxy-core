"""日期解析纯函数.

从 shared_kernel/utils/time_parser.py 提取的纯函数。
不依赖任何外部库（仅使用 Python 标准库）。
"""

import calendar
from datetime import datetime
from typing import Optional


def parse_date_to_int(date_str: str) -> int:
    """将日期字符串解析为整数 YYYYMMDD 格式.

    Args:
        date_str: 日期字符串 (至少包含8位数字)

    Returns:
        YYYYMMDD 格式的整数
    """
    return int(date_str[:8])


def int_to_datetime(date_int: int) -> datetime:
    """将整数日期转换为 datetime 对象.

    Args:
        date_int: YYYYMMDD 格式的整数日期

    Returns:
        datetime 对象
    """
    return datetime.strptime(str(date_int), "%Y%m%d")


def datetime_to_int(dt: datetime) -> int:
    """将 datetime 对象转换为整数日期.

    Args:
        dt: datetime 对象

    Returns:
        YYYYMMDD 格式的整数
    """
    return int(dt.strftime("%Y%m%d"))


def expand_date_to_full(
    date_str: Optional[str], interval: str, is_end: bool = False
) -> Optional[str]:
    """将原始精度日期补全为完整 8 位 YYYYMMDD 格式（统一入口）.

    合并了 pad_date_to_full_format、parse_date_to_datetime、
    parse_date_for_interval、_expand_date_by_interval 四个函数的逻辑。

    Args:
        date_str: 原始精度日期字符串（4 位 YYYY、6 位 YYYYMM 或 8 位 YYYYMMDD）
        interval: 周期类型（如 "year", "month", "season", "day", "week" 等）
        is_end: 是否为结束日期（影响补全方向：年初 vs 年末，月初 vs 月末）

    Returns:
        8 位 YYYYMMDD 格式的完整日期字符串，或 None（输入为 None 时）
    """
    if date_str is None:
        return None

    length = len(date_str)

    if interval == "year":
        # 年线：4 位 YYYY → 返回 YYYY0101 或 YYYY1231
        year = int(date_str[:4])
        if is_end:
            return f"{year}1231"
        else:
            return f"{year}0101"

    elif interval in ("season", "month"):
        # 月线/季线
        if length <= 4:
            # 只有年份 → 补全为年初或年末
            year = int(date_str[:4])
            if is_end:
                return f"{year}1231"
            else:
                return f"{year}0101"
        else:
            # 有年月信息（6 位或更多）
            date_str_padded = date_str.zfill(6)
            year = int(date_str_padded[:4])
            month = int(date_str_padded[4:6])
            if is_end:
                last_day = calendar.monthrange(year, month)[1]
                return f"{year}{month:02d}{last_day:02d}"
            else:
                return f"{year}{month:02d}01"

    else:
        # day, week, min* 等短周期
        if length == 4:
            # 4 位年份 → 补全为 YYYY0101 或 YYYY1231
            year = int(date_str[:4])
            if is_end:
                return f"{year}1231"
            else:
                return f"{year}0101"
        elif length == 6:
            # 6 位 YYYYMM → 补全为 YYYYMM01 或 YYYYMM+月末
            year = int(date_str[:4])
            month = int(date_str[4:6])
            if is_end:
                last_day = calendar.monthrange(year, month)[1]
                return f"{year}{month:02d}{last_day:02d}"
            else:
                return f"{year}{month:02d}01"
        else:
            # 8 位及以上 → 截取前 8 位
            return date_str[:8] if len(date_str) >= 8 else date_str.zfill(8)


def validate_date_length_for_interval(
    date_str: str, interval: str, field_name: str = "日期"
) -> list[str]:
    """校验日期长度是否符合周期精度要求.

    Args:
        date_str: 日期字符串
        interval: 周期类型
        field_name: 字段名称，用于错误信息

    Returns:
        错误信息列表
    """
    errors = []
    if date_str is None:
        return errors

    length = len(date_str)

    # 定义各周期可接受的日期位数
    length_requirements = {
        "year": [4],
        "season": [4, 6],
        "month": [4, 6],
        "week": [4, 6, 8],
        "day": [4, 6, 8],
        "min60": [8, 10],
        "min120": [8, 10],
        "min1": [8, 10, 12],
        "min3": [8, 10, 12],
        "min5": [8, 10, 12],
        "min10": [8, 10, 12],
        "min15": [8, 10, 12],
        "min30": [8, 10, 12],
    }

    acceptable_lengths = length_requirements.get(interval, [8])  # 默认按日线处理

    if length not in acceptable_lengths:
        # 构建友好的错误信息
        length_desc = {
            4: "4 位年份 (YYYY)",
            6: "6 位年月 (YYYYMM)",
            8: "8 位日期 (YYYYMMDD)",
            10: "10 位日期+小时 (YYYYMMDDHH)",
            12: "12 位日期+时分 (YYYYMMDDHHMM)",
        }
        acceptable_desc = "、".join([length_desc.get(l, f"{l}位") for l in acceptable_lengths])
        errors.append(
            f"{interval} 周期的 {field_name} 必须为 {acceptable_desc}，当前输入: {date_str} ({length}位)"
        )

    return errors


def convert_date_string_to_int(
    date_str: str, interval: str, is_end_date: bool = False
) -> int:
    """将日期字符串转换为整数格式，根据周期类型决定精度.

    Args:
        date_str: 日期字符串
        interval: 周期类型
        is_end_date: 是否是结束日期，如果是则补全为周期最后一天，否则补全为第一天

    Returns:
        整数格式的日期
    """
    # 根据周期确定日期字符串的长度
    if interval == "year":
        # 年线：4位数字 (YYYY)
        date_str = date_str.zfill(4)
        year = int(date_str[:4])
        if is_end_date:
            # 结束日期：补全为该年的最后一天
            return year * 10000 + 1231  # YYYY1231
        else:
            # 开始日期：补全为该年的第一天
            return year * 10000 + 101  # YYYY0101
    elif interval in ("season", "month"):
        # 月线/季线：6位数字 (YYYYMM)
        date_str = date_str.zfill(6)
        year = int(date_str[:4])
        month = int(date_str[4:6])

        if is_end_date:
            # 结束日期：补全为该月的最后一天
            last_day = calendar.monthrange(year, month)[1]
            return year * 10000 + month * 100 + last_day  # YYYYMMDD
        else:
            # 开始日期：补全为该月的第一天
            return year * 10000 + month * 100 + 1  # YYYYMM01
    elif interval in ("day", "week"):
        # 日线/周线
        if len(date_str) == 4:
            # 4位数字：年份，补全为 YYYY0101 或 YYYY1231
            year = int(date_str[:4])
            if is_end_date:
                return year * 10000 + 1231  # YYYY1231
            else:
                return year * 10000 + 101  # YYYY0101
        elif len(date_str) == 6:
            # 6位数字：YYYYMM，补全为 YYYYMM01 或 YYYYMMDD(最后一天)
            year = int(date_str[:4])
            month = int(date_str[4:6])
            if is_end_date:
                last_day = calendar.monthrange(year, month)[1]
                return year * 10000 + month * 100 + last_day
            else:
                return year * 10000 + month * 100 + 1
        else:
            # 8位数字 (YYYYMMDD)
            date_str = date_str.zfill(8)
            return int(date_str[:8])
    elif interval in ("min60", "min120"):
        # 小时线：10位数字 (YYYYMMDDHH)
        date_str = date_str.zfill(10)
        if is_end_date:
            # 结束日期：补全为该小时的最后时刻
            return int(date_str[:10] + "5959")  # 补全为 YYYYMMDDHH5959
        else:
            # 开始日期：补全为该小时的开始时刻
            return int(date_str[:10] + "0000")  # 补全为 YYYYMMDDHH0000
    elif interval in ("min1", "min3", "min5", "min10", "min15", "min30"):
        # 分钟线：12位数字 (YYYYMMDDHHMM)
        date_str = date_str.zfill(12)
        return int(date_str[:12])
    else:
        # 默认按日线处理
        date_str = date_str.zfill(8)
        return int(date_str[:8])


def validate_start_end_by_interval(
    interval: str, start: Optional[str], end: Optional[str]
) -> tuple[Optional[str], Optional[str]]:
    """根据周期获取开始/结束日期（不截断）.

    注意：此函数不再执行隐式截断。日期精度校验由 validate_date_length_for_interval() 处理。
    不符合精度要求的输入会返回错误，而非被截断。

    Args:
        interval: 周期名称
        start: 开始时间字符串
        end: 结束时间字符串

    Returns:
        (start, end) 原值返回，不修改
    """
    # 不再截断，直接返回原值
    # 精度校验由 validate_date_length_for_interval() 在 validate_date_range() 中执行
    return start, end
