"""测试交易日历服务功能.

集成测试：验证 TradingCalendarService 的 async 方法与真实数据库交互。
"""

from datetime import date

import pytest

from galaxy_core.database.core.async_connection import AsyncDatabaseManager
from galaxy_core.database.services.trading_calendar import TradingCalendarService


@pytest.fixture
def service(db_manager: AsyncDatabaseManager) -> TradingCalendarService:
    """创建注入 db_manager 的 TradingCalendarService."""
    return TradingCalendarService(db_manager=db_manager)


@pytest.mark.asyncio
async def test_trading_calendar(service: TradingCalendarService):
    """测试交易日历服务功能."""
    print("初始化数据库连接...")

    print("\n1. 测试获取2024年的交易日")
    start_date = date(2024, 1, 1)
    end_date = date(2024, 12, 31)
    trading_days = await service.get_trading_days_async(start_date, end_date)

    print(f"2024年SH市场交易日数量: {len(trading_days)}")
    print(f"前5个交易日: {trading_days[:5]}")
    print(f"后5个交易日: {trading_days[-5:]}")

    print("\n2. 测试判断某一天是否为交易日")
    test_date = date(2024, 3, 15)  # 假设这是一个交易日
    is_trading = await service.is_trading_day_async(test_date)
    print(f"{test_date} 是否为交易日 (SH): {is_trading}")

    print("\n3. 测试过滤交易日")
    test_dates = [
        date(2024, 1, 1),  # 新年，非交易日
        date(2024, 1, 2),  # 一般交易日
        date(2024, 1, 7),  # 一般交易日
        date(2024, 5, 1),  # 劳动节，非交易日
        date(2024, 12, 25),  # 圣诞节，非交易日（虽然是非中国假期，但作为示例）
    ]
    all_trading_days = set(await service.get_trading_days_async(min(test_dates), max(test_dates)))
    filtered_days = [d for d in test_dates if d in all_trading_days]
    print(f"原始日期: {test_dates}")
    print(f"过滤后的交易日: {filtered_days}")

    print("\n4. 测试共享交易日历行为")
    shared_trading_days = await service.get_trading_days_async(start_date, end_date)
    print(f"再次获取共享交易日历数量: {len(shared_trading_days)}")
    assert shared_trading_days == trading_days

    print("\n所有测试完成！")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
