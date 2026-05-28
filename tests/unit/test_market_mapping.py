#!/usr/bin/env python3
"""测试交易日历服务使用共享日历。"""

from datetime import date

from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.services.trading_calendar import trading_calendar_service


def test_shared_trading_calendar():
    """测试交易日历服务对所有调用共享同一套日历。"""
    print("初始化数据库连接...")
    db_manager.initialize()

    start_date = date(2024, 1, 1)
    end_date = date(2024, 12, 31)

    print("\n获取共享交易日历...")
    trading_days = trading_calendar_service.get_trading_days(start_date, end_date)
    print(f"获取到 {len(trading_days)} 个交易日")
    print(f"前3个交易日: {trading_days[:3]}")
    print(f"后3个交易日: {trading_days[-3:]}")

    test_date = date(2024, 3, 15)
    is_trading_day = trading_calendar_service.is_trading_day(test_date)
    print(f"{test_date} 是否为交易日: {is_trading_day}")

    trading_days_again = trading_calendar_service.get_trading_days(start_date, end_date)
    print(f"再次获取共享交易日历数量: {len(trading_days_again)}")

    assert trading_days_again == trading_days

    print("\n所有测试完成！")


if __name__ == "__main__":
    test_shared_trading_calendar()
