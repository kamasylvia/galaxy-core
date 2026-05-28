#!/usr/bin/env python3
"""测试交易日历服务的中英文市场代码映射功能"""

from datetime import date
from galaxy_db_bridge.database.core.connection import db_manager
from galaxy_db_bridge.database.services.trading_calendar import trading_calendar_service


def test_market_mapping():
    """测试市场代码映射功能"""
    print("初始化数据库连接...")
    db_manager.initialize()

    print("\n测试中英文市场代码映射功能:")

    # 测试不同的市场代码表示方式
    test_markets = [
        ("SSE", "标准英文代码"),
        ("SH", "简写代码（应映射到SSE）"),
        ("上海证券交易所", "中文名称"),
        ("上交所", "中文简称"),
    ]

    start_date = date(2024, 1, 1)
    end_date = date(2024, 12, 31)

    for market_code, description in test_markets:
        print(f"\n测试 {description}: {market_code}")
        try:
            trading_days = trading_calendar_service.get_trading_days(
                start_date, end_date, market_code
            )
            print(f"  获取到 {len(trading_days)} 个交易日")
            print(f"  前3个交易日: {trading_days[:3]}")
            print(f"  后3个交易日: {trading_days[-3:]}")

            # 测试判断特定日期是否为交易日
            test_date = date(2024, 3, 15)
            is_trading_day = trading_calendar_service.is_trading_day(
                test_date, market_code
            )
            print(f"  {test_date} 是否为交易日: {is_trading_day}")

        except Exception as e:
            print(f"  错误: {e}")

    # 测试其他市场
    print(f"\n测试其他市场:")
    other_markets = [
        ("SZSE", "深圳证券交易所"),
        ("SZ", "深圳简写"),
        ("深交所", "深圳中文简称"),
        ("BSE", "北京证券交易所"),
        ("BJ", "北京简写"),
        ("北交所", "北京中文简称"),
    ]

    for market_code, description in other_markets:
        print(f"\n测试 {description}: {market_code}")
        try:
            trading_days = trading_calendar_service.get_trading_days(
                start_date, end_date, market_code
            )
            print(f"  获取到 {len(trading_days)} 个交易日")
        except Exception as e:
            print(f"  错误: {e}")

    print("\n所有测试完成！")


if __name__ == "__main__":
    test_market_mapping()
