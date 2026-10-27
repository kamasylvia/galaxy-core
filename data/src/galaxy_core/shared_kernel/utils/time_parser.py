import argparse
import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Optional

import pandas as pd

from galaxy_core.shared_kernel.enums.security_type import (
    SecurityType,
    SecurityTypeFuture,
    SecurityTypeOption,
)

# 向后兼容 re-export — 纯函数已移至 domain.date_range.parser
from galaxy_core.domain.date_range.parser import (
    parse_date_to_int,
    int_to_datetime,
    datetime_to_int,
    expand_date_to_full,
    validate_date_length_for_interval,
    convert_date_string_to_int,
    validate_start_end_by_interval,
)

if TYPE_CHECKING:
    from galaxy_core.amazing_data.api.client import AmazingDataClient
    from galaxy_core.shared_kernel.utils.interval_boundary_checker import TradingCalendarProtocol

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
# 交易日历和上市日期（基础设施函数，保留在原位）
# =====================================================================


def get_default_dates(client: "AmazingDataClient") -> tuple[str, str]:
    """获取默认的起止日期."""
    calendar = client.get_trading_calendar(data_type="int")
    if not calendar:
        today = datetime.now().strftime("%Y%m%d")
        return "20130101", today

    begin_date = min(calendar)  # 最早的交易日
    end_date = max(calendar)  # 最新的交易日
    return str(begin_date), str(end_date)


def get_default_start_date_for_symbol(symbol: str) -> str:
    """根据证券类型返回单个 symbol 的默认起始日期（8 位 YYYYMMDD 格式）."""
    from galaxy_core.shared_kernel.utils import infer_security_type

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


async def resolve_default_end_date_for_interval(
    interval: str,
    end: str | None,
    reference_date: date | None = None,
    trading_calendar: Optional["TradingCalendarProtocol"] = None,
) -> str | None:
    """在 end 缺失时，根据周期推导正确精度的默认结束日期.

    根据 CON-005 约束，系统推导的默认日期在生成时就使用正确精度。
    根据 CON-006 约束，此函数返回原始精度日期，补全由 expand_date_to_full() 处理。

    Args:
        interval: 周期类型
        end: 用户显式输入的结束日期
        reference_date: 参考日期，用于计算长周期边界（默认为今天）
        trading_calendar: 交易日历实例（通过 DI 注入）

    Returns:
        正确精度的默认结束日期，或用户显式输入值（不修改）
    """
    from galaxy_core.shared_kernel.utils.interval_boundary_checker import (
        IntervalBoundaryChecker,
    )
    from galaxy_core.shared_kernel.enums.interval import Interval

    if end is not None:
        # 用户显式输入，不修改
        return end

    # 确定参考日期
    if reference_date is None:
        reference_date = date.today()

    interval_enum = Interval(interval)

    # 长周期：使用最后一个已结束周期的结束日期
    if interval_enum in {Interval.WEEK, Interval.MONTH, Interval.SEASON, Interval.YEAR}:
        if trading_calendar is None:
            raise ValueError(
                "长周期边界计算需要 trading_calendar 参数，请通过 DI 容器注入"
            )
        boundary_checker = IntervalBoundaryChecker(trading_calendar=trading_calendar)
        last_complete_end = await boundary_checker.get_last_complete_interval_end_async(
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


def get_listing_date(symbol: str, client: "AmazingDataClient") -> str:
    """获取证券的上市日期."""
    try:
        # 尝试从股票列表获取信息
        stock_info = client.get_stock_list()
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


async def validate_date_range(
    start: str | None,
    end: str | None,
    interval: str,
    trading_calendar: Optional["TradingCalendarProtocol"] = None,
) -> list[str]:
    """验证日期范围是否合法.

    Args:
        start: 开始日期
        end: 结束日期
        interval: 周期类型
        trading_calendar: 交易日历实例（通过 DI 注入）

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
    from galaxy_core.shared_kernel.enums.interval import Interval
    from galaxy_core.shared_kernel.utils.interval_boundary_checker import (
        IntervalBoundaryChecker,
    )

    long_intervals = {"year", "season", "month", "week"}

    if interval in long_intervals:
        # 长周期：使用 IntervalBoundaryChecker 获取最后一个已结束周期的结束日期
        try:
            if trading_calendar is None:
                raise ValueError(
                    "长周期边界计算需要 trading_calendar 参数，请通过 DI 容器注入"
                )
            checker = IntervalBoundaryChecker(trading_calendar=trading_calendar)
            interval_enum = Interval(interval)
            last_complete_end = await checker.get_last_complete_interval_end_async(interval_enum)
            # 将最后一个已结束周期的结束日期转换为与 end_int 相同格式的整数
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
                "Year: 4-digit (2024)\n"
                "Month/Season: 6-digit (202401)\n"
                "Date: 8-digit (20240101)\n"
                "Hour: 10-digit (2024010109)\n"
                "Minute: 12-digit (202401010930)"
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
