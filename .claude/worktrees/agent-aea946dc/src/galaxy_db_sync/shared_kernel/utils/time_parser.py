import argparse
import logging
from datetime import date, datetime, timedelta

import pandas as pd

from galaxy_db_sync.amazing_data.api.client import amazing_data_client
from galaxy_db_sync.shared_kernel.enums.security_type import (
    SecurityType,
    SecurityTypeFuture,
    SecurityTypeOption,
)

logger = logging.getLogger(__name__)


DEFAULT_START_DATE_BY_SECURITY_TYPE = {
    SecurityType.SH_A.value: "20130101",
    SecurityType.SZ_A.value: "20130101",
    SecurityType.BJ_A.value: "20130101",
    SecurityType.EXTRA_STOCK_A.value: "20130101",
    SecurityType.EXTRA_STOCK_A_SH_SZ.value: "20130101",
    SecurityType.SH_INDEX.value: "20130101",
    SecurityType.SZ_INDEX.value: "20130101",
    SecurityType.BJ_INDEX.value: "20130101",
    SecurityType.EXTRA_INDEX_A.value: "20130101",
    SecurityType.EXTRA_INDEX_A_SH_SZ.value: "20130101",
    SecurityType.SH_ETF.value: "20130101",
    SecurityType.SZ_ETF.value: "20130101",
    SecurityType.EXTRA_ETF.value: "20130101",
    SecurityType.SH_KZZ.value: "20130101",
    SecurityType.SZ_KZZ.value: "20130101",
    SecurityType.EXTRA_KZZ.value: "20130101",
    SecurityTypeOption.SH_OPTION.value: "20150101",
    SecurityTypeOption.SZ_OPTION.value: "20150101",
    SecurityTypeOption.EXTRA_ETF_OP.value: "20150101",
    SecurityType.SH_HKT.value: "20230101",
    SecurityType.SZ_HKT.value: "20230101",
    SecurityType.EXTRA_HKT.value: "20230101",
    SecurityTypeFuture.ZJ_FUTURE.value: "20100401",
    SecurityTypeFuture.DS_FUTURE.value: "20130601",
    SecurityTypeFuture.ZS_FUTURE.value: "20110101",
    SecurityTypeFuture.SQ_FUTURE.value: "20190801",
    SecurityTypeFuture.SN_FUTURE.value: "20190801",
    SecurityTypeFuture.EXTRA_FUTURE.value: "20100401",
}


# =====================================================================
# 日期转换工具函数
# =====================================================================


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


# =====================================================================
# 交易日历和上市日期
# =====================================================================


def get_default_dates() -> tuple[str, str]:
    """获取默认的起止日期."""
    calendar = amazing_data_client.get_trading_calendar(data_type="int")
    if not calendar:
        today = datetime.now().strftime("%Y%m%d")
        return "20130101", today

    begin_date = min(calendar)  # 最早的交易日
    end_date = max(calendar)  # 最新的交易日
    return str(begin_date), str(end_date)


def get_default_start_date_for_symbol(symbol: str) -> str:
    """根据证券类型返回单个 symbol 的默认起始日期（8 位 YYYYMMDD 格式）."""
    from galaxy_db_sync.shared_kernel.utils import infer_security_type

    security_type = infer_security_type(symbol)
    if security_type is None:
        raise ValueError(f"无法推断证券类型，无法为 {symbol} 计算默认开始日期")

    default_start = DEFAULT_START_DATE_BY_SECURITY_TYPE.get(security_type)
    if default_start is None:
        raise ValueError(
            f"证券类型 {security_type} 缺少默认开始日期映射，symbol={symbol}"
        )

    return default_start


def resolve_default_start_date(symbols: list[str], start: str | None) -> str | None:
    """在 start 缺失时，根据 symbol 列表推导请求级默认开始日期（8 位 YYYYMMDD 格式）.

    对多 symbol 请求，返回各 symbol 默认开始日期中的最大值。
    """
    if start is not None:
        return start

    if not symbols:
        return start

    return max(get_default_start_date_for_symbol(symbol) for symbol in symbols)


