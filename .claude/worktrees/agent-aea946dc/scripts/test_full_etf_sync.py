#!/usr/bin/env python3
"""EXTRA_ETF 全量年线同步性能测试.

同步所有 EXTRA_ETF (约382只) 的 2021-2023 年线数据，详细监控性能指标。
"""

import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Thread, Event

# 设置日志
log_dir = Path(__file__).parent.parent / 'logs'
log_dir.mkdir(exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = log_dir / f'full_sync_yearly_{timestamp}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger(__name__)

# 性能指标收集
performance_stats = {
    'start_time': None,
    'end_time': None,
    'api_calls': 0,
    'api_durations': [],
    'batch_sizes': [],
    'records_synced': 0,
    'errors': [],
}


class LogMonitor(Thread):
    """日志监控线程，实时解析性能指标."""

    def __init__(self, log_file_path: Path):
        super().__init__(daemon=True)
        self.log_file_path = log_file_path
        self.stop_event = Event()
        self.position = 0

    def stop(self):
        self.stop_event.set()

    def run(self):
        """监控日志文件变化."""
        logger.info("日志监控线程已启动")

        while not self.stop_event.is_set():
            try:
                if self.log_file_path.exists():
                    with open(self.log_file_path, 'r') as f:
                        f.seek(self.position)
                        new_lines = f.readlines()
                        self.position = f.tell()

                        for line in new_lines:
                            self._parse_log_line(line)

            except Exception as e:
                logger.debug(f"日志监控异常: {e}")

            time.sleep(0.5)

        logger.info("日志监控线程已停止")

    def _parse_log_line(self, line: str):
        """解析日志行提取性能指标."""
        # 解析 API 调用
        if 'Fetched kline for' in line:
            # 提取: Fetched kline for X codes from Y to Z
            try:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'for':
                        count = int(parts[i + 1])
                        performance_stats['api_calls'] += 1
                        performance_stats['batch_sizes'].append(count)
                        logger.info(f"[监控] 检测到 API 调用: {count} 只证券")
                        break
            except Exception:
                pass

        # 解析同步记录数
        if '批次完成: 保存' in line or 'synced_records' in line:
            try:
                # 尝试提取记录数
                import re
                match = re.search(r'(\d+)\s*条记录', line)
                if match:
                    records = int(match.group(1))
                    performance_stats['records_synced'] += records
            except Exception:
                pass

        # 记录错误
        if 'ERROR' in line:
            performance_stats['errors'].append(line.strip()[:200])


def run_full_sync() -> dict:
    """执行全量同步.

    Returns:
        性能指标字典
    """
    cmd = [
        'uv', 'run', 'python', '-m', 'galaxy_db_sync', 'kline',
        'EXTRA_ETF',
        '--interval', 'year',
        '--start', '2021',
        '--end', '2023',
    ]

    logger.info("=" * 70)
    logger.info("EXTRA_ETF 全量年线同步测试")
    logger.info("=" * 70)
    logger.info(f"命令: {' '.join(cmd)}")
    logger.info(f"预计同步: ~382 只 ETF")
    logger.info(f"时间范围: 2021-2023 (3年)")
    logger.info("=" * 70)

    # 记录开始时间
    performance_stats['start_time'] = datetime.now().isoformat()
    start_ts = time.perf_counter()

    try:
        # 启动日志监控
        log_monitor = LogMonitor(log_file)
        log_monitor.start()

        # 执行命令
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30分钟超时
            cwd=Path(__file__).parent.parent
        )

        # 停止日志监控
        log_monitor.stop()
        log_monitor.join(timeout=5)

        end_ts = time.perf_counter()
        performance_stats['end_time'] = datetime.now().isoformat()
        duration = end_ts - start_ts

        # 记录输出到日志
        logger.info("\n" + "=" * 70)
        logger.info("命令 STDOUT:")
        logger.info(result.stdout)
        if result.stderr:
            logger.info("\n命令 STDERR:")
            logger.info(result.stderr)
        logger.info("=" * 70)

        return {
            'success': result.returncode == 0,
            'duration': duration,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
        }

    except subprocess.TimeoutExpired:
        logger.error("命令执行超时 (30分钟)")
        return {'success': False, 'duration': 1800, 'error': 'timeout'}
    except Exception as e:
        logger.error(f"命令执行失败: {e}")
        return {'success': False, 'duration': 0, 'error': str(e)}


