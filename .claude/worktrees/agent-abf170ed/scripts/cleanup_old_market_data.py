#!/usr/bin/env python3
"""
清理旧格式的市场数据，只保留新格式（SSE_上海证券交易所）
"""

import logging
from galaxy_db_bridge.database.core.connection import db_manager
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def cleanup_old_market_data():
    """清理旧格式的市场数据"""
    # 初始化数据库
    db_manager.initialize()

    with db_manager.session() as session:
        # 检查旧格式数据
        result = session.execute(
            text("SELECT COUNT(*) FROM trading_calendar WHERE market = 'SSE'")
        )
        old_count = result.scalar()
        logger.info(f"发现 {old_count} 条旧格式 SSE 记录")

        # 检查新格式数据
        result = session.execute(
            text(
                "SELECT COUNT(*) FROM trading_calendar WHERE market = 'SSE_上海证券交易所'"
            )
        )
        new_count = result.scalar()
        logger.info(f"发现 {new_count} 条新格式 SSE_上海证券交易所 记录")

        if old_count > 0:
            # 删除旧格式数据
            result = session.execute(
                text("DELETE FROM trading_calendar WHERE market = 'SSE'")
            )
            logger.info(f"已删除 {result.rowcount} 条旧格式 SSE 记录")

        # 验证清理结果
        result = session.execute(
            text("SELECT COUNT(*) FROM trading_calendar WHERE market = 'SSE'")
        )
        remaining = result.scalar()
        logger.info(f"清理后剩余 {remaining} 条旧格式 SSE 记录")

        # 显示最终统计
        result = session.execute(text("SELECT market, COUNT(*) FROM trading_calendar GROUP BY market"))
        logger.info("最终市场分布:")
        for row in result:
            logger.info(f"  {row[0]}: {row[1]} 条记录")


if __name__ == "__main__":
    cleanup_old_market_data()
