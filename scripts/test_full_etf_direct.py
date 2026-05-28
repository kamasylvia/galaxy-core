#!/usr/bin/env python3
"""EXTRA_ETF 全量年线同步 - 使用 AD SDK 获取代码并直接调用 Python API."""

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# 设置日志
log_dir = Path(__file__).parent.parent / 'logs'
log_dir.mkdir(exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = log_dir / f'full_sync_direct_{timestamp}.log'

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

    try:
        from galaxy_db_sync.amazing_data.api.client import amazing_data_client

        # 确保客户端已初始化
        client = amazing_data_client.get_instance()

        # 使用 YYYYMMDD 格式日期
        codes = client.get_hist_code_list(
            security_type='EXTRA_ETF',
            start_date=20210101,  # YYYYMMDD 格式
            end_date=20231231,
            local_path='./cache/'
        )

        logger.info(f"从 AmazingData 获取到 {len(codes)} 个 ETF 代码")
        return codes

    except Exception as e:
        logger.error(f"从 AmazingData 获取 ETF 代码失败: {e}")
        return []


def sync_etf_batch(codes: list[str], interval: str, start: str, end: str) -> dict:
    """同步一批 ETF 代码.

    直接调用 Python API 而不是通过 CLI。
    """
    import AmazingData as ad
    from galaxy_db_sync.database.services.kline_data_sync import kline_data_sync_service
    from galaxy_db_sync.database.services.kline_completeness_checker import kline_completeness_checker

    # 转换日期格式
    start_int = int(start) if len(start) == 8 else int(start) * 10000 + 101
    end_int = int(end) if len(end) == 8 else int(end) * 10000 + 1231

    # 获取 SDK interval 值
    interval_value = ad.constant.Period.year.value

    logger.info(f"开始同步 {len(codes)} 只 ETF...")

    # 执行批量同步
    result = kline_data_sync_service.batch_sync_kline_data(
        symbols=codes,
        interval=interval,
        start_date=str(start_int),
        end_date=str(end_int),
        interval_value=interval_value,
        batch_size=100,
    )

    return {
        'success_count': result.success_count,
        'failed_count': result.failed_count,
        'synced_records': result.synced_records,
        'failed_codes': result.failed_codes,
    }


def run_full_sync(codes: list[str], interval: str, start: str, end: str) -> dict:
    """执行全量同步."""
    logger.info("=" * 70)
    logger.info(f"开始同步 {len(codes)} 只 ETF")
    logger.info("=" * 70)

    total_start = time.perf_counter()
    total_api_calls = 0
    total_records = 0
    batch_num = 0

    # 分批处理，每批 100 只
    batch_size = 100

    for i in range(0, len(codes), batch_size):
        batch_num += 1
        batch = codes[i:i + batch_size]

        logger.info(f"\n批次 {batch_num}/{(len(codes) + batch_size - 1) // batch_size}: {len(batch)} 只 ETF")

        batch_start = time.perf_counter()

        try:
            result = sync_etf_batch(batch, interval, start, end)
            batch_duration = time.perf_counter() - batch_start

            total_records += result['synced_records']
            total_api_calls += 1  # 每批一次 API 调用

            logger.info(f"批次 {batch_num} 完成:")
            logger.info(f"  耗时: {batch_duration:.2f}s")
            logger.info(f"  成功: {result['success_count']}")
            logger.info(f"  失败: {result['failed_count']}")
            logger.info(f"  记录数: {result['synced_records']}")

            if result['failed_codes']:
                logger.warning(f"  失败代码: {result['failed_codes'][:5]}...")

            # 短暂等待避免限流
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"批次 {batch_num} 执行失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

    total_duration = time.perf_counter() - total_start

    return {
        'total_codes': len(codes),
        'batches': batch_num,
        'total_duration': total_duration,
        'api_calls': total_api_calls,
        'total_records': total_records,
    }


def main():
    """主函数."""
    logger.info("=" * 70)
    logger.info("EXTRA_ETF 全量年线同步 (直接 Python API 调用)")
    logger.info("=" * 70)

    # 初始化数据库
    from galaxy_db_sync.database.core.connection import db_manager
    db_manager.initialize()
    logger.info("数据库已初始化")

    # 获取 ETF 代码
    codes = get_etf_codes_from_ad()

    if not codes:
        logger.error("未获取到任何 ETF 代码")
        return

    logger.info(f"准备同步 {len(codes)} 只 ETF 的 2021-2023 年线数据")

    # 执行同步
    result = run_full_sync(
        codes=codes,
        interval='year',
        start='2021',
        end='2023'
    )

    # 生成报告
    logger.info("\n" + "=" * 70)
    logger.info("同步完成报告")
    logger.info("=" * 70)
    logger.info(f"总 ETF 数: {result['total_codes']}")
    logger.info(f"总批次数: {result['batches']}")
    logger.info(f"总耗时: {result['total_duration']:.2f}s ({result['total_duration']/60:.2f}分钟)")
    logger.info(f"API 调用次数: {result['api_calls']}")
    logger.info(f"总记录数: {result['total_records']}")
    logger.info(f"平均每批耗时: {result['total_duration']/result['batches']:.2f}s")
    logger.info(f"平均每只耗时: {result['total_duration']/result['total_codes']:.2f}s")
    logger.info(f"吞吐量: {result['total_codes']/result['total_duration']:.2f} 只/秒")
    logger.info("=" * 70)

    # 保存结果
    import json
    stats_file = log_dir / f'full_sync_direct_{timestamp}.json'
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
