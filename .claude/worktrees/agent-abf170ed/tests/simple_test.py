#!/usr/bin/env python3
"""
简单测试同步 SZSE 交易日历是否会保存为 SSE
"""

from datetime import date
from galaxy_db_bridge.database.core.connection import db_manager
from galaxy_db_bridge.database.services.trading_calendar import trading_calendar_service


def test_szse_sync():
    """测试同步 SZSE 交易日历"""
    print("初始化数据库连接...")
    db_manager.initialize()

    print("开始同步 2020 年 SZSE 交易日历...")
    count = trading_calendar_service.sync_calendar(2020, "SZSE")
    print(f"同步完成，处理了 {count} 个交易日")

    # 查询 2020 年的数据分布
    from galaxy_db_bridge.database.models.trading_calendar import TradingCalendar
    from sqlalchemy import func

    session = db_manager.get_session()
    try:
        sse_2020_count = session.query(TradingCalendar).filter(
            TradingCalendar.market == "SSE",
            TradingCalendar.year == 2020
        ).count()

        szse_2020_count = session.query(TradingCalendar).filter(
            TradingCalendar.market == "SZSE",
            TradingCalendar.year == 2020
        ).count()

        print(f"2020年数据统计:")
        print(f"  SSE 2020记录数: {sse_2020_count}")
        print(f"  SZSE 2020记录数: {szse_2020_count}")

        if szse_2020_count == 0 and sse_2020_count > 0:
            print("✓ 验证通过：SZSE 同步的数据保存为了 SSE（没有新增 SZSE 记录）")
        else:
            print("✗ 验证失败：SZSE 同步的数据没有正确转换为 SSE")
    finally:
        session.close()


if __name__ == "__main__":
    test_szse_sync()
