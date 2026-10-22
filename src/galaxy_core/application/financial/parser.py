"""财务数据命令参数解析模块."""

from typing import Any


def create_financial_parser(subparsers: Any) -> Any:
    """创建 financial subparser.

    Args:
        subparsers: argparse subparsers 对象

    Returns:
        配置好的 financial parser
    """
    parser = subparsers.add_parser(
        "financial",
        help="同步财务数据（资产负债表、现金流量表、利润表、业绩快报、业绩预告）",
        description="获取 A 股财务数据并存入数据库，支持增量同步和全量刷新。",
    )

    parser.add_argument(
        "--type",
        required=True,
        choices=[
            "balance_sheet",
            "cash_flow",
            "income",
            "profit_express",
            "profit_notice",
            "dividend",
        ],
        help="财务数据类型",
    )

    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="证券代码（如 600000.SH），省略则同步全部 A 股",
    )

    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="报告期开始日期 (YYYYMMDD)，省略则按增量/全量推导",
    )

    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="报告期结束日期 (YYYYMMDD)，省略则为 T-1（昨天）",
    )

    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="全量刷新标志，覆盖最近 3 年数据",
    )

    return parser
