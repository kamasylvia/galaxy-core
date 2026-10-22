#!/usr/bin/env python3
"""测试交易日历服务使用共享日历.

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
async def test_shared_trading_calendar(service: TradingCalendarService):
    """测试交易日历服务对所有调用共享同一套日历."""
    print("初始化数据库连接...")

    start_date = date(2024, 1, 1)
    end_date = date(2024, 12, 31)

    print("\n获取共享交易日历...")
    trading_days = await service.get_trading_days_async(start_date, end_date)
    print(f"获取到 {len(trading_days)} 个交易日")
    print(f"前3个交易日: {trading_days[:3]}")
    print(f"后3个交易日: {trading_days[-3:]}")

    test_date = date(2024, 3, 15)
    is_trading = await service.is_trading_day_async(test_date)
    print(f"{test_date} 是否为交易日: {is_trading}")

    trading_days_again = await service.get_trading_days_async(start_date, end_date)
    print(f"再次获取共享交易日历数量: {len(trading_days_again)}")

    assert trading_days_again == trading_days

    print("\n所有测试完成！")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
