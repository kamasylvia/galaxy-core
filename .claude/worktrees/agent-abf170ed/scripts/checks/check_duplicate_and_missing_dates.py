#!/usr/bin/env python3
"""
检查交易日历表中的重复日期和缺失日期
"""

import sys
import os

sys.path.insert(0, os.getcwd())

from datetime import date, timedelta
from galaxy_db_bridge.database.core.connection import db_manager
from galaxy_db_bridge.database.models.trading_calendar import TradingCalendar


def check_duplicates_and_missing_dates():
    """检查重复日期和缺失日期"""
    print("初始化数据库连接...")
    db_manager.initialize()

    session = db_manager.get_session()
    try:
        # 获取所有交易日期，按日期排序
        all_dates = (
            session.query(TradingCalendar.trade_date)
            .filter(TradingCalendar.market == "SSE_上海证券交易所")
            .order_by(TradingCalendar.trade_date)
            .all()
        )

        dates_list = [date_row[0] for date_row in all_dates]
        print(f"数据库中共有 {len(dates_list)} 条记录")

        # 检查重复日期
        seen_dates = set()
        duplicates = []
        for d in dates_list:
            if d in seen_dates:
                duplicates.append(d)
            else:
                seen_dates.add(d)

        if duplicates:
            print(f"\n发现 {len(duplicates)} 个重复日期:")
            for dup in duplicates:
                print(f"  {dup}")

            # 查询重复日期的详细信息
            from sqlalchemy import func

            duplicate_info = (
                session.query(
                    TradingCalendar.trade_date,
                    func.count(TradingCalendar.id).label("count"),
                )
                .filter(
                    TradingCalendar.trade_date.in_(duplicates),
                    TradingCalendar.market == "SSE_上海证券交易所",
                )
                .group_by(TradingCalendar.trade_date)
                .all()
            )

            print("\n重复日期详细信息:")
            for date_val, count in duplicate_info:
                print(f"  {date_val}: {count} 条记录")
        else:
            print("\n未发现重复日期")

        # 检查缺失日期（2010-01-01 到 2026-12-31）
        start_date = date(2010, 1, 1)
        end_date = date(2026, 12, 31)

        # 生成完整的日期范围
        full_date_range = set()
        current_date = start_date
        while current_date <= end_date:
            full_date_range.add(current_date)
            current_date += timedelta(days=1)

        # 检查哪些日期缺失
        existing_dates = set(dates_list)
        missing_dates = sorted(list(full_date_range - existing_dates))

        if missing_dates:
            print(f"\n发现 {len(missing_dates)} 个缺失日期:")
            # 只显示前10个和后10个缺失日期
            if len(missing_dates) <= 20:
                for miss_date in missing_dates:
                    print(f"  {miss_date}")
            else:
                print("前10个缺失日期:")
                for miss_date in missing_dates[:10]:
                    print(f"  {miss_date}")
                print("...")
                print("后10个缺失日期:")
                for miss_date in missing_dates[-10:]:
                    print(f"  {miss_date}")
        else:
            print("\n未发现缺失日期")

        print(f"\n日期范围检查:")
        print(f"  预期范围: {start_date} 到 {end_date}")
        print(f"  预期天数: {(end_date - start_date).days + 1}")
        print(f"  实际天数: {len(existing_dates)}")
        print(f"  缺失天数: {len(missing_dates)}")

    except Exception as e:
        print(f"检查过程中发生错误: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    check_duplicates_and_missing_dates()