def resolve_default_start_date_for_interval(
    symbols: list[str], interval: str, start: str | None
) -> str | None:
    """在 start 缺失时，根据 symbol 列表和周期推导正确精度的默认开始日期.

    根据 CON-005 约束，系统推导的默认日期在生成时就使用正确精度，而非事后截断。

    Args:
        symbols: 证券代码列表
        interval: 周期类型
        start: 用户显式输入的开始日期

    Returns:
        正确精度的默认开始日期，或用户显式输入值（不修改）
    """
    if start is not None:
        # 用户显式输入，不修改（精度校验由其他函数处理）
        return start

    if not symbols:
        return start

    # 获取 8 位 YYYYMMDD 格式的默认日期
    base_date = max(get_default_start_date_for_symbol(symbol) for symbol in symbols)

    # 根据周期转换为正确精度
    if interval == "year":
        return base_date[:4]  # YYYY
    elif interval in ("season", "month"):
        return base_date[:6]  # YYYYMM
    else:
        # day, week, min60, min120, 分钟线: 保持 8 位 YYYYMMDD
        return base_date


def resolve_default_end_date_for_interval(
    interval: str, end: str | None, reference_date: date | None = None
) -> str | None:
    """在 end 缺失时，根据周期推导正确精度的默认结束日期.

    根据 CON-005 约束，系统推导的默认日期在生成时就使用正确精度。
    根据 CON-006 约束，此函数返回原始精度日期，补全由 pad_date_to_full_format() 处理。

    Args:
        interval: 周期类型
        end: 用户显式输入的结束日期
        reference_date: 参考日期，用于计算长周期边界（默认为今天）

    Returns:
        正确精度的默认结束日期，或用户显式输入值（不修改）
    """
    from galaxy_db_sync.shared_kernel.utils.interval_boundary_checker import (
        IntervalBoundaryChecker,
    )
    from galaxy_db_sync.shared_kernel.enums.interval import Interval

    if end is not None:
        # 用户显式输入，不修改
        return end

    # 确定参考日期
    if reference_date is None:
        reference_date = date.today()

    interval_enum = Interval(interval)

    # 长周期：使用最后一个已结束周期的结束日期
    if interval_enum in {Interval.WEEK, Interval.MONTH, Interval.SEASON, Interval.YEAR}:
        boundary_checker = IntervalBoundaryChecker()
        last_complete_end = boundary_checker.get_last_complete_interval_end(
            interval_enum, reference_date
        )
        full_date = last_complete_end.strftime("%Y%m%d")  # 8 位
    else:
        # 短周期：默认昨天
        yesterday = reference_date - timedelta(days=1)
        full_date = yesterday.strftime("%Y%m%d")  # 8 位

    # 根据周期转换为正确精度（与 CON-005 保持一致）
    if interval == "year":
        return full_date[:4]  # YYYY
    elif interval in ("season", "month"):
        return full_date[:6]  # YYYYMM
    else:
        # day, week, min60, min120, 分钟线: 保持 8 位 YYYYMMDD
        return full_date


def pad_date_to_full_format(date_str: str | None, interval: str, is_end: bool = False) -> str | None:
    """将原始精度日期补全为完整 8 位 YYYYMMDD 格式.

    根据 CON-006 约束，精度校验通过后才调用此函数补全。
    补全后的日期用于数据库服务和 API 调用。

    Args:
        date_str: 原始精度日期字符串
        interval: 周期类型
        is_end: 是否为结束日期（影响补全方向）

    Returns:
        8 位 YYYYMMDD 格式的完整日期，或 None（输入为 None 时）
    """
    import calendar

    if date_str is None:
        return None

    length = len(date_str)

    if interval == "year":
        # 4 位 YYYY → 补全为 YYYY0101 或 YYYY1231
        year = int(date_str[:4])
        if is_end:
            return f"{year}1231"
        else:
            return f"{year}0101"

    elif interval in ("season", "month"):
        # 4 位或 6 位 → 补全
        if length == 4:
            year = int(date_str[:4])
            if is_end:
                return f"{year}1231"
            else:
                return f"{year}0101"
        else:  # 6 位 YYYYMM
            year = int(date_str[:4])
            month = int(date_str[4:6])
            if is_end:
                last_day = calendar.monthrange(year, month)[1]
                return f"{year}{month:02d}{last_day:02d}"
            else:
                return f"{year}{month:02d}01"

    else:
        # day, week, min60, min120, 分钟线
        if length == 4:
            # 4位年份：补全为 YYYY0101 或 YYYY1231
            year = int(date_str[:4])
            if is_end:
                return f"{year}1231"
            else:
                return f"{year}0101"
        elif length == 6:
            # 6位 YYYYMM：补全为 YYYYMM01 或 YYYYMMDD(最后一天)
            year = int(date_str[:4])
            month = int(date_str[4:6])
            if is_end:
                last_day = calendar.monthrange(year, month)[1]
                return f"{year}{month:02d}{last_day:02d}"
            else:
                return f"{year}{month:02d}01"
        else:
            # 8位及以上：截取前8位
            return date_str[:8] if len(date_str) >= 8 else date_str.zfill(8)


