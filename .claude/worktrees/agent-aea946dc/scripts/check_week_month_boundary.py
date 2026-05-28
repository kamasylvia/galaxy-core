#!/usr/bin/env python3
"""检查周线和月线的边界情况.

今天是 2026-03-27（周五），检查本周和本月是否应该被清理。
"""

import os
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.models.kline import KlineWeek, KlineMonth
from galaxy_db_sync.shared_kernel.enums.interval import Interval
from galaxy_db_sync.shared_kernel.utils.interval_boundary_checker import (
    IntervalBoundaryChecker,
)


def check_week_boundary(checker: IntervalBoundaryChecker, today: date):
    """检查本周边界."""
    print("=" * 60)
    print("周线边界检查")
    print("=" * 60)

    # 本周的开始日期（周一）
    current_week_start = today - timedelta(days=today.weekday())
    # 下周一
    next_week_start = current_week_start + timedelta(days=7)

    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    print(f"今天: {today} ({weekdays[today.weekday()]})")
    print(f"本周开始 (周一): {current_week_start}")
    print(f"下周一 (下周开始): {next_week_start}")

    is_complete = checker.is_interval_complete(Interval.WEEK, current_week_start, today)
    print(f"本周是否已结束: {is_complete}")

    # 如果今天 < 下周一，说明本周还未结束
    if not is_complete:
        print(f"\n✓ 本周未结束，应该清理本周的周线数据")
        return current_week_start
    else:
        print(f"\n✗ 本周已结束，不应该清理本周的周线数据")
        return None


def check_month_boundary(checker: IntervalBoundaryChecker, today: date):
    """检查本月边界."""
    print("\n" + "=" * 60)
    print("月线边界检查")
    print("=" * 60)

    # 本月的开始日期（1日）
    current_month_start = today.replace(day=1)

    # 计算下月1日
    if today.month == 12:
        next_month_start = date(today.year + 1, 1, 1)
    else:
        next_month_start = date(today.year, today.month + 1, 1)

    print(f"今天: {today}")
    print(f"本月开始 (1日): {current_month_start}")
    print(f"下月1日: {next_month_start}")

    is_complete = checker.is_interval_complete(Interval.MONTH, current_month_start, today)
    print(f"本月是否已结束: {is_complete}")

    # 如果今天 < 下月1日，说明本月还未结束
    if not is_complete:
        print(f"\n✓ 本月未结束，应该清理本月的月线数据")
        return current_month_start
    else:
        print(f"\n✗ 本月已结束，不应该清理本月的月线数据")
        return None


def check_db_data(session, week_start, month_start):
    """检查数据库中的数据."""
    print("\n" + "=" * 60)
    print("数据库数据检查")
    print("=" * 60)

    # 检查本周的周线数据
    if week_start:
        week_records = (
            session.query(KlineWeek.symbol, KlineWeek.trade_time)
            .filter(
                KlineWeek.trade_time
                >= datetime.combine(week_start, datetime.min.time())
            )
            .order_by(KlineWeek.symbol)
            .all()
        )

        print(f"\n本周 ({week_start}) 的周线数据:")
        if week_records:
            print(f"  记录数: {len(week_records)}")
            print(f"  示例（前10条）:")
            for symbol, trade_time in week_records[:10]:
                print(f"    - {symbol}: {trade_time}")
        else:
            print("  没有数据")

    # 检查本月的月线数据
    if month_start:
        month_records = (
            session.query(KlineMonth.symbol, KlineMonth.trade_time)
            .filter(
                KlineMonth.trade_time
                >= datetime.combine(month_start, datetime.min.time())
            )
            .order_by(KlineMonth.symbol)
            .all()
        )

        print(f"\n本月 ({month_start}) 的月线数据:")
        if month_records:
            print(f"  记录数: {len(month_records)}")
            print(f"  示例（前10条）:")
            for symbol, trade_time in month_records[:10]:
                print(f"    - {symbol}: {trade_time}")
        else:
            print("  没有数据")


def main():
    today = date(2026, 3, 27)  # 周五

    # 创建周期边界检查器
    checker = IntervalBoundaryChecker()

    week_start = check_week_boundary(checker, today)
    month_start = check_month_boundary(checker, today)

    print("\n初始化数据库连接...")
    db_manager.initialize()

    session = db_manager.get_session()
    try:
        check_db_data(session, week_start, month_start)
    finally:
        session.close()

    print("\n" + "=" * 60)
    print("检查完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
