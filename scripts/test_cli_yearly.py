#!/usr/bin/env python3
"""使用 CLI 命令测试 EXTRA_ETF 年线同步并监控性能.

此脚本通过调用 CLI 命令来执行同步，避免直接操作内部客户端实例的复杂性。
"""

import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# 设置日志
log_dir = Path(__file__).parent.parent / 'logs'
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f'cli_test_yearly_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger(__name__)


def run_cli_command(symbols: str, interval: str, start: str, end: str = None) -> dict:
    """运行 CLI 命令并监控性能.

    Args:
        symbols: 证券代码或类型
        interval: K线周期
        start: 开始日期
        end: 结束日期

    Returns:
        性能指标字典
    """
    cmd = [
        'uv', 'run', 'python', '-m', 'galaxy_db_sync', 'kline',
        symbols,
        '--interval', interval,
        '--start', start,
    ]

    if end:
        cmd.extend(['--end', end])

    logger.info("=" * 60)
    logger.info(f"执行命令: {' '.join(cmd)}")
    logger.info("=" * 60)

    start_time = time.perf_counter()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10分钟超时
            cwd=Path(__file__).parent.parent
        )

        end_time = time.perf_counter()
        duration = end_time - start_time

        logger.info(f"命令执行完成，耗时: {duration:.2f}s")
        logger.info(f"返回码: {result.returncode}")

        # 记录输出
        if result.stdout:
            logger.info("STDOUT:\n" + result.stdout)
        if result.stderr:
            logger.info("STDERR:\n" + result.stderr)

        return {
            'success': result.returncode == 0,
            'duration': duration,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode,
        }

    except subprocess.TimeoutExpired:
        logger.error("命令执行超时")
        return {'success': False, 'duration': 600, 'error': 'timeout'}
    except Exception as e:
        logger.error(f"命令执行失败: {e}")
        return {'success': False, 'duration': 0, 'error': str(e)}


def main():
    """主函数."""
    logger.info("=" * 60)
    logger.info("EXTRA_ETF 年线同步测试 (2021-2023)")
    logger.info("=" * 60)

    # 测试参数
    test_cases = [
        {
            'name': '单只股票2021-2023年线同步',
            'symbols': '510050.SH',
            'interval': 'year',
            'start': '2021',
            'end': '2023',
        },
        {
            'name': '多只股票2021-2023年线同步',
            'symbols': '[510050.SH,510500.SH,510300.SH,510330.SH,510900.SH]',
            'interval': 'year',
            'start': '2021',
            'end': '2023',
        },
    ]

    results = []

    for test_case in test_cases:
        logger.info(f"\n开始测试: {test_case['name']}")

        result = run_cli_command(
            symbols=test_case['symbols'],
            interval=test_case['interval'],
            start=test_case['start'],
            end=test_case['end'],
        )

        results.append({
            'name': test_case['name'],
            **result,
        })

        # 等待一段时间再执行下一个测试
        time.sleep(2)

    # 生成汇总报告
    logger.info("\n" + "=" * 60)
    logger.info("测试汇总报告")
    logger.info("=" * 60)

    for result in results:
        logger.info(f"\n测试: {result['name']}")
        logger.info(f"  成功: {result['success']}")
        logger.info(f"  耗时: {result['duration']:.2f}s")
        if 'error' in result:
            logger.info(f"  错误: {result['error']}")

    # 计算统计信息
    total_tests = len(results)
    successful_tests = sum(1 for r in results if r['success'])
    total_duration = sum(r['duration'] for r in results)

    logger.info(f"\n总体统计:")
    logger.info(f"  总测试数: {total_tests}")
    logger.info(f"  成功: {successful_tests}")
    logger.info(f"  失败: {total_tests - successful_tests}")
    logger.info(f"  总耗时: {total_duration:.2f}s")

    logger.info("\n" + "=" * 60)
    logger.info("测试完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
