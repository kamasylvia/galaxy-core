import argparse
import logging
from datetime import datetime, timedelta

import pandas as pd

from galaxy_db_bridge.amazing_data.api.client import amazing_data_client
from galaxy_db_bridge.shared_kernel.enums.security_type import (
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
    """根据证券类型返回单个 symbol 的默认起始日期."""
    from galaxy_db_bridge.shared_kernel.utils.symbol_validator import infer_security_type

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
    """在 start 缺失时，根据 symbol 列表推导请求级默认开始日期.

    对多 symbol 请求，返回各 symbol 默认开始日期中的最大值。
    """
    if start is not None:
        return start

    if not symbols:
        return start

    return max(get_default_start_date_for_symbol(symbol) for symbol in symbols)


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


def validate_start_end_by_period(
    interval: str, start: str | None, end: str | None
) -> tuple[str | None, str | None]:
    """根据周期验证并调整开始/结束日期格式.

    不同周期支持的数字位数：
    - 年线(year): 4位数字 (YYYY)
    - 季线(season)/月线(month): 6位数字 (YYYYMM)
    - 日线(day)/周线(week): 8位数字 (YYYYMMDD)
    - 小时线(min60)/两小时线(min120): 10位数字 (YYYYMMDDHH)
    - 分钟线(min1/min3/min5/min10/min15/min30): 12位数字 (YYYYMMDDHHMM)

    Args:
        interval: 周期名称
        start: 开始时间字符串
        end: 结束时间字符串

    Returns:
        调整后的 (start, end)
    """

    def adjust_format(value: str | None, length: int) -> str | None:
        if value is None:
            return None
        # 如果长度超过要求，截断
        if len(value) > length:
            return value[:length]
        return value

    # 年线: 4位 (YYYY)
    if interval == "year":
        return adjust_format(start, 4), adjust_format(end, 4)
    # 季线/月线: 6位 (YYYYMM)
    elif interval in ("season", "month"):
        return adjust_format(start, 6), adjust_format(end, 6)
    # 日线/周线: 8位 (YYYYMMDD)
    elif interval in ("day", "week"):
        return adjust_format(start, 8), adjust_format(end, 8)
    # 小时线/两小时线: 10位 (YYYYMMDDHH)
    elif interval in ("min60", "min120"):
        return adjust_format(start, 10), adjust_format(end, 10)
    # 分钟线: 12位 (YYYYMMDDHHMM)
    elif interval in ("min1", "min3", "min5", "min10", "min15", "min30"):
        return adjust_format(start, 12), adjust_format(end, 12)

    return start, end


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

    if start is None or end is None:
        return errors

    # 根据周期将日期字符串转换为整数进行比较
    start_int = convert_date_string_to_int(start, interval, is_end_date=False)
    end_int = convert_date_string_to_int(end, interval, is_end_date=True)

    # 检查 start 是否晚于 end
    if start_int > end_int:
        errors.append(f"开始日期 ({start}) 晚于结束日期 ({end})")

    # 检查日期是否晚于当前时间
    current_int = convert_date_string_to_int(
        datetime.now().strftime("%Y%m%d"), interval, is_end_date=False
    )
    if start_int > current_int:
        errors.append(f"开始日期 ({start}) 晚于当前时间")
    if end_int > current_int:
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
        # 日线/周线：8位数字 (YYYYMMDD)
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
        # 月线/季线：6位数字 (YYYYMM) 或 8位数字 (YYYYMMDD)
        if len(date_str) >= 6:
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
        # 日线及以上：8位数字 (YYYYMMDD)
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
