"""验证交易日历缓存是否正常工作."""

import os
import sys
from datetime import date

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from galaxy_db_bridge.database.core.connection import init_database, db_manager
from galaxy_db_bridge.database.services.trading_calendar import trading_calendar_service
from galaxy_db_bridge.database.models.trading_calendar import TradingCalendar
from sqlalchemy import and_, delete

# 初始化数据库
init_database(create_tables=False)
print("数据库初始化成功")

# 清除 2016 年 1-2 月的测试数据
session = db_manager.get_session()
try:
    session.execute(
        delete(TradingCalendar).where(
            and_(
                TradingCalendar.market == "SSE",
                TradingCalendar.trade_date >= date(2016, 1, 1),
                TradingCalendar.trade_date <= date(2016, 2, 29),
            )
        )
    )
    session.commit()
    print("已清除测试数据")
finally:
    session.close()

start_date = date(2016, 1, 1)
end_date = date(2016, 2, 28)
market = "SSE"

print(f"\n=== 第一次调用: 获取 {start_date} 到 {end_date} 的交易日 ===")
trading_days_1 = trading_calendar_service.get_trading_days(start_date, end_date, market)
print(f"获取到 {len(trading_days_1)} 个交易日")

print(f"\n=== 第二次调用: 获取相同范围的交易日（应该命中缓存）===")
trading_days_2 = trading_calendar_service.get_trading_days(start_date, end_date, market)
print(f"获取到 {len(trading_days_2)} 个交易日")

print(f"\n=== 第三次调用: 获取更小范围 2016-01-01 到 2016-01-31（应该命中缓存）===")
trading_days_3 = trading_calendar_service.get_trading_days(date(2016, 1, 1), date(2016, 1, 31), market)
print(f"获取到 {len(trading_days_3)} 个交易日")

print("\n如果上面三次调用中第二次和第三次没有显示'从 akshare 获取'的日志，则缓存已生效。")
