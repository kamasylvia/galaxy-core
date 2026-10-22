#!/usr/bin/env python3
"""测试日志配置是否正常工作.

日志写入 pytest tmp_path 隔离目录，不污染生产 ./logs/。
"""

import logging
import re
from datetime import datetime, timedelta
from logging import FileHandler
from pathlib import Path

from galaxy_core.shared_kernel.utils.constants import CST, now_cst


def _build_log_config(log_dir: Path) -> dict:
    """构造 logging 配置，日志目录指向 log_dir."""
    return {
        "level": "INFO",
        "file_path": str(log_dir) + "/",
        "max_size": "100MB",
        "backup_count": 5,
        "enable_separate_log_files": True,
        "log_file_pattern": str(log_dir) + "/{date}/{time}.log",
    }


def setup_logging(log_config: dict) -> Path:
    """根据配置文件设置日志，返回实际日志文件路径."""
    log_level = log_config.get("level", "INFO").upper()

    enable_separate_logs = log_config.get("enable_separate_log_files", False)

    if enable_separate_logs:
        log_file_pattern = log_config.get(
            "log_file_pattern", "./logs/{date}/{time}.log"
        )
        # 文件名时间用北京时间(AGENTS.md 2026-06-25),而非服务器本地时间(UTC)。
        current_time = now_cst()
        date_str = current_time.strftime("%Y%m%d")
        time_str = current_time.strftime("%H%M%S")
        log_file_path = log_file_pattern.format(date=date_str, time=time_str)
    else:
        log_file_path = log_config.get("file_path", "./data/logs/app.log")
        max_size = log_config.get("max_size", "100MB")
        backup_count = log_config.get("backup_count", 5)

        max_bytes = 100 * 1024 * 1024
        if "MB" in max_size.upper():
            try:
                size_value = int(max_size.upper().replace("MB", "").strip())
                max_bytes = size_value * 1024 * 1024
            except ValueError:
                pass

        log_file = Path(log_file_path)
        if log_file.is_dir():
            log_file = log_file / "app.log"
            log_file_path = str(log_file)

    log_file = Path(log_file_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    # asctime 用北京时间:默认 converter=time.localtime 返回服务器本地时间(UTC),
    # 改为按 CST 转换,使日志行内时间戳与文件名时间一致(均为北京时间)。

    def _cst_converter(seconds: float):
        return datetime.fromtimestamp(seconds, CST).timetuple()

    formatter.converter = _cst_converter

    if enable_separate_logs:
        file_handler = FileHandler(log_file_path, encoding="utf-8")
    else:
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )

    file_handler.setFormatter(formatter)
    file_handler.setLevel(getattr(logging, log_level))
    root_logger.addHandler(file_handler)

    import sys

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, log_level))
    root_logger.addHandler(console_handler)

    return Path(log_file_path)


def test_separate_log_files_written_to_tmp(tmp_path):
    """启用分离日志文件时，日志写入 tmp_path 隔离目录."""
    log_config = _build_log_config(tmp_path)
    log_file_path = setup_logging(log_config)

    logger = logging.getLogger(__name__)
    logger.info("测试日志功能")
    logger.info("日志应该被写入按日期时间分目录的文件中")
    logger.warning("这是一个警告消息")
    logger.error("这是一个错误消息")

    # 关闭所有 handler，确保日志落盘
    for handler in logging.getLogger().handlers[:]:
        handler.close()
        logging.getLogger().removeHandler(handler)

    # 断言：日志文件存在于 tmp_path 下，不触及生产 ./logs/
    assert log_file_path.exists(), f"日志文件未生成: {log_file_path}"
    assert str(log_file_path).startswith(str(tmp_path)), "日志泄漏到生产目录"
    content = log_file_path.read_text(encoding="utf-8")
    assert "测试日志功能" in content
    assert "这是一个错误消息" in content


