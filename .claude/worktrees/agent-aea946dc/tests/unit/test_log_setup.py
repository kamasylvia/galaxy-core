#!/usr/bin/env python3
"""测试日志配置是否正常工作."""

import logging
import os
from pathlib import Path


# 临时模拟配置加载器函数
def get_section(section_name):
    """模拟配置加载器返回配置."""
    if section_name == "logging":
        return {
            "level": "INFO",
            "file_path": "./logs/",
            "max_size": "100MB",
            "backup_count": 5,
            "enable_separate_log_files": True,
            "log_file_pattern": "./logs/{date}/{time}.log",
        }
    return {}


# 从我们的修改中复制setup_logging函数
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
        from datetime import datetime

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

    print(f"日志文件路径: {log_file_path}")

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
    import sys

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, log_level))

    # 添加处理器到根日志记录器
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def test_logging():
    """测试日志功能."""
    setup_logging()

    # 记录一些测试日志
    logger = logging.getLogger(__name__)
    logger.info("测试日志功能")
    logger.info("日志应该被写入按日期时间分目录的文件中")
    logger.warning("这是一个警告消息")
    logger.error("这是一个错误消息")

    print("日志已记录，检查 ./logs/ 目录下的文件结构")


if __name__ == "__main__":
    test_logging()
