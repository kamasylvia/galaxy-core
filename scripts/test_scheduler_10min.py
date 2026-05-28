#!/usr/bin/env python
"""测试用自动同步调度器 - 每10分钟触发一次.

用途：
    用于测试验证自动同步流程，发送近10交易日范围，
    内部完整性检查自动识别缺失区间。

使用：
    python scripts/test_scheduler_10min.py

停止：
    Ctrl+C 或 kill 进程
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timedelta, date
from pathlib import Path

# Setup logging
log_dir = Path("./logs/scheduler/")
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / f"test-scheduler-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
file_handler.setFormatter(formatter)
root_logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)

from galaxy_db_sync.application.kline.command import handle_kline_command_async
import argparse

INTERVAL_MINUTES = 10  # 每10分钟触发
CHECK_TRADING_DAYS = 10  # 近10个交易日范围


class TestScheduler:
    """测试调度器 - 近10交易日范围同步."""

    def __init__(self):
        self._running = False
        from galaxy_db_sync.database.core.connection import db_manager
        from galaxy_db_sync.database.core.async_connection import async_db_manager
        db_manager.initialize()
        async_db_manager.initialize()

    async def run_forever(self):
        """每10分钟触发近10交易日范围同步."""
        self._running = True
        logger.info(f"测试调度器启动，每 {INTERVAL_MINUTES} 分钟触发一次")
        logger.info(f"同步范围: 近 {CHECK_TRADING_DAYS} 个交易日")
        logger.info(f"日志文件: {log_file}")

        while self._running:
            now = datetime.now()
            today = now.date()
            logger.info(f"=== 触发同步 @ {now.strftime('%Y-%m-%d %H:%M:%S')} ===")

            try:
                # 计算日期范围：近10个交易日
                # 简化处理：往前推约15天确保覆盖10个交易日
                start_date = (today - timedelta(days=15)).strftime("%Y%m%d")
                end_date = today.strftime("%Y%m%d")

                logger.info(f"日期范围: {start_date} ~ {end_date}")

                # 构造参数，调用 CLI 处理逻辑
                # CLI 内部有完整性检查，自动处理缺失区间
                args = argparse.Namespace(
                    symbols="EXTRA_ETF",
                    interval="day",
                    start=start_date,
                    end=end_date,
                )

                result = await handle_kline_command_async(args)
                logger.info(f"同步结果: 返回码 {result}")

                logger.info(f"同步完成，等待 {INTERVAL_MINUTES} 分钟后再次触发...")

            except Exception as e:
                logger.error(f"同步失败: {e}")
                import traceback
                traceback.print_exc()

            await asyncio.sleep(INTERVAL_MINUTES * 60)

    async def stop(self):
        """停止调度器."""
        logger.info("停止测试调度器...")
        self._running = False
        from galaxy_db_sync.database.core.async_connection import async_db_manager
        await async_db_manager.close()
        logger.info("已停止")


def main():
    scheduler = TestScheduler()

    def signal_handler(sig, frame):
        logger.info("收到停止信号")
        asyncio.run(scheduler.stop())
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("启动测试调度器...")
    asyncio.run(scheduler.run_forever())


if __name__ == "__main__":
    main()