#!/usr/bin/env python
"""
从 akshare 拉取 2010-01-01 至 2026-12-31 的交易日历数据并保存到数据库。

使用方法:
    python scripts/fetch_trading_calendar_2010_2026.py
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from galaxy_db_sync.database.services.trading_calendar import TradingCalendarService


async def main():
    """主函数：拉取 2010-2026 年的交易日历数据。"""
    print("=" * 60)
    print("交易日历数据拉取脚本")
    print("数据范围: 2010-01-01 至 2026-12-31")
    print("=" * 60)

    service = TradingCalendarService()

    # 定义年份范围
    start_year = 2010
    end_year = 2026

    print(f"\n开始同步 {start_year} 至 {end_year} 年的交易日历数据...\n")

    try:
        # 同步指定年份范围的交易日历
        result = await service.sync_years(start_year=start_year, end_year=end_year)

        print("\n" + "=" * 60)
        print("同步完成!")
        print(f"总计处理: {result.get('total', 0)} 条记录")
        print(f"新增: {result.get('added', 0)} 条")
        print(f"更新: {result.get('updated', 0)} 条")
        print(f"跳过: {result.get('skipped', 0)} 条")
        print("=" * 60)

    except Exception as e:
        print(f"\n错误: 同步过程中发生异常: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
