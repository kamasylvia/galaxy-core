#!/usr/bin/env python3
"""修复交易日历表中的重复日期和缺失日期。"""

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.getcwd())

from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.models.trading_calendar import TradingCalendar


def fix_duplicates_and_missing_dates():
    """修复重复日期和缺失日期"""
    print("初始化数据库连接...")
    db_manager.initialize()

    session = db_manager.get_session()
    try:
        from sqlalchemy import func
        import akshare as ak
        import pandas as pd

        duplicate_dates = (
            session.query(
                TradingCalendar.trade_date,
                func.count(TradingCalendar.id).label("count"),
            )
            .group_by(TradingCalendar.trade_date)
            .having(func.count(TradingCalendar.id) > 1)
            .all()
        )

        print(f"发现 {len(duplicate_dates)} 个重复日期:")
        for dup_date, count in duplicate_dates:
            print(f"  {dup_date}: {count} 条记录")

        for dup_date, _ in duplicate_dates:
            records = (
                session.query(TradingCalendar.id)
                .filter(TradingCalendar.trade_date == dup_date)
                .order_by(TradingCalendar.id)
                .all()
            )

            ids_to_delete = [record.id for record in records[1:]]
            if ids_to_delete:
                session.query(TradingCalendar).filter(
                    TradingCalendar.id.in_(ids_to_delete)
                ).delete(synchronize_session=False)
                print(f"  已删除 {len(ids_to_delete)} 条重复记录 ({dup_date})")

        start_date = date(2010, 1, 1)
        end_date = date(2026, 12, 31)

        all_existing_dates = session.query(TradingCalendar.trade_date).all()
        existing_dates = set(date_row[0] for date_row in all_existing_dates)

        full_date_range = set()
        current_date = start_date
        while current_date <= end_date:
            full_date_range.add(current_date)
            current_date += timedelta(days=1)

        missing_dates = sorted(list(full_date_range - existing_dates))

        print(f"\n发现 {len(missing_dates)} 个缺失日期:")
        for miss_date in missing_dates:
            print(f"  {miss_date}")

        print("\n从 akshare 获取交易日历作为参考...")
        df = ak.tool_trade_date_hist_sina()
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        trading_days_set = set(df["trade_date"].tolist())

        missing_records_added = 0
        for miss_date in missing_dates:
            is_trading_day = miss_date in trading_days_set
            if miss_date.weekday() >= 5:
                is_trading_day = False

            new_record = TradingCalendar(
                trade_date=miss_date,
                is_trading_day=is_trading_day,
                year=miss_date.year,
            )
            session.add(new_record)
            missing_records_added += 1

        session.commit()
        print(f"\n已修复重复记录并添加了 {missing_records_added} 个缺失日期的记录")

        duplicate_check = (
            session.query(
                TradingCalendar.trade_date,
                func.count(TradingCalendar.id).label("count"),
            )
            .group_by(TradingCalendar.trade_date)
            .having(func.count(TradingCalendar.id) > 1)
            .all()
        )

        if not duplicate_check:
            print("✓ 重复日期问题已修复")
        else:
            print(f"✗ 仍有 {len(duplicate_check)} 个重复日期问题")

        all_existing_dates_after_fix = session.query(TradingCalendar.trade_date).all()
        existing_dates_after_fix = set(date_row[0] for date_row in all_existing_dates_after_fix)
        missing_dates_after_fix = sorted(list(full_date_range - existing_dates_after_fix))

        if not missing_dates_after_fix:
            print("✓ 缺失日期问题已修复")
        else:
            print(f"✗ 仍有 {len(missing_dates_after_fix)} 个缺失日期")

        print(f"\n修复完成！当前数据库中共有 {len(existing_dates_after_fix)} 条记录")
    except Exception as e:
        session.rollback()
        print(f"修复过程中发生错误: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    fix_duplicates_and_missing_dates()
