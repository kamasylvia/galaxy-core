"""CLI 命令入口."""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

from galaxy_db_bridge.application.kline.command import (
    create_kline_parser,
    handle_kline_command,
)
from galaxy_db_bridge.application.calendar.command import (
    create_calendar_parser,
    handle_calendar_command,
)
from galaxy_db_bridge.shared_kernel.utils.config_loader import get_section


# 配置日志
def setup_logging():
    """根据配置文件设置日志"""
    log_config = get_section("logging")

    # 获取日志配置
    log_level = log_config.get("level", "INFO").upper()

    # 检查是否启用分离日志文件功能
    enable_separate_logs = log_config.get("enable_separate_log_files", False)

    if enable_separate_logs:
        # 按日期时间生成日志文件路径
        log_file_pattern = log_config.get(
            "log_file_pattern", "./logs/{date}/{time}.log"
        )
        current_time = datetime.now()
        date_str = current_time.strftime("%Y%m%d")
        time_str = current_time.strftime("%H%M%S")

        # 替换路径中的占位符
        log_file_path = log_file_pattern.format(date=date_str, time=time_str)
    else:
        # 传统模式
        log_file_path = log_config.get("file_path", "./data/logs/app.log")
        max_size = log_config.get("max_size", "100MB")
        backup_count = log_config.get("backup_count", 5)

        # 解析最大文件大小（简单处理，只支持MB单位）
        max_bytes = 100 * 1024 * 1024  # 默认100MB
        if "MB" in max_size.upper():
            try:
                size_value = int(max_size.upper().replace("MB", "").strip())
                max_bytes = size_value * 1024 * 1024
            except ValueError:
                pass  # 使用默认值

        # 确保日志目录存在
        log_file = Path(log_file_path)

        # 检查log_file_path是否是一个目录
        if log_file.is_dir():
            # 如果是目录，则添加默认文件名
            log_file = log_file / "app.log"
            log_file_path = str(log_file)

    # 确保日志目录存在
    log_file = Path(log_file_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))

    # 清除现有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 创建格式器
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 根据配置选择处理器类型
    if enable_separate_logs:
        # 使用普通文件处理器（单次运行写入单个文件）
        from logging import FileHandler

        file_handler = FileHandler(log_file_path, encoding="utf-8")
    else:
        # 使用轮转文件处理器（传统的单文件轮转）
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )

    file_handler.setFormatter(formatter)
    file_handler.setLevel(getattr(logging, log_level))

    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, log_level))

    # 添加处理器到根日志记录器
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


setup_logging()
logger = logging.getLogger(__name__)


def main() -> int:
    """CLI 主入口."""
    parser = argparse.ArgumentParser(
        prog="galaxy-data-ingest",
        description="银河证券AmazingData数据接入工具",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 注册各命令解析器
    create_kline_parser(subparsers)
    create_calendar_parser(subparsers)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    print(f"执行命令: {args.command}")
    print(f"参数: {args}")

    # 执行对应的命令
    if args.command == "kline":
        return handle_kline_command(args)
    elif args.command == "calendar":
        return handle_calendar_command(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
