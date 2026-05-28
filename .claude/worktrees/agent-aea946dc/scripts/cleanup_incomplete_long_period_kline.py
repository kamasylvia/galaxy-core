#!/usr/bin/env python3
"""清理未走完周期的长周期 K 线数据.

在实现长周期边界检查之前，可能已经同步了一些不符合规则的数据：
- 本周的周线数据（但本周还未结束）
- 本月的月线数据（但本月还未结束）
- 本季的季线数据（但本季还未结束）
- 本年的年线数据（但本年还未结束）

本脚本用于识别并清理这些不符合边界检查规则的数据。
"""

import os
import sys
from datetime import date, datetime, timedelta
from typing import Dict

# 添加项目根目录和 src 目录到 Python 路径
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.models.kline import (
    KlineWeek,
    KlineMonth,
    KlineSeason,
    KlineYear,
)
from galaxy_db_sync.shared_kernel.enums.interval import Interval
from galaxy_db_sync.shared_kernel.utils.interval_boundary_checker import (
    IntervalBoundaryChecker,
)


def cleanup_incomplete_week_data(
    session, checker: IntervalBoundaryChecker, today: date
) -> int:
    """清理未走完的本周周线数据.

    Args:
        session: 数据库会话
        checker: 周期边界检查器实例
        today: 今天的日期

    Returns:
        删除的记录数
    """
    # 获取本周的开始日期（周一）
    current_week_start = today - timedelta(days=today.weekday())

    # 如果本周未结束，清理本周数据
    if not checker.is_interval_complete(Interval.WEEK, current_week_start, today):
        records = (
            session.query(KlineWeek)
            .filter(
                KlineWeek.trade_time
                >= datetime.combine(current_week_start, datetime.min.time())
            )
            .all()
        )

        if records:
            count = len(records)
            for record in records:
                session.delete(record)
            print(f"  发现 {count} 条未走完的本周周线数据 (本周开始: {current_week_start})")
            return count
    return 0


def cleanup_incomplete_month_data(
    session, checker: IntervalBoundaryChecker, today: date
) -> int:
    """清理未走完的本月月线数据.

    Args:
        session: 数据库会话
        checker: 周期边界检查器实例
        today: 今天的日期

    Returns:
        删除的记录数
    """
    # 获取本月的开始日期（1日）
    current_month_start = today.replace(day=1)

    # 如果本月未结束，清理本月数据
    if not checker.is_interval_complete(Interval.MONTH, current_month_start, today):
        records = (
            session.query(KlineMonth)
            .filter(
                KlineMonth.trade_time
                >= datetime.combine(current_month_start, datetime.min.time())
            )
            .all()
        )

        if records:
            count = len(records)
            for record in records:
                session.delete(record)
            print(f"  发现 {count} 条未走完的本月月线数据 (本月开始: {current_month_start})")
            return count
    return 0


def cleanup_incomplete_season_data(
    session, checker: IntervalBoundaryChecker, today: date
) -> int:
    """清理未走完的本季季线数据.

    Args:
        session: 数据库会话
        checker: 周期边界检查器实例
        today: 今天的日期

    Returns:
        删除的记录数
    """
    # 获取本季的开始日期
    quarter = (today.month - 1) // 3 + 1
    start_month = (quarter - 1) * 3 + 1
    current_quarter_start = today.replace(month=start_month, day=1)

    # 如果本季未结束，清理本季数据
    if not checker.is_interval_complete(Interval.SEASON, current_quarter_start, today):
        records = (
            session.query(KlineSeason)
            .filter(
                KlineSeason.trade_time
                >= datetime.combine(current_quarter_start, datetime.min.time())
            )
            .all()
        )

        if records:
            count = len(records)
            for record in records:
                session.delete(record)
            print(f"  发现 {count} 条未走完的本季季线数据 (本季开始: {current_quarter_start})")
            return count
    return 0


def cleanup_incomplete_year_data(
    session, checker: IntervalBoundaryChecker, today: date
) -> int:
    """清理未走完的本年年线数据.

    Args:
        session: 数据库会话
        checker: 周期边界检查器实例
        today: 今天的日期

    Returns:
        删除的记录数
    """
    # 获取本年的开始日期（1月1日）
    current_year_start = today.replace(month=1, day=1)

    # 如果本年未结束，清理本年数据
    if not checker.is_interval_complete(Interval.YEAR, current_year_start, today):
        records = (
            session.query(KlineYear)
            .filter(
                KlineYear.trade_time
                >= datetime.combine(current_year_start, datetime.min.time())
            )
            .all()
        )

        if records:
            count = len(records)
            for record in records:
                session.delete(record)
            print(f"  发现 {count} 条未走完的本年年线数据 (本年开始: {current_year_start})")
            return count
    return 0


