#!/usr/bin/env python3
"""
清理交易日历数据，将所有中国市场的数据统一为 SSE
"""

import logging
from sqlalchemy import and_
from galaxy_db_bridge.database.core.connection import db_manager
from galaxy_db_bridge.database.models.trading_calendar import TradingCalendar


def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )


def clear_and_unify_calendar():
    """清理并统一交易日历数据"""
    setup_logging()
    logger = logging.getLogger(__name__)

    # 初始化数据库
    logger.info("初始化数据库连接...")
    db_manager.initialize()

    session = db_manager.get_session()
    try:
        # 统计原始数据
        total_count = session.query(TradingCalendar).count()
        sse_count = (
            session.query(TradingCalendar)
            .filter(TradingCalendar.market == "SSE")
            .count()
        )
        szse_count = (
            session.query(TradingCalendar)
            .filter(TradingCalendar.market == "SZSE")
            .count()
        )
        bse_count = (
            session.query(TradingCalendar)
            .filter(TradingCalendar.market == "BSE")
            .count()
        )

        logger.info(f"清理前数据统计:")
        logger.info(f"  总记录数: {total_count}")
        logger.info(f"  SSE记录数: {sse_count}")
        logger.info(f"  SZSE记录数: {szse_count}")
        logger.info(f"  BSE记录数: {bse_count}")

        # 删除 SZSE 和 BSE 的数据（因为 A 股市场使用统一的日历）
        deleted_szse = (
            session.query(TradingCalendar)
            .filter(TradingCalendar.market == "SZSE")
            .delete()
        )
        deleted_bse = (
            session.query(TradingCalendar)
            .filter(TradingCalendar.market == "BSE")
            .delete()
        )

        # 删除旧格式的数据（包含 "SSE_" 前缀的记录）
        deleted_old_format = (
            session.query(TradingCalendar)
            .filter(TradingCalendar.market.like("SSE_%"))
            .delete()
        )

        logger.info(f"删除 {deleted_szse} 条 SZSE 记录")
        logger.info(f"删除 {deleted_bse} 条 BSE 记录")
        logger.info(f"删除 {deleted_old_format} 条旧格式记录（SSE_前缀）")

        # 确保提交更改
        session.commit()

        # 重新统计数据
        total_count_after = session.query(TradingCalendar).count()
        sse_count_after = (
            session.query(TradingCalendar)
            .filter(TradingCalendar.market == "SSE")
            .count()
        )

        logger.info(f"清理后数据统计:")
        logger.info(f"  总记录数: {total_count_after}")
        logger.info(f"  SSE记录数: {sse_count_after}")

        logger.info("交易日历数据清理和统一完成！")

    finally:
        session.close()


if __name__ == "__main__":
    clear_and_unify_calendar()
