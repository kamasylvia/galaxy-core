#!/usr/bin/env python3
"""检查交易日历数据同步情况。"""

import logging
from sqlalchemy import func

from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.models.trading_calendar import TradingCalendar


def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )


def check_data():
    """检查数据库中的交易日历数据"""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("初始化数据库连接...")
    db_manager.initialize()

    session = db_manager.get_session()
    try:
        total_count = session.query(func.count(TradingCalendar.id)).scalar()
        logger.info(f"数据库中总共有 {total_count} 条交易日历记录")

        yearly_counts = (
            session.query(TradingCalendar.year, func.count(TradingCalendar.id))
            .group_by(TradingCalendar.year)
            .order_by(TradingCalendar.year)
            .all()
        )

        logger.info("各年份数据统计:")
        for year, count in yearly_counts:
            logger.info(f"  {year}年: {count} 条记录")

        min_date = session.query(func.min(TradingCalendar.trade_date)).scalar()
        max_date = session.query(func.max(TradingCalendar.trade_date)).scalar()

        if min_date and max_date:
            logger.info(f"日期范围: {min_date} 到 {max_date}")

        logger.info("数据检查完成")
    finally:
        session.close()


if __name__ == "__main__":
    check_data()
