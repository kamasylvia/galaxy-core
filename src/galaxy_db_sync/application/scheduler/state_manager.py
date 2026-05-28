"""Sync state manager for database operations."""

import logging
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from galaxy_db_sync.database.core.async_connection import async_db_manager
from galaxy_db_sync.database.models.sync_state import SyncState

logger = logging.getLogger(__name__)


class SyncStateManager:
    """Manages sync state records in database.

    Prevents duplicate syncs and tracks retry history.
    """

    async def is_synced(self, sync_type: str, period_identifier: str) -> bool:
        """Check if this sync was already completed successfully.

        Args:
            sync_type: e.g., 'kline_day', 'kline_week', 'calendar'
            period_identifier: e.g., '2025-03-28', '2025-W12', '2026'

        Returns:
            True if sync already succeeded, False otherwise
        """
        async with async_db_manager.session() as session:
            query = select(SyncState).where(
                SyncState.sync_type == sync_type,
                SyncState.period_identifier == period_identifier,
                SyncState.sync_status == "success"
            )
            result = await session.execute(query)
            record = result.scalar_one_or_none()
            return record is not None

    async def mark_running(self, sync_type: str, period_identifier: str) -> None:
        """Mark sync as running (started).

        Creates new record or updates existing pending/failed record.
        """
        async with async_db_manager.session() as session:
            # Upsert: insert if not exists, update if exists
            stmt = insert(SyncState).values(
                sync_type=sync_type,
                period_identifier=period_identifier,
                sync_status="running",
                started_at=datetime.utcnow(),
            ).on_conflict_do_update(
                index_elements=["sync_type", "period_identifier"],
                set_={
                    "sync_status": "running",
                    "started_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            )
            await session.execute(stmt)
        logger.info(f"Sync marked running: {sync_type} {period_identifier}")

    async def mark_success(
        self,
        sync_type: str,
        period_identifier: str,
        records_synced: int = 0
    ) -> None:
        """Mark sync as successfully completed.

        Args:
            sync_type: Sync type identifier
            period_identifier: Period identifier
            records_synced: Number of records synced
        """
        async with async_db_manager.session() as session:
            stmt = update(SyncState).where(
                SyncState.sync_type == sync_type,
                SyncState.period_identifier == period_identifier,
            ).values(
                sync_status="success",
                completed_at=datetime.utcnow(),
                records_synced=records_synced,
                updated_at=datetime.utcnow(),
            )
            await session.execute(stmt)
        logger.info(f"Sync succeeded: {sync_type} {period_identifier}, {records_synced} records")

    async def mark_failed(
        self,
        sync_type: str,
        period_identifier: str,
        error_message: str
    ) -> None:
        """Mark sync as failed.

        Args:
            sync_type: Sync type identifier
            period_identifier: Period identifier
            error_message: Error description
        """
        async with async_db_manager.session() as session:
            # Get current retry count
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
                updated_at=datetime.utcnow(),
            )
            await session.execute(stmt)
        logger.error(f"Sync failed: {sync_type} {period_identifier} - {error_message}")

    async def get_retry_count(self, sync_type: str, period_identifier: str) -> int:
        """Get current retry count for a sync."""
        async with async_db_manager.session() as session:
            query = select(SyncState.retry_count).where(
                SyncState.sync_type == sync_type,
                SyncState.period_identifier == period_identifier,
            )
            result = await session.execute(query)
            return result.scalar_one_or_none() or 0