def get_listing_date(symbol: str) -> str:
    """获取证券的上市日期."""
    try:
        # 尝试从股票列表获取信息
        stock_info = amazing_data_client.get_stock_list()
        if "code" in stock_info.columns:
            match = stock_info[stock_info["code"] == symbol]
        elif "symbol" in stock_info.columns:
            match = stock_info[stock_info["symbol"] == symbol]
        else:
            match = stock_info[stock_info.iloc[:, 0] == symbol]

        if not match.empty and "list_date" in match.columns:
            list_date = match.iloc[0]["list_date"]
            if pd.notna(list_date):
                # 转换为 YYYYMMDD 格式
                if isinstance(list_date, str):
                    return list_date.replace("-", "").replace("/", "")[:8]
                elif isinstance(list_date, datetime):
                    return list_date.strftime("%Y%m%d")
    except Exception as e:
        logger.warning(f"无法获取 {symbol} 的上市日期: {e}")

    # 默认返回一个较早的日期
    return "20130101"


def validate_start_end_by_interval(
    interval: str, start: str | None, end: str | None
) -> tuple[str | None, str | None]:
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


def validate_date_length_for_interval(date_str: str, interval: str, field_name: str = "日期") -> list[str]:
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


def validate_date_range(start: str | None, end: str | None, interval: str) -> list[str]:
    """验证日期范围是否合法.

    Args:
        start: 开始日期
        end: 结束日期
        interval: 周期类型

    Returns:
        错误信息列表
    """
    errors = []

    # 先校验日期精度
    if start:
        errors.extend(validate_date_length_for_interval(start, interval, "开始日期"))
    if end:
        errors.extend(validate_date_length_for_interval(end, interval, "结束日期"))

    if start is None or end is None:
        return errors

    # 根据周期将日期字符串转换为整数进行比较
    start_int = convert_date_string_to_int(start, interval, is_end_date=False)
    end_int = convert_date_string_to_int(end, interval, is_end_date=True)

    # 检查 start 是否晚于 end
    if start_int > end_int:
        errors.append(f"开始日期 ({start}) 晚于结束日期 ({end})")

    # 检查日期是否晚于当前时间
    # 对于长周期（年、季、月、周），使用最后一个已结束周期的结束日期作为边界
    from galaxy_db_sync.shared_kernel.enums.interval import Interval
    from galaxy_db_sync.shared_kernel.utils.interval_boundary_checker import (
        IntervalBoundaryChecker,
    )

    long_intervals = {"year", "season", "month", "week"}

    if interval in long_intervals:
        # 长周期：使用 IntervalBoundaryChecker 获取最后一个已结束周期的结束日期
        try:
            checker = IntervalBoundaryChecker()
            interval_enum = Interval(interval)
            last_complete_end = checker.get_last_complete_interval_end(interval_enum)
            # 将最后一个已结束周期的结束日期转换为与 end_int 相同格式的整数
            # 根据周期类型截断日期字符串，然后使用 convert_date_string_to_int 统一转换
            boundary_str = last_complete_end.strftime("%Y%m%d")
            if interval == "year":
                boundary_str = boundary_str[:4]
            elif interval in ("season", "month"):
                boundary_str = boundary_str[:6]
            # 对于日线/周线，保持8位
            boundary_int = convert_date_string_to_int(boundary_str, interval, is_end_date=True)
        except Exception:
            # 如果获取失败，回退到使用当前日期
            boundary_int = convert_date_string_to_int(
                datetime.now().strftime("%Y%m%d"), interval, is_end_date=False
            )
    else:
        # 短周期（日、小时、分钟）：使用当前日期作为边界
        boundary_int = convert_date_string_to_int(
            datetime.now().strftime("%Y%m%d"), interval, is_end_date=False
        )

    if start_int > boundary_int:
        errors.append(f"开始日期 ({start}) 晚于当前时间")
    if end_int > boundary_int:
        errors.append(f"结束日期 ({end}) 晚于当前时间")

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
    from datetime import datetime
    import calendar

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


