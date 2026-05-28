#!/usr/bin/env python3
"""检查未走完周期的长周期 K 线数据详情.

验证：理论上一个周期 K 线表内，一个证券代码对应的未完成记录只有一条。
"""

import os
import sys
from datetime import date, datetime
from collections import defaultdict

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.models.kline import (
    KlineSeason,
    KlineYear,
)
from galaxy_db_sync.shared_kernel.enums.interval import Interval
from galaxy_db_sync.shared_kernel.utils.interval_boundary_checker import (
    IntervalBoundaryChecker,
)


def check_incomplete_data_detail(session, checker: IntervalBoundaryChecker, today: date):
    """检查未走完周期数据的详情."""
    print("=" * 80)
    print("未走完周期 K 线数据详情检查")
    print("=" * 80)
    print(f"参考日期: {today}")
    print("-" * 80)

    # 检查季线
    print("\n【季线数据检查】")
    quarter = (today.month - 1) // 3 + 1
    start_month = (quarter - 1) * 3 + 1
    current_quarter_start = today.replace(month=start_month, day=1)

    if quarter == 4:
        next_quarter_start = date(today.year + 1, 1, 1)
    else:
        next_quarter_start = date(today.year, quarter * 3 + 1, 1)

    if not checker.is_interval_complete(Interval.SEASON, current_quarter_start, today):
        print(f"  本季开始: {current_quarter_start}")
        print(f"  本季结束标志: {next_quarter_start}")

        records = (
            session.query(KlineSeason.symbol, KlineSeason.trade_time)
            .filter(
                KlineSeason.trade_time
                >= datetime.combine(current_quarter_start, datetime.min.time())
            )
            .order_by(KlineSeason.symbol, KlineSeason.trade_time)
            .all()
        )

        if records:
            # 按 symbol 分组统计
            symbol_count = defaultdict(list)
            for symbol, trade_time in records:
                symbol_count[symbol].append(trade_time)

            print(f"  总记录数: {len(records)}")
            print(f"  涉及证券数: {len(symbol_count)}")

            # 检查是否有证券有多条记录
            multi_record_symbols = {
                s: times for s, times in symbol_count.items() if len(times) > 1
            }
            if multi_record_symbols:
                print(
                    f"\n  ⚠️  发现 {len(multi_record_symbols)} 个证券有多条未走完周期记录（理论上应该只有1条）："
                )
                for symbol, times in list(multi_record_symbols.items())[:5]:  # 只显示前5个
                    print(f"    - {symbol}: {len(times)} 条记录")
                    for t in times:
                        print(f"        trade_time: {t}")
                if len(multi_record_symbols) > 5:
                    print(f"    ... 还有 {len(multi_record_symbols) - 5} 个证券")
            else:
                print(f"\n  ✓ 每个证券只有1条未走完周期记录，符合预期")

            # 显示部分数据示例
            print(f"\n  数据示例（前10条）：")
            for symbol, times in list(symbol_count.items())[:10]:
                print(f"    - {symbol}: trade_time={times[0]}")
        else:
            print("  没有未走完的季线数据")

    # 检查年线
    print("\n【年线数据检查】")
    current_year_start = today.replace(month=1, day=1)

    if not checker.is_interval_complete(Interval.YEAR, current_year_start, today):
        print(f"  本年开始: {current_year_start}")
        next_year_start = date(today.year + 1, 1, 1)
        print(f"  本年结束标志: {next_year_start}")

        records = (
            session.query(KlineYear.symbol, KlineYear.trade_time)
            .filter(
                KlineYear.trade_time
                >= datetime.combine(current_year_start, datetime.min.time())
            )
            .order_by(KlineYear.symbol, KlineYear.trade_time)
            .all()
        )

        if records:
            # 按 symbol 分组统计
            symbol_count = defaultdict(list)
            for symbol, trade_time in records:
                symbol_count[symbol].append(trade_time)

            print(f"  总记录数: {len(records)}")
            print(f"  涉及证券数: {len(symbol_count)}")

            # 检查是否有证券有多条记录
            multi_record_symbols = {
                s: times for s, times in symbol_count.items() if len(times) > 1
            }
            if multi_record_symbols:
                print(
                    f"\n  ⚠️  发现 {len(multi_record_symbols)} 个证券有多条未走完周期记录（理论上应该只有1条）："
                )
                for symbol, times in list(multi_record_symbols.items())[:5]:  # 只显示前5个
                    print(f"    - {symbol}: {len(times)} 条记录")
                    for t in times:
                        print(f"        trade_time: {t}")
                if len(multi_record_symbols) > 5:
                    print(f"    ... 还有 {len(multi_record_symbols) - 5} 个证券")
            else:
                print(f"\n  ✓ 每个证券只有1条未走完周期记录，符合预期")

            # 显示部分数据示例
            print(f"\n  数据示例（前10条）：")
            for symbol, times in list(symbol_count.items())[:10]:
                print(f"    - {symbol}: trade_time={times[0]}")
        else:
            print("  没有未走完的年线数据")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="检查未走完周期的长周期 K 线数据详情"
    )
    parser.add_argument(
        "--date",
        type=str,
        help="指定今天的日期（格式: YYYY-MM-DD，用于测试）",
    )

    args = parser.parse_args()

    today = date.today()
    if args.date:
        today = datetime.strptime(args.date, "%Y-%m-%d").date()

    print("初始化数据库连接...")
    db_manager.initialize()

    # 创建周期边界检查器
    checker = IntervalBoundaryChecker()

    session = db_manager.get_session()
    try:
        check_incomplete_data_detail(session, checker, today)
    finally:
        session.close()
