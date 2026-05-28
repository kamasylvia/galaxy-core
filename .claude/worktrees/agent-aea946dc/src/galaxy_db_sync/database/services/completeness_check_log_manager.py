"""Completeness check log manager for database operations."""

import logging
from datetime import datetime
from sqlalchemy import select

from galaxy_db_sync.database.core.async_connection import async_db_manager
from galaxy_db_sync.database.models.completeness_check_log import CompletenessCheckLog

logger = logging.getLogger(__name__)


class CompletenessCheckLogManager:
    """Manages completeness check log records in database."""

    async def create_log(
        self,
        check_type: str,
        check_date: str,
        check_intervals: list[str],
        symbols_checked: int = 0,
    ) -> CompletenessCheckLog:
        """Create a new check log entry (started).

        Args:
            check_type: 'daily_17pm' or 'post_sync'
            check_date: Date of data being checked (YYYY-MM-DD)
            check_intervals: List of intervals checked ['day', 'week']
            symbols_checked: Number of symbols to check

        Returns:
            CompletenessCheckLog: Created log record
        """
        async with async_db_manager.session() as session:
            log = CompletenessCheckLog(
                check_type=check_type,
                check_date=check_date,
                check_intervals=check_intervals,
                symbols_checked=symbols_checked,
                started_at=datetime.utcnow(),
            )
            session.add(log)
            await session.commit()
            await session.refresh(log)
            return log

    async def complete_log(
        self,
        log_id: int,
        total_missing: int,
        repair_triggered: str,
        repair_result: str | None = None,
        check_duration_ms: int = 0,
    ) -> None:
        """Mark check log as completed with results.

        Args:
            log_id: Log record ID
            total_missing: Total missing data points found
            repair_triggered: 'yes', 'no', or 'partial'
            repair_result: Repair outcome details
            check_duration_ms: Check execution time in milliseconds
        """
        async with async_db_manager.session() as session:
            log = await session.get(CompletenessCheckLog, log_id)
            if log:
                log.total_missing = total_missing
                log.repair_triggered = repair_triggered
                log.repair_result = repair_result
                log.check_duration_ms = check_duration_ms
                log.completed_at = datetime.utcnow()
                await session.commit()
        logger.info(
            f"Completeness check completed: {log_id}, "
            f"missing={total_missing}, repair={repair_triggered}"
        )

    async def get_latest_log(self, check_type: str) -> CompletenessCheckLog | None:
        """Get the most recent check log for a type.

        Args:
            check_type: 'daily_17pm' or 'post_sync'

        Returns:
            CompletenessCheckLog or None
        """
        async with async_db_manager.session() as session:
            query = select(CompletenessCheckLog)
            query = query.where(CompletenessCheckLog.check_type == check_type)
            query = query.order_by(CompletenessCheckLog.started_at.desc())
            query = query.limit(1)
            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def get_logs_for_date(self, check_date: str) -> list[CompletenessCheckLog]:
        """Get all check logs for a specific date.

        Args:
            check_date: Date string YYYY-MM-DD

        Returns:
            List of CompletenessCheckLog records
        """
        async with async_db_manager.session() as session:
            query = select(CompletenessCheckLog)
            query = query.where(CompletenessCheckLog.check_date == check_date)
            query = query.order_by(CompletenessCheckLog.started_at)
            result = await session.execute(query)
            return list(result.scalars().all())


# Global manager instance
completeness_check_log_manager = CompletenessCheckLogManager()