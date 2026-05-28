#!/usr/bin/env python3
"""清理交易日历数据。"""

import logging

from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.models.trading_calendar import TradingCalendar


def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )


def clear_and_unify_calendar():
    """清理交易日历数据。"""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("初始化数据库连接...")
    db_manager.initialize()

    session = db_manager.get_session()
    try:
        total_count = session.query(TradingCalendar).count()
        logger.info("清理前数据统计:")
        logger.info(f"  总记录数: {total_count}")

        deleted_count = session.query(TradingCalendar).delete()
        session.commit()

        total_count_after = session.query(TradingCalendar).count()
        logger.info(f"已删除 {deleted_count} 条交易日历记录")
        logger.info("清理后数据统计:")
        logger.info(f"  总记录数: {total_count_after}")
        logger.info("交易日历数据清理完成！")
    finally:
        session.close()


if __name__ == "__main__":
    clear_and_unify_calendar()
