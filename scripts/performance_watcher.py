"""后台性能监控脚本.

用于监控API调用、批量查询和异步查询的实时性能。
"""

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Thread, Event

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PerformanceWatcher(Thread):
    """性能监控线程."""

    def __init__(self, interval: float = 5.0):
        super().__init__(daemon=True)
        self.interval = interval
        self.stop_event = Event()
        self.stats = {
            'start_time': datetime.now().isoformat(),
            'checks': []
        }
        self.stats_file = Path('logs/performance_stats.json')
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)

    def stop(self):
        """停止监控."""
        self.stop_event.set()

    def run(self):
        """监控循环."""
        logger.info(f"性能监控线程已启动，采样间隔: {self.interval}s")

        while not self.stop_event.is_set():
            self._collect_stats()
            time.sleep(self.interval)

        # 保存最终统计
        self._save_stats()
        logger.info("性能监控线程已停止")

    def _collect_stats(self):
        """收集当前统计信息."""
        check = {
            'timestamp': datetime.now().isoformat(),
            'time_from_start': time.time() - self._start_timestamp
        }
        self.stats['checks'].append(check)

        # 尝试从共享文件读取API调用统计
        api_stats_file = Path('logs/api_stats.json')
        if api_stats_file.exists():
            try:
                with open(api_stats_file) as f:
                    api_stats = json.load(f)
                    check['api_calls'] = api_stats.get('call_count', 0)
                    check['avg_response_time'] = api_stats.get('avg_duration', 0)
            except Exception:
                pass

        logger.info(f"[监控] 运行时间: {check['time_from_start']:.1f}s")

    def _save_stats(self):
        """保存统计信息到文件."""
        with open(self.stats_file, 'w') as f:
            json.dump(self.stats, f, indent=2)
        logger.info(f"性能统计已保存到 {self.stats_file}")

    @property
    def _start_timestamp(self):
        """获取开始时间戳."""
        return datetime.fromisoformat(self.stats['start_time']).timestamp()


def main():
    """主函数."""
    watcher = PerformanceWatcher(interval=5.0)
    watcher.start()

    try:
        # 保持运行直到收到退出信号
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止...")
        watcher.stop()
        watcher.join(timeout=5)


if __name__ == "__main__":
    main()
