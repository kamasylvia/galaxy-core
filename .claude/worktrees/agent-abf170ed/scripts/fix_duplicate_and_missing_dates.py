#!/usr/bin/env python3
"""
修复交易日历表中的重复日期和缺失日期
"""

import sys
import os

sys.path.insert(0, os.getcwd())

from datetime import date, timedelta
from galaxy_db_bridge.database.core.connection import db_manager
from galaxy_db_bridge.database.models.trading_calendar import TradingCalendar


def fix_duplicates_and_missing_dates():
    """修复重复日期和缺失日期"""
    print("初始化数据库连接...")
    db_manager.initialize()

    session = db_manager.get_session()
    try:
        # 检查重复日期
        from sqlalchemy import func

        duplicate_dates = (
            session.query(
                TradingCalendar.trade_date,
                func.count(TradingCalendar.id).label("count"),
            )
            .filter(TradingCalendar.market == "SSE_上海证券交易所")
            .group_by(TradingCalendar.trade_date)
            .having(func.count(TradingCalendar.id) > 1)
            .all()
        )

        print(f"发现 {len(duplicate_dates)} 个重复日期:")
        for dup_date, count in duplicate_dates:
            print(f"  {dup_date}: {count} 条记录")

        # 删除重复记录（保留ID最小的一条）
        for dup_date, count in duplicate_dates:
            # 获取该日期的所有记录ID，按ID升序排列，保留第一个
            records = (
                session.query(TradingCalendar.id)
                .filter(
                    TradingCalendar.trade_date == dup_date,
                    TradingCalendar.market == "SSE_上海证券交易所",
                )
                .order_by(TradingCalendar.id)
                .all()
            )

            # 删除除第一个外的所有记录
            ids_to_delete = [record.id for record in records[1:]]
            if ids_to_delete:
                session.query(TradingCalendar).filter(
                    TradingCalendar.id.in_(ids_to_delete)
                ).delete(synchronize_session=False)

                print(f"  已删除 {len(ids_to_delete)} 条重复记录 ({dup_date})")

        # 检查缺失日期（2010-01-01 到 2026-12-31）
        start_date = date(2010, 1, 1)
        end_date = date(2026, 12, 31)

        # 获取数据库中现有的所有日期
        all_existing_dates = (
            session.query(TradingCalendar.trade_date)
            .filter(TradingCalendar.market == "SSE_上海证券交易所")
            .all()
        )

        existing_dates = set(date_row[0] for date_row in all_existing_dates)

        # 生成完整的日期范围
        full_date_range = set()
        current_date = start_date
        while current_date <= end_date:
            full_date_range.add(current_date)
            current_date += timedelta(days=1)

        # 检查哪些日期缺失
        missing_dates = sorted(list(full_date_range - existing_dates))

        print(f"\n发现 {len(missing_dates)} 个缺失日期:")
        for miss_date in missing_dates:
            print(f"  {miss_date}")

        # 为缺失的日期添加记录
        # 根据日期判断是否为交易日（周末和节假日为非交易日，其他为交易日）
        from datetime import datetime
        import pandas as pd
        import akshare as ak

        # 获取akshare中的交易日历作为参考
        print("\n从 akshare 获取交易日历作为参考...")
        df = ak.tool_trade_date_hist_sina()
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        trading_days_set = set(df["trade_date"].tolist())

        missing_records_added = 0
        for miss_date in missing_dates:
            # 判断是否为交易日
            # 如果在akshare的交易日历中，或者是工作日（周一到周五）且不在节假日中，则为交易日
            is_trading_day = miss_date in trading_days_set

            # 如果不是周末，但不在交易日列表中，也可能是节假日，标记为非交易日
            if not is_trading_day and miss_date.weekday() < 5:  # 工作日
                # 检查是否在交易日列表中
                is_trading_day = miss_date in trading_days_set

            # 对于周末，强制设为非交易日
            if miss_date.weekday() >= 5:  # 周六周日
                is_trading_day = False

            # 创建缺失的记录
            new_record = TradingCalendar(
                market="SSE_上海证券交易所",
                trade_date=miss_date,
                is_trading_day=is_trading_day,
                year=miss_date.year,
            )
            session.add(new_record)
            missing_records_added += 1

        # 提交所有更改
        session.commit()
        print(f"\n已修复重复记录并添加了 {missing_records_added} 个缺失日期的记录")

        # 验证修复结果
        duplicate_check = (
            session.query(
                TradingCalendar.trade_date,
                func.count(TradingCalendar.id).label("count"),
            )
            .filter(TradingCalendar.market == "SSE_上海证券交易所")
            .group_by(TradingCalendar.trade_date)
            .having(func.count(TradingCalendar.id) > 1)
            .all()
        )

        if not duplicate_check:
            print("✓ 重复日期问题已修复")
        else:
            print(f"✗ 仍有 {len(duplicate_check)} 个重复日期问题")

        # 检查是否还有缺失日期
        all_existing_dates_after_fix = (
            session.query(TradingCalendar.trade_date)
            .filter(TradingCalendar.market == "SSE_上海证券交易所")
            .all()
        )

        existing_dates_after_fix = set(
            date_row[0] for date_row in all_existing_dates_after_fix
        )
        missing_dates_after_fix = sorted(
            list(full_date_range - existing_dates_after_fix)
        )

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
