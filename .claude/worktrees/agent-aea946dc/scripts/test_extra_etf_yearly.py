#!/usr/bin/env python3
"""测试拉取2021-2023年EXTRA_ETF年线数据并监控性能.

此脚本用于:
1. 拉取2021-2023年的EXTRA_ETF年线数据
2. 监控批量查询和异步查询的性能
3. 生成性能评估报告

使用方法:
    uv run python scripts/test_extra_etf_yearly.py
"""

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# 设置日志
log_dir = Path(__file__).parent.parent / 'logs'
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f'kline_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger(__name__)

from galaxy_db_sync.amazing_data.api.client import AmazingDataClient
from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.shared_kernel.utils import get_valid_symbols_from_input
from galaxy_db_sync.database.services.kline_data_sync import kline_data_sync_service
from galaxy_db_sync.database.services.kline_completeness_checker import kline_completeness_checker
from galaxy_db_sync.shared_kernel.utils.interval_boundary_checker import IntervalBoundaryChecker
from galaxy_db_sync.shared_kernel.enums.interval import Interval

# 导入性能监控 - 使用绝对路径
import sys
sys.path.insert(0, str(Path(__file__).parent))
from performance_monitor import performance_monitor


def setup_environment():
    """设置测试环境."""
    logger.info("=" * 60)
    logger.info("开始设置测试环境")
    logger.info("=" * 60)

    # 初始化数据库
    db_manager.initialize()
    logger.info("数据库已初始化")

    # 初始化AmazingData客户端
    client = AmazingDataClient.from_config()
    logger.info("AmazingData客户端已初始化")

    return client


def get_extra_etf_symbols(start_date: str, end_date: str) -> list[str]:
    """获取EXTRA_ETF证券代码列表 - 使用akshare."""
    logger.info("获取EXTRA_ETF证券代码列表...")

    try:
        import akshare as ak

        # 获取所有 ETF 基金列表
        df = ak.fund_etf_category_sina()

        # 构建代码列表 (格式: code.exchange)
        codes = []
        for _, row in df.iterrows():
            code = str(row['代码'])
            # 去掉可能的前缀
            code = code.replace('sz', '').replace('sh', '').replace('SZ', '').replace('SH', '')

            # 根据代码前缀判断交易所
            if code.startswith('15') or code.startswith('16'):
                codes.append(f"{code}.SZ")
            elif code.startswith('51') or code.startswith('56') or code.startswith('58') or code.startswith('59'):
                codes.append(f"{code}.SH")
            else:
                # 其他情况根据名称判断
                name = str(row.get('名称', ''))
                if 'SH' in name or '上海' in name:
                    codes.append(f"{code}.SH")
                else:
                    codes.append(f"{code}.SZ")

        logger.info(f"从 akshare 获取到 {len(codes)} 个 ETF 代码")
        return codes

    except Exception as e:
        logger.error(f"获取 ETF 代码列表失败: {e}")
        return []


def check_completeness(symbols: list[str], interval: str, start: str, end: str) -> dict:
    """检查数据完整性."""
    logger.info(f"检查 {len(symbols)} 只ETF的{interval}线完整性...")

    completeness_results = {}
    incomplete_symbols = []
    total_missing = 0

    for i, symbol in enumerate(symbols):
        if i % 100 == 0:
            logger.info(f"  已检查 {i}/{len(symbols)}...")

        result = kline_completeness_checker.check(
            symbol=symbol,
            interval=interval,
            start_date=start,
            end_date=end,
        )
        completeness_results[symbol] = result

        if not result.is_complete:
            incomplete_symbols.append(symbol)
            total_missing += result.missing_count

    logger.info(f"完整性检查完成: {len(incomplete_symbols)}/{len(symbols)} 需要同步, 总缺失 {total_missing} 条")
    return completeness_results, incomplete_symbols


def execute_sync_test():
    """执行同步测试."""
    logger.info("=" * 60)
    logger.info("开始执行EXTRA_ETF年线同步测试 (2021-2023)")
    logger.info("=" * 60)

    # 设置环境
    client = setup_environment()

    # 强制初始化全局 amazing_data_client（kline_data_sync_service 使用的）
    from galaxy_db_sync.amazing_data.api.client import amazing_data_client
    # 通过访问属性触发延迟加载初始化
    _ = amazing_data_client._is_logged_in
    logger.info("全局 amazing_data_client 已初始化")

    # 测试参数
    interval = "year"
    start_year = "2021"
    end_year = "2023"

    # 获取ETF列表
    symbols = get_extra_etf_symbols(start_year, end_year)

    if not symbols:
        logger.error("未获取到任何ETF代码")
        return

    # 检查数据完整性
    completeness_results, incomplete_symbols = check_completeness(
        symbols, interval, start_year, end_year
    )

    if not incomplete_symbols:
        logger.info("所有数据已完整，无需同步")
        return

    # 开始性能监控
    logger.info("=" * 60)
    logger.info("开始性能监控")
    logger.info("=" * 60)

    # Patch AmazingDataClient以监控API调用
    performance_monitor.patch_amazing_data_client(AmazingDataClient)
    performance_monitor.start_monitoring(max_workers=5)

    # 执行批量同步
    logger.info(f"开始批量同步 {len(incomplete_symbols)} 只ETF...")

    try:
        start_time = time.perf_counter()

        # 获取SDK interval值
        import AmazingData as ad
        interval_value = ad.constant.Period.year.value

        # 执行批量同步
        result = kline_data_sync_service.batch_sync_kline_data(
            symbols=incomplete_symbols,
            interval=interval,
            start_date=start_year,
            end_date=end_year,
            interval_value=interval_value,
            batch_size=500,
        )

        end_time = time.perf_counter()
        duration = end_time - start_time

        # 记录结果
        performance_monitor.record_sync_result(
            success=result.success_count,
            failed=result.failed_count,
            records=result.synced_records
        )

        logger.info("=" * 60)
        logger.info("同步完成")
        logger.info("=" * 60)
        logger.info(f"总耗时: {duration:.2f}s")
        logger.info(f"成功: {result.success_count}")
        logger.info(f"失败: {result.failed_count}")
        logger.info(f"总记录数: {result.synced_records}")
        logger.info(f"Symbol吞吐量: {len(incomplete_symbols)/duration:.2f} symbols/s")
        logger.info(f"记录吞吐量: {result.synced_records/duration:.2f} records/s")

        if result.failed_codes:
            logger.info(f"失败代码: {result.failed_codes[:10]}...")

    except Exception as e:
        logger.error(f"同步失败: {e}", exc_info=True)
    finally:
        # 结束监控并生成报告
        metrics = performance_monitor.end_monitoring()
        performance_monitor.unpatch_amazing_data_client(AmazingDataClient)

        # 打印详细报告
        logger.info("=" * 60)
        logger.info("性能监控报告")
        logger.info("=" * 60)
        report = metrics.generate_report()
        logger.info("\n" + report)

        # 登出
        from galaxy_db_sync.shared_kernel.utils.config_loader import get_config
        username = get_config("amazing_data", "username")
        client.logout(username)
        logger.info("已登出")


def main():
    """主函数."""
    # 创建日志目录
    log_dir = Path(__file__).parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)

    try:
        execute_sync_test()
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
