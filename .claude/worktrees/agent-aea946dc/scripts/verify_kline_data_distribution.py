#!/usr/bin/env python3
"""验证 K 线数据分布情况.

检查长周期 K 线表中的数据分布，确认清理后的数据状态。
"""

import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.models.kline import (
    KlineWeek,
    KlineMonth,
    KlineSeason,
    KlineYear,
)
from sqlalchemy import func


def check_table_distribution(session, model_class, table_name):
    """检查表的数据分布."""
    print(f"\n【{table_name} 表】")

    # 总记录数
    total_count = session.query(model_class).count()
    print(f"  总记录数: {total_count}")

    if total_count == 0:
        return

    # 证券数量
    symbol_count = session.query(model_class.symbol).distinct().count()
    print(f"  证券数量: {symbol_count}")

    # 时间范围
    min_time = session.query(func.min(model_class.trade_time)).scalar()
    max_time = session.query(func.max(model_class.trade_time)).scalar()
    print(f"  时间范围: {min_time} ~ {max_time}")

    # 按年份统计
    print(f"\n  按年份分布:")
    year_counts = (
        session.query(
            func.extract('year', model_class.trade_time).label('year'),
            func.count().label('count')
        )
        .group_by(func.extract('year', model_class.trade_time))
        .order_by(func.extract('year', model_class.trade_time))
        .all()
    )

    for year, count in year_counts:
        print(f"    {int(year)}: {count} 条")

    # 检查2026年数据（当前未走完的年份）
    current_year_data = (
        session.query(model_class)
        .filter(func.extract('year', model_class.trade_time) == 2026)
        .count()
    )

    if current_year_data > 0:
        print(f"\n  ⚠️  发现 {current_year_data} 条 2026 年数据（本年未结束）")
    else:
        print(f"\n  ✓ 没有 2026 年数据（符合边界检查规则）")


def main():
    print("=" * 80)
    print("K 线数据分布验证")
    print("=" * 80)
    print(f"当前日期: {date.today()}")
    print("-" * 80)

    print("\n初始化数据库连接...")
    db_manager.initialize()

    session = db_manager.get_session()
    try:
        # 检查各长周期表
        check_table_distribution(session, KlineWeek, "周线")
        check_table_distribution(session, KlineMonth, "月线")
        check_table_distribution(session, KlineSeason, "季线")
        check_table_distribution(session, KlineYear, "年线")

        print("\n" + "=" * 80)
        print("验证完成")
        print("=" * 80)

    finally:
        session.close()


if __name__ == "__main__":
    main()
