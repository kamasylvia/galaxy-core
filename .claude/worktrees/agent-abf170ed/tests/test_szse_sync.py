#!/usr/bin/env python3
"""
测试同步 SZSE 交易日历是否会保存为 SSE，并验证 trade_date 唯一性
"""

import logging
from datetime import date
from sqlalchemy import func
from galaxy_db_bridge.database.core.connection import db_manager
from galaxy_db_bridge.database.services.trading_calendar import trading_calendar_service
from galaxy_db_bridge.database.models.trading_calendar import TradingCalendar


def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )


def test_szse_sync():
    """测试同步 SZSE 交易日历"""
    setup_logging()
    logger = logging.getLogger(__name__)

    # 初始化数据库
    logger.info("初始化数据库连接...")
    db_manager.initialize()

    session = db_manager.get_session()
    try:
        # 记录同步前的数据状态
        total_before = session.query(func.count(TradingCalendar.id)).scalar()
        sse_before = session.query(func.count(TradingCalendar.id)).filter(TradingCalendar.market == "SSE").scalar()
        szse_before = session.query(func.count(TradingCalendar.id)).filter(TradingCalendar.market == "SZSE").scalar()
        bse_before = session.query(func.count(TradingCalendar.id)).filter(TradingCalendar.market == "BSE").scalar()

        logger.info(f"同步前数据统计:")
        logger.info(f"  总记录数: {total_before}")
        logger.info(f"  SSE记录数: {sse_before}")
        logger.info(f"  SZSE记录数: {szse_before}")
        logger.info(f"  BSE记录数: {bse_before}")

        # 同步 2020 年 SZSE 的交易日历
        logger.info("开始同步 2020 年 SZSE 交易日历...")
        count = trading_calendar_service.sync_calendar(2020, "SZSE")

        logger.info(f"同步完成，处理了 {count} 个交易日")

        # 记录同步后的数据状态
        total_after = session.query(func.count(TradingCalendar.id)).scalar()
        sse_after = session.query(func.count(TradingCalendar.id)).filter(TradingCalendar.market == "SSE").scalar()
        szse_after = session.query(func.count(TradingCalendar.id)).filter(TradingCalendar.market == "SZSE").scalar()
        bse_after = session.query(func.count(TradingCalendar.id)).filter(TradingCalendar.market == "BSE").scalar()

        logger.info(f"同步后数据统计:")
        logger.info(f"  总记录数: {total_after}")
        logger.info(f"  SSE记录数: {sse_after}")
        logger.info(f"  SZSE记录数: {szse_after}")
        logger.info(f"  BSE记录数: {bse_after}")

        # 检查 2020 年的数据
        sse_2020_count = session.query(func.count(TradingCalendar.id)).filter(
            TradingCalendar.market == "SSE",
            TradingCalendar.year == 2020
        ).scalar()

        szse_2020_count = session.query(func.count(TradingCalendar.id)).filter(
            TradingCalendar.market == "SZSE",
            TradingCalendar.year == 2020
        ).scalar()

        logger.info(f"2020年数据统计:")
        logger.info(f"  SSE 2020记录数: {sse_2020_count}")
        logger.info(f"  SZSE 2020记录数: {szse_2020_count}")

        # 验证 trade_date 的唯一性
        from sqlalchemy import text
        unique_check = session.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT trade_date, COUNT(*) as cnt
                FROM trading_calendar
                WHERE year = 2020
                GROUP BY trade_date
                HAVING COUNT(*) > 1
            ) AS duplicates;
        """)).fetchone()[0]

        logger.info(f"2020年存在重复 trade_date 的数量: {unique_check}")

        # 验证结果
        if szse_2020_count == 0:
            logger.info("✓ SZSE 同步的数据保存为了 SSE（没有新增 SZSE 记录）")
        else:
            logger.info("✗ SZSE 同步的数据没有正确转换为 SSE（仍存在 SZSE 记录）")

        if unique_check == 0:
            logger.info("✓ trade_date 唯一性约束生效")
        else:
            logger.info("✗ 存在重复的 trade_date")

        # 检查 SSE 中 2020 年的数据量是否增加
        expected_increase = 366 if count > 0 else 0  # 2020年是闰年
        if sse_after > sse_before:
            logger.info(f"✓ SSE 记录数增加了 {sse_after - sse_before}")
        else:
            logger.info(f"? SSE 记录数没有变化，可能数据已存在")

    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    test_szse_sync()