def generate_report(result: dict) -> str:
    """生成性能报告."""
    duration = result.get('duration', 0)

    # 计算统计指标
    api_calls = performance_stats['api_calls']
    batch_sizes = performance_stats['batch_sizes']
    avg_batch_size = sum(batch_sizes) / len(batch_sizes) if batch_sizes else 0
    max_batch_size = max(batch_sizes) if batch_sizes else 0
    total_symbols = sum(batch_sizes) if batch_sizes else 0

    report_lines = [
        "\n" + "=" * 70,
        "EXTRA_ETF 全量年线同步性能报告",
        "=" * 70,
        f"测试时间: {performance_stats['start_time']}",
        f"完成时间: {performance_stats['end_time']}",
        "",
        "【总体指标】",
        f"  执行结果: {'成功' if result.get('success') else '失败'}",
        f"  总耗时: {duration:.2f} 秒 ({duration/60:.2f} 分钟)",
        f"  返回码: {result.get('returncode', 'N/A')}",
        "",
        "【批量同步指标】",
        f"  API 调用次数: {api_calls}",
        f"  总证券数: {total_symbols}",
        f"  平均每批: {avg_batch_size:.1f} 只",
        f"  最大批次: {max_batch_size} 只",
        f"  平均每批耗时: {duration/api_calls:.2f} 秒" if api_calls > 0 else "  平均每批耗时: N/A",
        "",
        "【吞吐量指标】",
        f"  证券吞吐量: {total_symbols/duration:.2f} 只/秒" if duration > 0 else "  证券吞吐量: N/A",
        f"  记录吞吐量: {performance_stats['records_synced']/duration:.2f} 条/秒" if duration > 0 else "  记录吞吐量: N/A",
        "",
    ]

    if performance_stats['errors']:
        report_lines.extend([
            "【错误统计】",
            f"  错误数量: {len(performance_stats['errors'])}",
            "  错误样本 (前5条):",
        ])
        for i, error in enumerate(performance_stats['errors'][:5], 1):
            report_lines.append(f"    {i}. {error[:100]}")

    report_lines.extend([
        "",
        "【性能对比】",
        "  单只股票同步 (预估): 3.38 秒/只",
        f"  批量同步实际: {duration:.2f} 秒/{total_symbols}只",
    ])

    if duration > 0 and total_symbols > 0:
        serial_time = total_symbols * 3.38
        speedup = serial_time / duration
        report_lines.extend([
            f"  串行预估时间: {serial_time:.2f} 秒",
            f"  实际节省时间: {serial_time - duration:.2f} 秒",
            f"  性能提升倍数: {speedup:.1f}x",
        ])

    report_lines.append("=" * 70)

    return "\n".join(report_lines)


def save_stats():
    """保存统计信息到 JSON 文件."""
    stats_file = log_dir / f'full_sync_stats_{timestamp}.json'
    with open(stats_file, 'w') as f:
        json.dump(performance_stats, f, indent=2)
    logger.info(f"统计信息已保存到: {stats_file}")


def main():
    """主函数."""
    logger.info("启动 EXTRA_ETF 全量年线同步测试...")

    # 执行同步
    result = run_full_sync()

    # 生成报告
    report = generate_report(result)
    logger.info(report)

    # 保存统计
    save_stats()

    # 保存报告
    report_file = log_dir / f'full_sync_report_{timestamp}.md'
    with open(report_file, 'w') as f:
        f.write(report)
    logger.info(f"报告已保存到: {report_file}")

    logger.info("\n测试完成!")


if __name__ == "__main__":
    main()
