"""Cleanup job for pruning old sync_state records and log directories.

Runs after each sync cycle to remove stale data.
"""

import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from galaxy_core.application.scheduler.state_manager import SyncStateManager
from galaxy_core.shared_kernel.utils.config_loader import get_section

logger = logging.getLogger(__name__)


class CleanupJob:
    """Prunes old records from sync_state and old log directories."""

    def __init__(
        self,
        state_manager: SyncStateManager,
    ) -> None:
        self._state_manager = state_manager
        self._scheduler_config = get_section("scheduler")
        self._logging_config = get_section("logging")

    async def run(self) -> dict[str, int]:
        """Execute cleanup for sync_state and file logs.

        Returns:
            dict with deleted counts
        """
        retention_days = self._scheduler_config.get("cleanup_retention_days", 30)

        logger.debug(
            f"启动清理: 保留 {retention_days} 天"
        )

        sync_deleted = await self._state_manager.cleanup_old_records(retention_days)
        log_deleted = self._cleanup_old_log_directories(retention_days)

        logger.info(
            f"清理完成: sync_state 删除 {sync_deleted} 条, "
            f"日志目录删除 {log_deleted} 个"
        )

        return {
            "sync_state_deleted": sync_deleted,
            "log_dirs_deleted": log_deleted,
        }

    def _cleanup_old_log_directories(self, retention_days: int) -> int:
        """清理超过 retention_days 天数的旧日志目录.

        Args:
            retention_days: 保留天数

        Returns:
            删除的目录数量
        """
        log_file_pattern = self._logging_config.get(
            "log_file_pattern", "./logs/{date}/{time}.log"
        )
        log_file = Path(log_file_pattern.format(
            date="YYYYMMDD", time="HHMMSS"
        ))
        log_base_path = log_file.parent.parent

        if not log_base_path.exists():
            return 0

        cutoff_date = datetime.now() - timedelta(days=retention_days)
        deleted_count = 0

        try:
            for item in log_base_path.iterdir():
                if item.is_dir() and len(item.name) == 8 and item.name.isdigit():
                    try:
                        dir_date = datetime.strptime(item.name, "%Y%m%d")
                    except ValueError:
                        continue
                    if dir_date < cutoff_date:
                        try:
                            shutil.rmtree(item)
                            deleted_count += 1
                        except Exception:
                            pass
        except Exception as e:
            logger.warning(f"清理日志目录时出错: {e}")

        return deleted_count
