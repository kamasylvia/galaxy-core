"""Calendar sync job for scheduler.

Syncs next year calendar on December 20, verifies Dec 20-31.
"""

import asyncio
import logging
from datetime import date

from galaxy_db_sync.database.services.trading_calendar import trading_calendar_service
from galaxy_db_sync.shared_kernel.utils.config_loader import get_section
from galaxy_db_sync.application.scheduler.state_manager import SyncStateManager
from galaxy_db_sync.application.scheduler.retry_handler import sync_with_retry

logger = logging.getLogger(__name__)


class CalendarSyncJob:
    """Calendar synchronization job.

    Runs at 00:00:
    - Dec 20: Sync next year calendar
    - Dec 20-31: Check if next year calendar exists, sync if missing
    """

    def __init__(self, state_manager: SyncStateManager) -> None:
        self._state_manager = state_manager
        self._config = get_section("scheduler")
        self._calendar_service = trading_calendar_service

    async def run(self, today: date) -> None:
        """Run calendar sync job.

        Args:
            today: Current date
        """
        # Only run in December
        if today.month != 12:
            logger.debug(f"Calendar sync skipped: not December ({today})")
            return

        # Get window from config
        window_start = self._config.get("calendar_check_window_start", 20)
        window_end = self._config.get("calendar_check_window_end", 31)

        # Outside window
        if today.day < window_start:
            logger.debug(f"Calendar sync skipped: before Dec {window_start} ({today})")
            return

        # Determine next year
        next_year = today.year + 1
        sync_type = "calendar"
        period_id = str(next_year)

        # Dec 20: force sync
        sync_day = self._config.get("calendar_sync_day", 20)
        if today.day == sync_day:
            logger.info(f"Dec {sync_day}: Syncing {next_year} calendar")
            await self._sync_calendar(next_year, sync_type, period_id)
            return

        # Dec 20-31: check if exists, sync if missing
        if today.day <= window_end:
            logger.info(f"Dec {today.day}: Checking {next_year} calendar existence")
            exists = await self._check_calendar_exists(next_year)
            if not exists:
                logger.info(f"{next_year} calendar missing, syncing")
                await self._sync_calendar(next_year, sync_type, period_id)
            else:
                logger.info(f"{next_year} calendar already exists")

    async def _sync_calendar(self, year: int, sync_type: str, period_id: str) -> None:
        """Sync calendar with retry."""
        # Check if already synced
        if await self._state_manager.is_synced(sync_type, period_id):
            logger.info(f"Calendar {year} already synced, skipping")
            return

        # Mark running
        await self._state_manager.mark_running(sync_type, period_id)

        # Sync with retry
        success = await sync_with_retry(
            self._do_sync_calendar,
            f"calendar {year}",
            year
        )

        # Update state
        if success:
            await self._state_manager.mark_success(sync_type, period_id)
        else:
            await self._state_manager.mark_failed(sync_type, period_id, "All retries exhausted")

    async def _do_sync_calendar(self, year: int) -> None:
        """Actual calendar sync.

        Uses asyncio.to_thread to wrap synchronous sync_calendar method.
        Validates result: a full year should have ~240-250 trading days.
        If count is too low, akshare likely hasn't published the calendar yet.
        """
        MIN_TRADING_DAYS_PER_YEAR = 200

        count = await asyncio.to_thread(self._calendar_service.sync_calendar, year)
        logger.info(f"Synced {count} trading days for {year}")

        if count < MIN_TRADING_DAYS_PER_YEAR:
            raise ValueError(
                f"Calendar for {year} has only {count} trading days, "
                f"expected at least {MIN_TRADING_DAYS_PER_YEAR}. "
                f"akshare may not have published the calendar yet. Will retry."
            )

    async def _check_calendar_exists(self, year: int) -> bool:
        """Check if calendar data exists for year with quality threshold."""
        MIN_TRADING_DAYS_PER_YEAR = 200
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        try:
            days = await self._calendar_service.get_trading_days(start_date, end_date)
            exists = len(days) >= MIN_TRADING_DAYS_PER_YEAR
            if 0 < len(days) < MIN_TRADING_DAYS_PER_YEAR:
                logger.warning(
                    f"Calendar for {year} has only {len(days)} trading days, "
                    f"below threshold {MIN_TRADING_DAYS_PER_YEAR}"
                )
            return exists
        except Exception:
            return False