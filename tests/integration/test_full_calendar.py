#!/usr/bin/env python3
"""测试完整的交易日历功能，包括交易日和非交易日.

集成测试：验证 TradingCalendarService 内部方法与真实数据库交互。
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
async def test_full_calendar(service: TradingCalendarService):
    """测试完整的交易日历功能."""
    print("测试生成完整日历...")
    # 测试生成一个小范围的日历
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 31)  # 一个月的数据

    # 获取交易日
    trading_days = service._fetch_from_akshare(
        start_date, end_date
    )

    print(f"从 akshare 获取到 {len(trading_days)} 个交易日")
    if trading_days:
        print(f"交易日范围: {min(trading_days)} 到 {max(trading_days)}")

    # 生成完整日历
    full_calendar = service._generate_full_calendar(
        start_date, end_date, trading_days
    )

    print(f"生成完整日历: {len(full_calendar)} 条记录")
    print(f"其中交易日: {len(trading_days)} 个")
    print(f"非交易日: {len(full_calendar) - len(trading_days)} 个")

    # 显示一些示例
    print("\n示例日历数据:")
    for cal_date, is_trading in full_calendar[:10]:
        print(f"  {cal_date} - {'交易日' if is_trading else '非交易日'}")

    if len(full_calendar) > 10:
        print("  ...")
        for cal_date, is_trading in full_calendar[-3:]:
            print(f"  {cal_date} - {'交易日' if is_trading else '非交易日'}")

    print("\n测试完成!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
