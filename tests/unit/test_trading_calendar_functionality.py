#!/usr/bin/env python3
"""测试交易日历服务功能"""

from datetime import date
from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.services.trading_calendar import trading_calendar_service


def test_trading_calendar():
    """测试交易日历服务功能"""
    print("初始化数据库连接...")
    db_manager.initialize()

    print("\n1. 测试获取2024年的交易日")
    start_date = date(2024, 1, 1)
    end_date = date(2024, 12, 31)
    trading_days = trading_calendar_service.get_trading_days(start_date, end_date)

    print(f"2024年SH市场交易日数量: {len(trading_days)}")
    print(f"前5个交易日: {trading_days[:5]}")
    print(f"后5个交易日: {trading_days[-5:]}")

    print("\n2. 测试判断某一天是否为交易日")
    test_date = date(2024, 3, 15)  # 假设这是一个交易日
    is_trading_day = trading_calendar_service.is_trading_day(test_date)
    print(f"{test_date} 是否为交易日 (SH): {is_trading_day}")

    print("\n3. 测试过滤交易日")
    test_dates = [
        date(2024, 1, 1),  # 新年，非交易日
        date(2024, 1, 2),  # 一般交易日
        date(2024, 1, 7),  # 一般交易日
        date(2024, 5, 1),  # 劳动节，非交易日
        date(2024, 12, 25),  # 圣诞节，非交易日（虽然是非中国假期，但作为示例）
    ]
    filtered_days = trading_calendar_service.filter_trading_days(test_dates)
    print(f"原始日期: {test_dates}")
    print(f"过滤后的交易日: {filtered_days}")

    print("\n4. 测试共享交易日历行为")
    shared_trading_days = trading_calendar_service.get_trading_days(start_date, end_date)
    print(f"再次获取共享交易日历数量: {len(shared_trading_days)}")
    assert shared_trading_days == trading_days

    print("\n所有测试完成！")


if __name__ == "__main__":
    test_trading_calendar()
