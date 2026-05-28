"""Scheduler module entry point for running as `python -m galaxy_db_sync.application.scheduler`."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

# Setup logging before importing scheduler - read from config file
from galaxy_db_sync.shared_kernel.utils.config_loader import get_section

log_config = get_section("logging")
log_level = log_config.get("level", "INFO").upper()

# Use date-based directory if configured
if log_config.get("enable_separate_log_files", False):
    pattern = log_config.get("log_file_pattern", "./logs/{date}/{time}.log")
    date_str = datetime.now().strftime("%Y%m%d")
    time_str = datetime.now().strftime("%H%M%S")
    log_file_path = pattern.replace("{date}", date_str).replace("{time}", time_str)
else:
    log_file_path = log_config.get("file_path", "./logs/") + f"scheduler-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"

log_file = Path(log_file_path)
log_file.parent.mkdir(parents=True, exist_ok=True)

root_logger = logging.getLogger()
root_logger.setLevel(getattr(logging, log_level))

# Clear existing handlers
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# File handler
from logging import FileHandler
file_handler = FileHandler(str(log_file), encoding="utf-8")
file_handler.setFormatter(formatter)
file_handler.setLevel(getattr(logging, log_level))
root_logger.addHandler(file_handler)

# Console handler
import sys
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
console_handler.setLevel(getattr(logging, log_level))
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)
logger.info(f"Scheduler logging initialized: {log_file}")

from .scheduler import run_scheduler

if __name__ == "__main__":
    asyncio.run(run_scheduler())