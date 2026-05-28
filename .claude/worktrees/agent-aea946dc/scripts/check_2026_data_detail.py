#!/usr/bin/env python3
"""检查 2026 年数据的详细时间分布."""

import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.models.kline import KlineWeek, KlineMonth
from sqlalchemy import func


def check_2026_week_data(session):
    """检查 2026 年周线数据的详细分布."""
    print("=" * 60)
    print("2026 年周线数据详细分布")
    print("=" * 60)

    # 按月份统计
    month_counts = (
        session.query(
            func.extract('month', KlineWeek.trade_time).label('month'),
            func.count().label('count')
        )
        .filter(func.extract('year', KlineWeek.trade_time) == 2026)
        .group_by(func.extract('month', KlineWeek.trade_time))
        .order_by(func.extract('month', KlineWeek.trade_time))
        .all()
    )

    print("\n按月份统计:")
    for month, count in month_counts:
        print(f"  2026年{int(month)}月: {count} 条")

    # 检查3月的数据（本月）
    march_data = (
        session.query(KlineWeek.symbol, KlineWeek.trade_time)
        .filter(func.extract('year', KlineWeek.trade_time) == 2026)
        .filter(func.extract('month', KlineWeek.trade_time) == 3)
        .order_by(KlineWeek.trade_time)
        .all()
    )

    print(f"\n2026年3月周线数据（本月）:")
    if march_data:
        print(f"  记录数: {len(march_data)}")
        # 按日期分组
        date_groups = {}
        for symbol, trade_time in march_data:
            date_key = trade_time.date()
            if date_key not in date_groups:
                date_groups[date_key] = 0
            date_groups[date_key] += 1

        print(f"  按日期分布:")
        for d in sorted(date_groups.keys()):
            print(f"    {d}: {date_groups[d]} 条")
    else:
        print("  没有数据")

    # 检查2月的数据（上月）
    feb_data = (
        session.query(KlineWeek.symbol, KlineWeek.trade_time)
        .filter(func.extract('year', KlineWeek.trade_time) == 2026)
        .filter(func.extract('month', KlineWeek.trade_time) == 2)
        .order_by(KlineWeek.trade_time)
        .all()
    )

    print(f"\n2026年2月周线数据（上月）:")
    if feb_data:
        print(f"  记录数: {len(feb_data)}")
        # 按日期分组
        date_groups = {}
        for symbol, trade_time in feb_data:
            date_key = trade_time.date()
            if date_key not in date_groups:
                date_groups[date_key] = 0
            date_groups[date_key] += 1

        print(f"  按日期分布:")
        for d in sorted(date_groups.keys()):
            print(f"    {d}: {date_groups[d]} 条")
    else:
        print("  没有数据")


def check_2026_month_data(session):
    """检查 2026 年月线数据的详细分布."""
    print("\n" + "=" * 60)
    print("2026 年月线数据详细分布")
    print("=" * 60)

    # 按月份统计
    month_counts = (
        session.query(
            func.extract('month', KlineMonth.trade_time).label('month'),
            func.count().label('count')
        )
        .filter(func.extract('year', KlineMonth.trade_time) == 2026)
        .group_by(func.extract('month', KlineMonth.trade_time))
        .order_by(func.extract('month', KlineMonth.trade_time))
        .all()
    )

    print("\n按月份统计:")
    for month, count in month_counts:
        print(f"  2026年{int(month)}月: {count} 条")

    # 检查3月的数据（本月）
    march_data = (
        session.query(KlineMonth.symbol, KlineMonth.trade_time)
        .filter(func.extract('year', KlineMonth.trade_time) == 2026)
        .filter(func.extract('month', KlineMonth.trade_time) == 3)
        .order_by(KlineMonth.trade_time)
        .all()
    )

    print(f"\n2026年3月月线数据（本月）:")
    if march_data:
        print(f"  记录数: {len(march_data)}")
        print(f"  示例（前10条）:")
        for symbol, trade_time in march_data[:10]:
            print(f"    - {symbol}: {trade_time}")
    else:
        print("  没有数据")

    # 检查1月的数据
    jan_data = (
        session.query(KlineMonth.symbol, KlineMonth.trade_time)
        .filter(func.extract('year', KlineMonth.trade_time) == 2026)
        .filter(func.extract('month', KlineMonth.trade_time) == 1)
        .order_by(KlineMonth.trade_time)
        .all()
    )

    print(f"\n2026年1月月线数据:")
    if jan_data:
        print(f"  记录数: {len(jan_data)}")
        print(f"  示例（前10条）:")
        for symbol, trade_time in jan_data[:10]:
            print(f"    - {symbol}: {trade_time}")
    else:
        print("  没有数据")


def main():
    print("初始化数据库连接...")
    db_manager.initialize()

    session = db_manager.get_session()
    try:
        check_2026_week_data(session)
        check_2026_month_data(session)
    finally:
        session.close()

    print("\n" + "=" * 60)
    print("检查完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
