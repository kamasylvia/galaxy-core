#!/usr/bin/env python3
"""简单测试共享交易日历同步是否成功。"""

from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.services.trading_calendar import trading_calendar_service


def test_szse_sync():
    """测试以 SZSE 调用同步时会写入共享交易日历。"""
    print("初始化数据库连接...")
    db_manager.initialize()

    print("开始同步 2020 年交易日历...")
    count = trading_calendar_service.sync_calendar(2020)
    print(f"同步完成，处理了 {count} 个交易日")

    from galaxy_db_sync.database.models.trading_calendar import TradingCalendar

    session = db_manager.get_session()
    try:
        year_2020_count = session.query(TradingCalendar).filter(
            TradingCalendar.year == 2020
        ).count()

        print("2020年数据统计:")
        print(f"  2020记录数: {year_2020_count}")

        if year_2020_count > 0:
            print("✓ 验证通过：SZSE 调用成功写入了共享交易日历")
        else:
            print("✗ 验证失败：SZSE 调用后没有写入共享交易日历")
    finally:
        session.close()


if __name__ == "__main__":
    test_szse_sync()
