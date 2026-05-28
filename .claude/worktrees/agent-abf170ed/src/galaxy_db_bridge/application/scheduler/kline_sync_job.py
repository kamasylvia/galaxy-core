"""K-line sync job for scheduler.

Per SCHED-06: Uses IntervalBoundaryChecker to detect which periods end today.
"""

import logging
from datetime import date

from galaxy_db_bridge.shared_kernel.enums.interval import Interval
from galaxy_db_bridge.shared_kernel.utils.interval_boundary_checker import IntervalBoundaryChecker
from galaxy_db_bridge.shared_kernel.utils.config_loader import get_section
from galaxy_db_bridge.application.scheduler.state_manager import SyncStateManager
from galaxy_db_bridge.application.scheduler.retry_handler import sync_with_retry

logger = logging.getLogger(__name__)


class KlineSyncJob:
    """K-line synchronization job.

    Runs at 23:00 to sync K-line data for periods ending today.
    """

    def __init__(self, state_manager: SyncStateManager) -> None:
        self._state_manager = state_manager
        self._boundary_checker = IntervalBoundaryChecker()
        self._config = get_section("scheduler")

    async def run(self, today: date) -> None:
        """Run K-line sync for periods ending today.

        Args:
            today: Current date
        """
        # Get intervals to sync based on trading calendar
        intervals_to_sync = await self._boundary_checker.get_periods_to_sync_today(today)

        # Filter by enabled intervals from config
        enabled = self._config.get("enabled_intervals", ["day", "week", "month", "season", "year"])
        enabled_intervals = [Interval(i) for i in enabled]

        intervals_to_sync = [i for i in intervals_to_sync if i in enabled_intervals]

        if not intervals_to_sync:
            logger.info(f"No intervals to sync on {today}")
            return

        logger.info(f"K-line sync: {len(intervals_to_sync)} intervals to sync on {today}")

        # Sync in order: DAY first, then ascending (per RESEARCH.md recommendation)
        sync_order = [Interval.DAY, Interval.WEEK, Interval.MONTH, Interval.SEASON, Interval.YEAR]
        intervals_to_sync = sorted(intervals_to_sync, key=lambda x: sync_order.index(x))

        for interval in intervals_to_sync:
            await self._sync_interval(interval, today)

    async def _sync_interval(self, interval: Interval, today: date) -> None:
        """Sync single interval with retry per SCHED-03."""
        sync_type = f"kline_{interval.value}"
        period_id = self._get_period_identifier(interval, today)

        # Check if already synced
        if await self._state_manager.is_synced(sync_type, period_id):
            logger.info(f"{sync_type} {period_id} already synced, skipping")
            return

        # Mark as running
        await self._state_manager.mark_running(sync_type, period_id)

        # Execute sync with retry
        success = await sync_with_retry(
            self._do_sync,
            f"{sync_type} {period_id}",
            interval,
            today
        )

        # Update state
        if success:
            await self._state_manager.mark_success(sync_type, period_id)
        else:
            await self._state_manager.mark_failed(sync_type, period_id, "All retries exhausted")

    async def _do_sync(self, interval: Interval, today: date) -> None:
        """Actual sync implementation.

        Delegates to existing sync_kline_data from sync_orchestrator.
        """
        # TODO: Full implementation calls sync_kline_data with appropriate parameters
        # This is a stub for initial implementation
        # Full implementation needs to:
        # 1. Get security list (all A-shares or from config)
        # 2. Calculate start/end dates for the period
        # 3. Call sync_kline_data with completeness check
        logger.info(f"Syncing {interval.value} K-line data for period ending {today}")
        # Stub: actual implementation in integration testing

    def _get_period_identifier(self, interval: Interval, today: date) -> str:
        """Generate period identifier for state tracking."""
        if interval == Interval.WEEK:
            week_num = today.isocalendar()[1]
            return f"{today.year}-W{week_num}"
        elif interval == Interval.MONTH:
            return f"{today.year}-{today.month:02d}"
        elif interval == Interval.SEASON:
            quarter = (today.month - 1) // 3 + 1
            return f"{today.year}-Q{quarter}"
        elif interval == Interval.YEAR:
            return f"{today.year}"
        else:
            # DAY and others: use date
            return today.strftime("%Y%m%d")