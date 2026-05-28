#!/usr/bin/env python3
"""茅台 2016 年 K 线数据完整性检查脚本.

检查茅台（600519.SH）2016 年的月线、季线、年线数据完整性。
"""

import logging
import sys
from datetime import date

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 添加项目根目录到 Python 路径
sys.path.insert(0, "/home/laniakea/Development/galaxy-db-bridge/src")

from galaxy_db_bridge.database.core.connection import db_manager
from galaxy_db_bridge.database.services.kline_completeness_checker import (
    kline_completeness_checker,
)
from galaxy_db_bridge.shared_kernel.enums.interval import Interval


def check_moutai_2016_completeness():
    """检查茅台 2016 年月季年线数据完整性."""
    # 初始化数据库连接
    db_manager.initialize()
    logger.info("数据库连接已初始化")
    # 茅台股票代码
    symbol = "600519.SH"
    start_date = date(2016, 1, 1)
    end_date = date(2016, 12, 31)

    print(f"\n{'=' * 60}")
    print(f"茅台（{symbol}）2016 年数据完整性检查")
    print(f"检查区间：{start_date} ~ {end_date}")
    print(f"{'=' * 60}\n")

    # 需要检查的周期：月线、季线、年线
    intervals = [
        (Interval.MONTH, "月线"),
        (Interval.SEASON, "季线"),
        (Interval.YEAR, "年线"),
    ]

    all_complete = True

    for interval, interval_name in intervals:
        print(f"\n{'-' * 50}")
        print(f"检查 {interval_name}（{interval.value}）数据...")
        print(f"{'-' * 50}")

        try:
            result = kline_completeness_checker.check(
                symbol=symbol,
                interval=interval,
                start_date=start_date,
                end_date=end_date,
            )

            # 输出检查结果
            print(f"  完整性状态：{'✓ 完整' if result.is_complete else '✗ 不完整'}")
            print(f"  覆盖率：{result.coverage_ratio:.2%}")
            print(f"  数据点：{result.total_count - result.missing_count}/{result.total_count}")
            print(f"  缺失数量：{result.missing_count}")
            print(f"  检查方法：{result.check_method}")

            if result.missing_ranges:
                print(f"  缺失区间：")
                for range_start, range_end in result.missing_ranges:
                    if range_start == range_end:
                        print(f"    - {range_start}")
                    else:
                        print(f"    - {range_start} ~ {range_end}")

            if not result.is_complete:
                all_complete = False

        except Exception as e:
            logger.error(f"检查 {interval_name} 数据时出错：{e}")
            all_complete = False

    print(f"\n{'=' * 60}")
    if all_complete:
        print("✓ 所有周期数据完整")
    else:
        print("✗ 存在数据缺失")
    print(f"{'=' * 60}\n")

    return all_complete


if __name__ == "__main__":
    check_moutai_2016_completeness()
