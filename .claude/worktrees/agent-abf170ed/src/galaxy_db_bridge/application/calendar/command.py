"""交易日历同步命令."""

import argparse
import logging
from datetime import date
from galaxy_db_bridge.database.core.connection import db_manager
from galaxy_db_bridge.database.services.trading_calendar import trading_calendar_service

logger = logging.getLogger(__name__)


def create_calendar_parser(subparsers):
    """创建交易日历命令解析器."""
    parser = subparsers.add_parser(
        "calendar", help="同步交易日历数据，包括交易日和非交易日"
    )

    # 添加起始年份参数，默认为2010
    parser.add_argument(
        "--start-year", type=int, default=2010, help="起始年份 (默认: 2010)"
    )

    # 添加结束年份参数，默认为当前年份
    parser.add_argument(
        "--end-year",
        type=int,
        default=date.today().year,
        help=f"结束年份 (默认: {date.today().year})",
    )

    return parser


def validate_years(start_year: int, end_year: int) -> bool:
    """验证年份参数."""
    current_year = date.today().year

    # 检查年份范围是否合理
    if start_year < 1990 or start_year > current_year:
        logger.error(f"起始年份 {start_year} 不在合理范围内 (1990-{current_year})")
        return False

    if end_year < 1990 or end_year > current_year + 10:
        logger.error(f"结束年份 {end_year} 不在合理范围内 (1990-{current_year + 10})")
        return False

    if start_year > end_year:
        logger.error(f"起始年份 {start_year} 不能大于结束年份 {end_year}")
        return False

    return True


def handle_calendar_command(args) -> int:
    """处理交易日历命令."""
    logger.info(f"开始处理交易日历同步命令")
    logger.info(f"参数: start_year={args.start_year}, end_year={args.end_year}")

    # 验证参数
    if not validate_years(args.start_year, args.end_year):
        return 1

    try:
        # 初始化数据库连接
        logger.info("初始化数据库连接...")
        db_manager.initialize()

        logger.info(f"开始同步 {args.start_year} 年到 {args.end_year} 年的交易日历数据")

        # 逐年同步数据
        success_count = 0
        for year in range(args.start_year, args.end_year + 1):
            logger.info(f"正在同步 {year} 年数据...")
            count = trading_calendar_service.sync_calendar(year, "SSE")
            logger.info(f"{year} 年同步完成，共 {count} 个交易日")
            success_count += 1

        logger.info(f"交易日历同步完成！成功同步 {success_count} 年数据")
        return 0

    except Exception as e:
        logger.error(f"同步交易日历时发生错误: {e}")
        return 1