def preview_incomplete_data(
    session, checker: IntervalBoundaryChecker, today: date
) -> Dict:
    """预览将要删除的数据.

    Args:
        session: 数据库会话
        checker: 周期边界检查器实例
        today: 今天的日期

    Returns:
        各周期将要删除的记录数
    """
    preview = {}

    # 周线预览
    current_week_start = today - timedelta(days=today.weekday())
    if not checker.is_interval_complete(Interval.WEEK, current_week_start, today):
        week_count = (
            session.query(KlineWeek)
            .filter(
                KlineWeek.trade_time
                >= datetime.combine(current_week_start, datetime.min.time())
            )
            .count()
        )
        next_week_start = current_week_start + timedelta(days=7)
        preview["week"] = {
            "count": week_count,
            "period_start": current_week_start,
            "reason": f"本周未结束（需等到 {next_week_start} 之后）",
        }

    # 月线预览
    current_month_start = today.replace(day=1)
    if not checker.is_interval_complete(Interval.MONTH, current_month_start, today):
        month_count = (
            session.query(KlineMonth)
            .filter(
                KlineMonth.trade_time
                >= datetime.combine(current_month_start, datetime.min.time())
            )
            .count()
        )
        if today.month == 12:
            next_month_start = date(today.year + 1, 1, 1)
        else:
            next_month_start = date(today.year, today.month + 1, 1)
        preview["month"] = {
            "count": month_count,
            "period_start": current_month_start,
            "reason": f"本月未结束（需等到 {next_month_start} 之后）",
        }

    # 季线预览
    quarter = (today.month - 1) // 3 + 1
    start_month = (quarter - 1) * 3 + 1
    current_quarter_start = today.replace(month=start_month, day=1)
    if not checker.is_interval_complete(Interval.SEASON, current_quarter_start, today):
        season_count = (
            session.query(KlineSeason)
            .filter(
                KlineSeason.trade_time
                >= datetime.combine(current_quarter_start, datetime.min.time())
            )
            .count()
        )
        if quarter == 4:
            next_quarter_start = date(today.year + 1, 1, 1)
        else:
            next_quarter_start = date(today.year, quarter * 3 + 1, 1)
        preview["season"] = {
            "count": season_count,
            "period_start": current_quarter_start,
            "reason": f"本季未结束（需等到 {next_quarter_start} 之后）",
        }

    # 年线预览
    current_year_start = today.replace(month=1, day=1)
    if not checker.is_interval_complete(Interval.YEAR, current_year_start, today):
        year_count = (
            session.query(KlineYear)
            .filter(
                KlineYear.trade_time
                >= datetime.combine(current_year_start, datetime.min.time())
            )
            .count()
        )
        next_year_start = date(today.year + 1, 1, 1)
        preview["year"] = {
            "count": year_count,
            "period_start": current_year_start,
            "reason": f"本年未结束（需等到 {next_year_start} 之后）",
        }

    return preview


def cleanup_incomplete_long_period_kline(dry_run: bool = True, today: date = None):
    """清理未走完周期的长周期 K 线数据.

    Args:
        dry_run: 是否为预览模式（不实际删除数据）
        today: 指定今天的日期（用于测试），默认为系统当前日期
    """
    if today is None:
        today = date.today()

    print("=" * 60)
    print("长周期 K 线数据清理工具")
    print("=" * 60)
    print(f"参考日期: {today}")
    print(f"模式: {'预览模式（不删除数据）' if dry_run else '执行模式（将删除数据）'}")
    print("-" * 60)

    print("\n初始化数据库连接...")
    db_manager.initialize()

    # 创建周期边界检查器
    checker = IntervalBoundaryChecker()

    session = db_manager.get_session()
    try:
        if dry_run:
            # 预览模式
            print("\n扫描将要清理的数据...")
            preview = preview_incomplete_data(session, checker, today)

            total_to_delete = 0
            for period, info in preview.items():
                if info["count"] > 0:
                    print(f"\n[{period.upper()}]")
                    print(f"  将要删除: {info['count']} 条记录")
                    print(f"  周期开始: {info['period_start']}")
                    print(f"  原因: {info['reason']}")
                    total_to_delete += info["count"]

            print("\n" + "=" * 60)
            if total_to_delete > 0:
                print(f"总计将要删除: {total_to_delete} 条记录")
                print(
                    "\n如需执行清理，请使用: python scripts/cleanup_incomplete_long_period_kline.py --execute"
                )
            else:
                print("没有发现需要清理的数据")
            print("=" * 60)
        else:
            # 执行模式
            print("\n开始清理数据...")
            total_deleted = 0

            # 清理周线
            print("\n[1/4] 检查周线数据...")
            week_deleted = cleanup_incomplete_week_data(session, checker, today)
            total_deleted += week_deleted

            # 清理月线
            print("\n[2/4] 检查月线数据...")
            month_deleted = cleanup_incomplete_month_data(session, checker, today)
            total_deleted += month_deleted

            # 清理季线
            print("\n[3/4] 检查季线数据...")
            season_deleted = cleanup_incomplete_season_data(session, checker, today)
            total_deleted += season_deleted

            # 清理年线
            print("\n[4/4] 检查年线数据...")
            year_deleted = cleanup_incomplete_year_data(session, checker, today)
            total_deleted += year_deleted

            if total_deleted > 0:
                session.commit()
                print("\n" + "=" * 60)
                print(f"清理完成！共删除 {total_deleted} 条记录")
                print("=" * 60)
            else:
                print("\n" + "=" * 60)
                print("没有发现需要清理的数据")
                print("=" * 60)

    except Exception as e:
        if not dry_run:
            session.rollback()
        print(f"\n清理过程中发生错误: {e}")
        import traceback

        traceback.print_exc()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="清理未走完周期的长周期 K 线数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 预览模式（默认）：查看将要删除的数据
  python scripts/cleanup_incomplete_long_period_kline.py

  # 执行模式：实际删除数据
  python scripts/cleanup_incomplete_long_period_kline.py --execute

  # 指定日期进行测试
  python scripts/cleanup_incomplete_long_period_kline.py --date 2025-03-15
        """,
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="执行实际删除操作（默认仅为预览）",
    )
    parser.add_argument(
        "--date",
        type=str,
        help="指定今天的日期（格式: YYYY-MM-DD，用于测试）",
    )

    args = parser.parse_args()

    today = None
    if args.date:
        today = datetime.strptime(args.date, "%Y-%m-%d").date()

    cleanup_incomplete_long_period_kline(dry_run=not args.execute, today=today)
