"""K 线命令参数解析模块."""

import AmazingData as ad
from enum import Enum
from typing import Any


class IntervalOption(Enum):
    """数据周期枚举 - 用于命令行界面."""

    MIN1 = "min1"
    MIN3 = "min3"
    MIN5 = "min5"
    MIN10 = "min10"
    MIN15 = "min15"
    MIN30 = "min30"
    MIN60 = "min60"
    MIN120 = "min120"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    SEASON = "season"
    YEAR = "year"


def get_sdk_interval_value(interval_option: IntervalOption) -> int:
    """获取 AmazingData SDK 中真实的 interval 值.

    Args:
        interval_option: IntervalOption 枚举值

    Returns:
        SDK Period 常量的整数值

    Raises:
        RuntimeError: SDK constants unavailable
    """
    if not hasattr(ad, "constant"):
        raise RuntimeError("AmazingData SDK constants are unavailable: missing ad.constant")

    if not hasattr(ad.constant, "Period"):
        raise RuntimeError("AmazingData SDK constants are unavailable: missing ad.constant.Period")

    sdk_period = ad.constant.Period
    required_members = {
        IntervalOption.MIN1: "min1",
        IntervalOption.MIN3: "min3",
        IntervalOption.MIN5: "min5",
        IntervalOption.MIN10: "min10",
        IntervalOption.MIN15: "min15",
        IntervalOption.MIN30: "min30",
        IntervalOption.MIN60: "min60",
        IntervalOption.MIN120: "min120",
        IntervalOption.DAY: "day",
        IntervalOption.WEEK: "week",
        IntervalOption.MONTH: "month",
        IntervalOption.SEASON: "season",
        IntervalOption.YEAR: "year",
    }

    if interval_option not in required_members:
        raise RuntimeError(f"Unsupported interval option: {interval_option}")

    member_name = required_members[interval_option]
    if not hasattr(sdk_period, member_name):
        raise RuntimeError(
            f"AmazingData SDK constants are unavailable: missing ad.constant.Period.{member_name}"
        )

    return getattr(sdk_period, member_name).value


def create_kline_parser(subparsers: Any) -> Any:
    """创建 kline subparser.

    Args:
        subparsers: argparse subparsers 对象

    Returns:
        配置好的 kline parser
    """
    kline_parser = subparsers.add_parser(
        "kline",
        help="获取 K 线数据并存入数据库",
        description="获取指定证券的 K 线数据，支持单代码、代码列表、SecurityType 或混合列表。"
        "数据自动存入数据库，增量获取缺失数据。",
    )

    # 必选参数: symbols
    kline_parser.add_argument(
        "symbols",
        type=str,
        help="证券代码，支持：\n"
        '- 单代码: "600000.SH"\n'
        '- 代码列表: "[600000.SH, 000001.SZ]" 或 "600000.SH,000001.SZ"\n'
        '- SecurityType: "SH_A", "SZ_ETF", "EXTRA_STOCK_A" 等\n'
        '- 混合列表: "[600000.SH, SH_ETF]"',
    )

    # 可选参数: interval
    interval_choices = [p.name.lower() for p in IntervalOption]
    kline_parser.add_argument(
        "--interval",
        choices=interval_choices,
        default="day",
        help=f"K 线周期，默认为 day。可选值: {', '.join(interval_choices)}",
    )

    # 可选参数: start
    kline_parser.add_argument(
        "--start",
        default=None,
        help="开始日期/时间。\n"
        "- 年线: 4 位数字 (YYYY)\n"
        "- 季线/月线: 6 位数字 (YYYYMM)\n"
        "- 日线/周线: 8 位数字 (YYYYMMDD)\n"
        "- 小时/两小时线: 10 位数字 (YYYYMMDDHH)\n"
        "- 分钟线: 12 位数字 (YYYYMMDDHHMM)\n"
        "默认按证券类型使用 AmazingData 数据起点。",
    )

    # 可选参数: end
    kline_parser.add_argument(
        "--end",
        default=None,
        help="结束日期/时间。\n"
        "- 年线: 4 位数字 (YYYY)\n"
        "- 季线/月线: 6 位数字 (YYYYMM)\n"
        "- 日线/周线: 8 位数字 (YYYYMMDD)\n"
        "- 小时/两小时线: 10 位数字 (YYYYMMDDHH)\n"
        "- 分钟线: 12 位数字 (YYYYMMDDHHMM)\n"
        "默认为昨天。",
    )

    return kline_parser