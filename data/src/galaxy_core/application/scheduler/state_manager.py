"""同步状态管理器，用于数据库操作。"""

import logging
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from galaxy_core.database.core.async_connection import AsyncDatabaseManager
from galaxy_core.database.models.sync_state import SyncState

logger = logging.getLogger(__name__)


def _now_naive() -> datetime:
    """naive 北京时间(nocodb 形态 sync_state 时间列为 naive ts,2026-08-26 回迁)."""
    from galaxy_core.shared_kernel.utils.constants import now_cst

    return now_cst().replace(tzinfo=None)


class SyncStateManager:
    """管理数据库中的同步状态记录。

    防止重复同步并跟踪重试历史。
    """

    def __init__(self, db_manager: AsyncDatabaseManager) -> None:
        self._db = db_manager

    async def is_synced(self, sync_type: str, period_identifier: str) -> bool:
        """检查此同步是否已成功完成。

        Args:
            sync_type: 同步类型，如 'kline_day', 'kline_week', 'calendar'
            period_identifier: 周期标识，如 '2025-03-28', '2025-W12', '2026'

        Returns:
            同步已成功返回 True，否则返回 False
        """
        async with self._db.session() as session:
            query = select(SyncState).where(
                SyncState.sync_type == sync_type,
                SyncState.period_identifier == period_identifier,
                SyncState.sync_status == "success"
            )
            result = await session.execute(query)
            record = result.scalar_one_or_none()
            return record is not None

    async def mark_running(self, sync_type: str, period_identifier: str) -> None:
        """标记同步为运行中（已开始）。

        创建新记录或更新现有的 pending/failed 记录。
        """
        async with self._db.session() as session:
            # Upsert：不存在则插入，存在则更新
            stmt = insert(SyncState).values(
                sync_type=sync_type,
                period_identifier=period_identifier,
                sync_status="running",
                started_at=_now_naive(),
            ).on_conflict_do_update(
                index_elements=["sync_type", "period_identifier"],
                set_={
                    "sync_status": "running",
                    "started_at": _now_naive(),
                    "updated_at": _now_naive(),
                }
            )
            await session.execute(stmt)
        logger.debug(f"同步标记为运行中: {sync_type} {period_identifier}")

    async def mark_success(
        self,
        sync_type: str,
        period_identifier: str,
        records_synced: int = 0
    ) -> None:
        """标记同步为成功完成。

        成功时显式置空 error_message，避免残留先前失败记录的报错
        （否则 sync_status='success' 与非空 error_message 并存，误导排查）。

        Args:
            sync_type: 同步类型标识
            period_identifier: 周期标识
            records_synced: 同步的记录数
        """
        async with self._db.session() as session:
            stmt = update(SyncState).where(
                SyncState.sync_type == sync_type,
                SyncState.period_identifier == period_identifier,
            ).values(
                sync_status="success",
                completed_at=_now_naive(),
                records_synced=records_synced,
                error_message=None,
                updated_at=_now_naive(),
            )
            await session.execute(stmt)
        logger.debug(f"同步成功: {sync_type} {period_identifier}, {records_synced} 条记录")

    async def mark_failed(
        self,
        sync_type: str,
        period_identifier: str,
        error_message: str
    ) -> None:
        """标记同步为失败。

        Args:
            sync_type: 同步类型标识
            period_identifier: 周期标识
            error_message: 错误描述
        """
        async with self._db.session() as session:
            # 获取当前重试次数
            query = select(SyncState.retry_count).where(
                SyncState.sync_type == sync_type,
                SyncState.period_identifier == period_identifier,
            )
            result = await session.execute(query)
            current_retry = result.scalar_one_or_none() or 0

            stmt = update(SyncState).where(
                SyncState.sync_type == sync_type,
                SyncState.period_identifier == period_identifier,
            ).values(
                sync_status="failed",
                error_message=error_message,
                retry_count=current_retry + 1,
                updated_at=_now_naive(),
            )
            await session.execute(stmt)
        logger.debug(f"同步失败: {sync_type} {period_identifier} - {error_message}")

    async def get_retry_count(self, sync_type: str, period_identifier: str) -> int:
        """获取同步的当前重试次数。"""
        async with self._db.session() as session:
            query = select(SyncState.retry_count).where(
                SyncState.sync_type == sync_type,
                SyncState.period_identifier == period_identifier,
            )
            result = await session.execute(query)
            return result.scalar_one_or_none() or 0

    async def cleanup_old_records(self, retention_days: int) -> int:
        """清理超过保留天数的旧记录。

        Args:
            retention_days: 保留天数，updated_at 早于该天数的记录将被删除

        Returns:
            删除的记录数
        """
        from datetime import timedelta

        from sqlalchemy import delete

        cutoff = _now_naive() - timedelta(days=retention_days)
        async with self._db.session() as session:
            stmt = delete(SyncState).where(SyncState.updated_at < cutoff)
            result = await session.execute(stmt)
            await session.commit()
            deleted = int(result.rowcount)  # type: ignore[attr-defined]
        if deleted > 0:
            logger.info(f"sync_state 清理完成: 删除 {deleted} 条超过 {retention_days} 天的记录")
        return deleted