def parse_date_to_datetime(date_str: str, interval: str) -> datetime:
    """将日期字符串解析为 datetime 对象.

    Args:
        date_str: 日期字符串
        interval: 周期类型，用于确定日期格式

    Returns:
        datetime 对象
    """
    if interval == "year":
        # 年线：4位数字 (YYYY) 或 6位数字 (YYYYMM)
        if len(date_str) == 4:
            return datetime.strptime(date_str + "01", "%Y%m%d")  # 补全为 YYYY01
        elif len(date_str) >= 6:
            date_part = date_str[:6]  # 取前6位 YYYYMM
            # 根据月份确定最后一天
            year = int(date_part[:4])
            month = int(date_part[4:6])
            if month in [1, 3, 5, 7, 8, 10, 12]:
                day = "31"
            elif month in [4, 6, 9, 11]:
                day = "30"
            else:  # 2月
                if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
                    day = "29"
                else:
                    day = "28"
            return datetime.strptime(date_part + day, "%Y%m%d")
        else:
            return datetime.strptime(date_str.zfill(8)[:8], "%Y%m%d")
    elif interval in ["season", "month"]:
        # 月线/季线：处理不同长度的日期输入
        if len(date_str) == 4:
            # 4位数字：年份，补全为 YYYY0101
            return datetime.strptime(date_str + "0101", "%Y%m%d")
        elif len(date_str) >= 6:
            date_part = date_str[:6]  # 取前6位 YYYYMM
            # 根据月份确定最后一天
            year = int(date_part[:4])
            month = int(date_part[4:6])
            if month in [1, 3, 5, 7, 8, 10, 12]:
                day = "31"
            elif month in [4, 6, 9, 11]:
                day = "30"
            else:  # 2月
                if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
                    day = "29"
                else:
                    day = "28"
            return datetime.strptime(date_part + day, "%Y%m%d")
        else:
            return datetime.strptime(date_str.zfill(8)[:8], "%Y%m%d")
    else:
        # 日线/周线/分钟线：处理不同长度的日期输入
        if len(date_str) == 4:
            # 4位数字：年份，补全为 YYYY0101
            return datetime.strptime(date_str + "0101", "%Y%m%d")
        elif len(date_str) == 6:
            # 6位数字：YYYYMM，补全为 YYYYMM01
            year = int(date_str[:4])
            month = int(date_str[4:6])
            return datetime.strptime(date_str + "01", "%Y%m%d")
        else:
            # 8位及以上：直接解析
            return datetime.strptime(date_str.zfill(8)[:8], "%Y%m%d")


def parse_time_arg(value: str, is_end: bool = False) -> str:
    """
    智能解析时间参数：
    - 4 位数字 → 年份（年线场景）: 2024
    - 6 位数字 → 年月（季月线场景）: 202401 或 240101
    - 8 位数字 → 日期（日线场景）: 20240101
    - 10 位数字 → 日期+小时（小时线场景）: 2024010109
    - 12 位数字 → 日期+时分（分钟线场景）: 202401010930
    - "today"/"yesterday" → 动态日期
    """
    # 处理关键词
    if value.lower() == "today":
        return datetime.now().strftime("%Y%m%d")
    if value.lower() == "yesterday":
        return (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    # 纯数字处理
    if value.isdigit():
        if len(value) == 4:
            # 4位数字：年份 (YYYY)
            return value
        elif len(value) == 6:
            # 6位数字：年月 (YYYYMM 或 YYMMDD)
            # 统一转为 YYYYMM 格式
            if int(value[:2]) < 50:
                # YYMMDD 格式，转为 YYYYMM
                return "20" + value[:4]
            else:
                # 已经是 YYYYMM 格式
                return value
        elif len(value) == 8:
            # 8位数字：日期 (YYYYMMDD)
            return value
        elif len(value) == 10:
            # 10位数字：日期+小时 (YYYYMMDDHH)
            return value
        elif len(value) == 12:
            # 12位数字：日期+时分 (YYYYMMDDHHMM)
            return value
        else:
            raise argparse.ArgumentTypeError(
                f"Invalid digit length: '{value}'\n"
                "✓ Year: 4-digit (2024)\n"
                "✓ Month/Season: 6-digit (202401)\n"
                "✓ Date: 8-digit (20240101)\n"
                "✓ Hour: 10-digit (2024010109)\n"
                "✓ Minute: 12-digit (202401010930)"
            )

    # 尝试解析标准时间字符串（2024-01-01 09:30:00）
    try:
        dt = datetime.fromisoformat(value.replace(" ", "T"))
        # 根据是否含时间决定返回格式
        if dt.hour == 0 and dt.minute == 0 and not is_end:
            return dt.strftime("%Y%m%d")  # 无时间部分 → 日期
        return dt.strftime("%Y%m%d%H%M%S")[:14]  # 保留到秒
    except:
        raise argparse.ArgumentTypeError(
            f"Unrecognized time format: '{value}'\n"
            "Examples: 2024, 202401, 20240101, 2024010109, 202401010930, '2024-01-01 14:30'"
        )