def test_traditional_rotating_handler(tmp_path):
    """未启用分离日志文件时，使用 RotatingFileHandler 写入 tmp_path."""
    log_config = _build_log_config(tmp_path)
    log_config["enable_separate_log_files"] = False
    log_config["file_path"] = str(tmp_path / "app.log")

    log_file_path = setup_logging(log_config)

    logger = logging.getLogger(__name__)
    logger.info("传统模式测试")

    for handler in logging.getLogger().handlers[:]:
        handler.close()
        logging.getLogger().removeHandler(handler)

    assert log_file_path.exists()
    assert "传统模式测试" in log_file_path.read_text(encoding="utf-8")


class TestLogTimezoneBeijing:
    """日志时区回归测试(AGENTS.md 2026-06-25)。

    生产服务器系统时区为 UTC,日志文件名({date}/{time})与日志行内 asctime 必须按
    北京时间(Asia/Shanghai, UTC+8)生成,使运维按文件名/时间戳排查时看到的是
    业务语义时间(A 股交易日、数据源发布时刻),而非服务器本地 UTC。
    """

    def test_log_filename_uses_beijing_time(self, tmp_path):
        """日志文件名 {date}/{time} 用北京时间,而非服务器本地 UTC。"""
        # 记录调用前后的北京时区窗口(setup_logging 内部一次性取时间)
        cst_before = now_cst()
        log_file_path = setup_logging(_build_log_config(tmp_path))
        cst_after = now_cst()

        # 文件名形如 {tmp_path}/{YYYYMMDD}/{HHMMSS}.log
        # 提取 date / time 部分与北京时区窗口对比
        parts = log_file_path.parts
        date_dir = parts[-2]
        time_file = parts[-1].removesuffix(".log")

        assert re.fullmatch(r"\d{8}", date_dir), f"日期目录格式异常: {date_dir}"
        assert re.fullmatch(r"\d{6}", time_file), f"时间文件名格式异常: {time_file}"

        file_cst = datetime.strptime(date_dir + time_file, "%Y%m%d%H%M%S").replace(
            tzinfo=CST
        )
        # 文件名时间精度仅到秒(setup_logging 用 %H%M%S 截断微秒),所以窗口下界
        # 允许回退到该秒的开始(file_cst 可能略早于 cst_before 的微秒部分)。
        # 窗口校验本身即证明文件名用的是北京时间:若文件名用 UTC,它会比 cst_before
        # 早 8 小时,不可能落在 [cst_before, cst_after] 窗口内。
        assert cst_before - timedelta(seconds=1) <= file_cst <= cst_after + timedelta(
            seconds=2
        ), f"日志文件名时间 {file_cst} 不在北京时区窗口 [{cst_before}, {cst_after}]"

        for handler in logging.getLogger().handlers[:]:
            handler.close()
            logging.getLogger().removeHandler(handler)

    def test_log_asctime_uses_beijing_time(self, tmp_path):
        """日志行内 asctime 用北京时间,而非服务器本地 UTC。"""
        log_file_path = setup_logging(_build_log_config(tmp_path))

        cst_before = now_cst()
        logger = logging.getLogger(__name__)
        logger.info("时区测试标记")
        cst_after = now_cst()

        for handler in logging.getLogger().handlers[:]:
            handler.close()
            logging.getLogger().removeHandler(handler)

        content = log_file_path.read_text(encoding="utf-8")
        assert "时区测试标记" in content

        # asctime 格式 "YYYY-MM-DD HH:MM:SS,mmm" — 提取首行的日期时间部分
        match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d{3}", content)
        assert match, f"asctime 格式异常,内容首行: {content.splitlines()[0]}"
        asctime_cst = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=CST
        )

        # asctime 应落在记录前后的北京时区窗口内
        # 窗口校验本身即证明 asctime 用的是北京时间:若用 UTC,它会比 cst_before
        # 早 8 小时,不可能落在 [cst_before, cst_after] 窗口内。
        assert (
            cst_before - timedelta(seconds=1) <= asctime_cst <= cst_after + timedelta(seconds=2)
        ), f"asctime {asctime_cst} 不在北京窗口 [{cst_before}, {cst_after}]"


if __name__ == "__main__":
    # 手动运行时仍用相对路径，方便本地调试
    setup_logging(_build_log_config(Path("./logs")))
    logger = logging.getLogger(__name__)
    logger.info("测试日志功能")
    print("日志已记录，检查 ./logs/ 目录下的文件结构")
