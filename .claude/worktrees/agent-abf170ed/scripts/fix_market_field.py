#!/usr/bin/env python3
"""
修复交易日历表中的market字段格式，统一为"SSE_上海证券交易所"格式
"""

import sys
import os

sys.path.insert(0, os.getcwd())

from galaxy_db_bridge.database.core.connection import db_manager
from galaxy_db_bridge.database.models.trading_calendar import TradingCalendar


def fix_market_field():
    """修复market字段格式"""
    print("初始化数据库连接...")
    db_manager.initialize()

    session = db_manager.get_session()
    try:
        # 查找所有不规范的market值
        from sqlalchemy import func

        distinct_markets = session.query(TradingCalendar.market).distinct().all()

        print("当前所有的market值:")
        for market in distinct_markets:
            count = (
                session.query(func.count(TradingCalendar.id))
                .filter(TradingCalendar.market == market[0])
                .scalar()
            )
            print(f"  {market[0]}: {count} 条记录")

        # 将"上海证券交易所(SSE)"格式修正为"SSE_上海证券交易所"格式
        old_format = "上海证券交易所(SSE)"
        new_format = "SSE_上海证券交易所"

        count_to_fix = (
            session.query(func.count(TradingCalendar.id))
            .filter(TradingCalendar.market == old_format)
            .scalar()
        )

        if count_to_fix > 0:
            print(
                f"\n发现 {count_to_fix} 条记录使用旧格式 '{old_format}'，正在更新为 '{new_format}'..."
            )

            session.query(TradingCalendar).filter(
                TradingCalendar.market == old_format
            ).update({TradingCalendar.market: new_format})

            session.commit()
            print("更新完成!")
        else:
            print(f"\n没有发现使用旧格式 '{old_format}' 的记录。")

        # 检查更新后的结果
        print("\n更新后的market值统计:")
        market_stats = (
            session.query(TradingCalendar.market, func.count(TradingCalendar.id))
            .group_by(TradingCalendar.market)
            .all()
        )

        for market, count in market_stats:
            print(f"  {market}: {count} 条记录")

    except Exception as e:
        session.rollback()
        print(f"更新过程中发生错误: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    fix_market_field()
