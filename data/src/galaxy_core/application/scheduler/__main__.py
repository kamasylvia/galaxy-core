"""调度器模块入口点，用于 `python -m galaxy_core.application.scheduler` 运行。"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from time import struct_time

# 在导入调度器之前设置日志 - 从配置文件读取
from galaxy_core.shared_kernel.utils.config_loader import get_section
from galaxy_core.shared_kernel.utils.constants import CST, now_cst

if "pytest" not in sys.modules:
    log_config = get_section("logging")
    log_level = log_config.get("level", "INFO").upper()

    # 如果配置了，使用基于日期的目录。文件名时间用北京时间(AGENTS.md 2026-06-25),
    # 而非服务器本地时间(UTC)——审计按文件名时间判定进程实际触发时刻。
    if log_config.get("enable_separate_log_files", False):
        pattern = log_config.get("log_file_pattern", "./logs/{date}/{time}.log")
        current_time = now_cst()
        date_str = current_time.strftime("%Y%m%d")
        time_str = current_time.strftime("%H%M%S")
        log_file_path = pattern.replace("{date}", date_str).replace("{time}", time_str)
    else:
        current_time = now_cst()
        log_file_path = log_config.get("file_path", "./logs/") + (
            f"scheduler-{current_time.strftime('%Y%m%d-%H%M%S')}.log"
        )

    log_file = Path(log_file_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))

    # 清除现有处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    # asctime 用北京时间:默认 converter=time.localtime 返回服务器本地时间(UTC),
    # 改为按 CST 转换,使日志行内时间戳与文件名时间一致(均为北京时间)。

    def _cst_converter(seconds: float | None) -> struct_time:
        # seconds=None 时回退到当前时刻(typeshed 签名允许 None)
        ts = seconds if seconds is not None else datetime.now(CST).timestamp()
        return datetime.fromtimestamp(ts, CST).timetuple()

    formatter.converter = _cst_converter

    # 文件处理器
    # CSTMidnightFileHandler:按北京午夜显式轮转(2026-09-09 替换 TRFH)。
    # 原 TimedRotatingFileHandler(when="midnight", atTime=16:00, utc=False)
    # 在 CPython 3.14 静默停写 48h(9/5~9/8 北京,归档缺失无报错,见 HISTORY);
    # 新处理器每次写入前比对北京日期,跨日归档为 .YYYYMMDD(命名与 TRFH 一致)。
    # 历史:FileHandler 时代进程跨天无限写启动当天文件(2026-08-01 修复引入 TRFH)。
    # 注:base 文件名仍是启动日期目录(进程实例标识),轮转只做内容归档不改路径。
    # 审计 SOP:看日志行内 asctime(北京时间)而非目录名判定实际触发日期。
    from galaxy_core.shared_kernel.utils.log_handlers import CSTMidnightFileHandler
    file_handler = CSTMidnightFileHandler(
        str(log_file),
        backup_count=log_config.get("backup_count", 14),
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(getattr(logging, log_level))
    root_logger.addHandler(file_handler)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, log_level))
    root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)
if "pytest" not in sys.modules:
    logger.info(f"调度器日志初始化完成: {log_file}")

from .scheduler import run_scheduler

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Galaxy DB Bridge 自动同步调度器")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="如果已有调度器在运行，强制终止旧实例后启动新实例",
    )
    args = parser.parse_args()
    asyncio.run(run_scheduler(replace=args.replace))
