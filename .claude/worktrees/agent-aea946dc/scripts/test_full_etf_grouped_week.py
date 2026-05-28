#!/usr/bin/env python3
"""EXTRA_ETF 全量周线同步 - 按数据缺口分组批量同步.

使用 AD SDK 获取代码，按缺失区间分组，相同缺口的一次性批量查询。
"""

import logging
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import AmazingData as ad
import pandas as pd

# 设置日志
log_dir = Path(__file__).parent.parent / 'logs'
log_dir.mkdir(exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = log_dir / f'full_sync_grouped_{timestamp}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger(__name__)


def get_etf_codes_from_ad() -> list[str]:
    """使用 AmazingData SDK 获取 ETF 代码列表."""
    logger.info("使用 AmazingData SDK 获取 ETF 代码列表...")

    from galaxy_db_sync.amazing_data.api.client import amazing_data_client

    client = amazing_data_client.get_instance()

    # 获取 2013-2024 年所有存在过的 ETF 代码
    codes = client.get_hist_code_list(
        security_type='EXTRA_ETF',
        start_date=20130101,  # 2013年1月1日
        end_date=20241231,    # 2024年12月31日
        local_path='./cache/'
    )

    logger.info(f"从 AmazingData 获取到 {len(codes)} 个 ETF 代码")
    return codes


def check_completeness_for_symbols(
    symbols: list[str], interval: str, start_date: str, end_date: str
) -> dict:
    """批量检查数据完整性.

    优化：先统一获取交易日历缓存，避免每只ETF都查询数据库。
    """
    from galaxy_db_sync.database.services.kline_completeness_checker import (
        kline_completeness_checker,
    )
    from galaxy_db_sync.database.services.trading_calendar import trading_calendar_service

    logger.info(f"检查 {len(symbols)} 只 ETF 的数据完整性...")

    # 优化：先统一获取交易日历，建立缓存
    # 解析日期范围
    start_year = int(start_date)
    end_year = int(end_date)
    from datetime import date
    start_dt = date(start_year, 1, 1)
    end_dt = date(end_year, 12, 31)

    logger.info(f"  预加载交易日历: {start_dt} ~ {end_dt}")
    trading_calendar_service.get_trading_days(start_dt, end_dt)
    logger.info(f"  交易日历缓存完成")

    results = {}
    for i, symbol in enumerate(symbols):
        if i % 500 == 0:
            logger.info(f"  已检查 {i}/{len(symbols)}...")

        result = kline_completeness_checker.check(
            symbol=symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
        )
        results[symbol] = result

    # 统计
    complete_count = sum(1 for r in results.values() if r.is_complete)
    incomplete_count = len(results) - complete_count
    logger.info(f"完整性检查完成: {complete_count} 只完整, {incomplete_count} 只缺失")

    return results


def group_symbols_by_missing_ranges(
    completeness_results: dict, interval_value: int
) -> dict[tuple[int, int, int], list[str]]:
    """按缺失区间对 symbol 进行分组.

    Returns:
        dict: key 为 (begin_date, end_date, interval_value), value 为 symbol 列表
    """
    range_groups = defaultdict(list)

    for symbol, result in completeness_results.items():
        if result.is_complete:
            continue

        for range_start, range_end in result.missing_ranges:
            begin_int = int(range_start.strftime("%Y%m%d"))
            end_int = int(range_end.strftime("%Y%m%d"))
            key = (begin_int, end_int, interval_value)
            range_groups[key].append(symbol)

    return dict(range_groups)


def fetch_kline_batch(
    symbols: list[str], begin_date: int, end_date: int, interval: int
) -> dict[str, pd.DataFrame]:
    """批量获取 K 线数据.

    Returns:
        dict: {symbol: DataFrame}
    """
    from galaxy_db_sync.amazing_data.api.client import amazing_data_client

    client = amazing_data_client.get_instance()

    try:
        result = client.query_kline(
            code_list=symbols,
            begin_date=begin_date,
            end_date=end_date,
            interval=interval,
        )
        return result
    except Exception as e:
        logger.error(f"API 查询失败: {e}")
        return {}


def save_kline_data(
    data: dict[str, pd.DataFrame], interval: str
) -> int:
    """保存 K 线数据到数据库.

    Returns:
        int: 保存的记录数
    """
    from galaxy_db_sync.database.services.kline import kline_service

    return kline_service.batch_save_kline_to_db(data, interval)


def run_grouped_sync(
    symbols: list[str], interval: str, start: str, end: str
) -> dict:
    """按缺失区间分组执行同步.

    Args:
        symbols: 证券代码列表
        interval: K线周期
        start: 开始日期 (YYYY)
        end: 结束日期 (YYYY)

    Returns:
        统计结果
    """
    logger.info("=" * 70)
    logger.info(f"开始分组同步 {len(symbols)} 只 ETF")
    logger.info("=" * 70)

    # 1. 检查完整性
    completeness_results = check_completeness_for_symbols(symbols, interval, start, end)

    # 2. 按缺失区间分组
    interval_value = ad.constant.Period.week.value
    range_groups = group_symbols_by_missing_ranges(completeness_results, interval_value)

    if not range_groups:
        logger.info("所有数据已完整，无需同步")
        return {
            'total_symbols': len(symbols),
            'groups': 0,
            'api_calls': 0,
            'total_duration': 0,
            'total_records': 0,
        }

    logger.info(f"分组完成: {len(range_groups)} 个不同的缺失区间")
    for key, syms in sorted(range_groups.items()):
        logger.info(f"  区间 {key[0]}-{key[1]}: {len(syms)} 只 ETF")

    # 3. 按组同步
    total_start = time.perf_counter()
    total_api_calls = 0
    total_records = 0

    for i, (key, group_symbols) in enumerate(sorted(range_groups.items()), 1):
        begin_date, end_date, _ = key

        logger.info(f"\n处理第 {i}/{len(range_groups)} 组:")
        logger.info(f"  区间: {begin_date} - {end_date}")
        logger.info(f"  ETF数: {len(group_symbols)}")

        batch_start = time.perf_counter()

        # API 批量查询
        data = fetch_kline_batch(group_symbols, begin_date, end_date, interval_value)
        total_api_calls += 1

        # 保存数据
        if data:
            records_saved = save_kline_data(data, interval)
            total_records += records_saved
            logger.info(f"  保存 {records_saved} 条记录")

        batch_duration = time.perf_counter() - batch_start
        logger.info(f"  耗时: {batch_duration:.2f}s")

        # 短暂等待
        time.sleep(0.5)

    total_duration = time.perf_counter() - total_start

    return {
        'total_symbols': len(symbols),
        'groups': len(range_groups),
        'api_calls': total_api_calls,
        'total_duration': total_duration,
        'total_records': total_records,
    }


def main():
    """主函数."""
    logger.info("=" * 70)
    logger.info("EXTRA_ETF 全量周线同步 (按缺失区间分组)")
    logger.info("=" * 70)

    # 初始化数据库
    from galaxy_db_sync.database.core.connection import db_manager
    db_manager.initialize()
    logger.info("数据库已初始化")

    # 获取 ETF 代码 (仅使用 AD SDK)
    codes = get_etf_codes_from_ad()

    if not codes:
        logger.error("未获取到任何 ETF 代码")
        return

    # 周线同步到上年末 (2024-12-31)，所以 end_date 设为 2024
    end_year = datetime.now().year - 1  # 上年
    logger.info(f"准备同步 {len(codes)} 只 ETF 的 2013-{end_year} 周线数据")

    # 执行分组同步
    result = run_grouped_sync(
        symbols=codes,
        interval='week',
        start='2013',
        end=str(end_year)
    )

    # 生成报告
    logger.info("\n" + "=" * 70)
    logger.info("同步完成报告")
    logger.info("=" * 70)
    logger.info(f"总 ETF 数: {result['total_symbols']}")
    logger.info(f"分组数: {result['groups']}")
    logger.info(f"总耗时: {result['total_duration']:.2f}s ({result['total_duration']/60:.2f}分钟)")
    logger.info(f"API 调用次数: {result['api_calls']}")
    logger.info(f"总记录数: {result['total_records']}")
    logger.info(f"平均每组耗时: {result['total_duration']/result['groups']:.2f}s" if result['groups'] > 0 else "N/A")
    logger.info(f"平均每只耗时: {result['total_duration']/result['total_symbols']:.2f}s")
    logger.info(f"吞吐量: {result['total_symbols']/result['total_duration']:.2f} 只/秒")
    logger.info("=" * 70)

    # 保存结果
    import json
    stats_file = log_dir / f'full_sync_grouped_{timestamp}.json'
    with open(stats_file, 'w') as f:
        json.dump(result, f, indent=2)
    logger.info(f"统计信息已保存到: {stats_file}")

    # 登出
    from galaxy_db_sync.shared_kernel.utils.config_loader import get_config
    from galaxy_db_sync.amazing_data.api.client import amazing_data_client
    username = get_config("amazing_data", "username")
    amazing_data_client.logout(username)
    logger.info("已登出")


if __name__ == "__main__":
    main()
