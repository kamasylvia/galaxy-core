"""Auto Sync Scheduler main implementation.

Per SCHED-01: Custom asyncio loop without APScheduler or schedule library.
Polls every minute, triggers sync jobs at configured times.

Per D-19: Dual trigger mechanism for completeness check:
- 17:00 daily check (trading day only)
- Post-sync verification (after K-line sync completes)

Supports auto_sync_interval_minutes for periodic sync (test environment).
"""

import asyncio
import logging
from datetime import date, datetime, time, timedelta

from galaxy_db_sync.application.scheduler.calendar_sync_job import CalendarSyncJob
from galaxy_db_sync.application.scheduler.completeness_check_job import CompletenessCheckJob
from galaxy_db_sync.application.scheduler.kline_sync_job import KlineSyncJob
from galaxy_db_sync.application.scheduler.reference_data_sync_job import ReferenceDataSyncJob
from galaxy_db_sync.application.scheduler.state_manager import SyncStateManager
from galaxy_db_sync.database.core.async_connection import async_db_manager
from galaxy_db_sync.database.services.trading_calendar import trading_calendar_service
from galaxy_db_sync.shared_kernel.utils.config_loader import get_section

logger = logging.getLogger(__name__)


class AutoSyncScheduler:
    """Auto sync scheduler using custom asyncio loop per SCHED-01.

    Runs continuously, checking triggers every minute:
    - 17:00: Daily completeness check (trading days only)
    - 23:00: K-line sync for periods ending today
    - 00:00: Calendar sync (Dec 20) or verification (Dec 20-31)

    Post-sync: Completeness verification after K-line sync completes (D-19)

    Test mode: auto_sync_interval_minutes enables periodic sync.
    """

    def __init__(self) -> None:
        self._running = False
        self._tasks: set[asyncio.Task] = set()
        self._config = get_section("scheduler")

        # Initialize database
        async_db_manager.initialize()

        # Initialize components
        self._state_manager = SyncStateManager()
        self._kline_job = KlineSyncJob(self._state_manager)
        self._calendar_job = CalendarSyncJob(self._state_manager)
        self._completeness_job = CompletenessCheckJob(self._state_manager)
        self._refdata_job = ReferenceDataSyncJob(self._state_manager)

        # Track last sync time for interval-based sync
        self._last_sync_time: datetime | None = None

        # Check if interval-based sync is configured
        self._auto_sync_interval = self._config.get("auto_sync_interval_minutes", None)
        if self._auto_sync_interval:
            logger.info(f"Auto sync interval configured: every {self._auto_sync_interval} minutes")

    async def run_forever(self) -> None:
        """Main scheduler loop per SCHED-01.

        Polls every minute, triggers sync jobs when conditions match.
        Sleeps to next minute boundary to avoid clock drift.
        """
        self._running = True
        logger.info("Auto Sync Scheduler started")

        # Startup verification
        await self._verify_trading_calendar()

        while self._running:
            now = datetime.now()
            current_time = now.time()
            today = now.date()

            # Poll triggers
            await self._check_monthly_full_trigger(today, current_time)
            # Daily 17:00 routine check removed: KlineSyncJob now uses
            # expanded lookback (30 trading days for DAY, 5 for MIN)
            # which covers recent gaps without a separate check pass.
            await self._check_kline_trigger(today, current_time)
            await self._check_calendar_trigger(today, current_time)

            # Check interval-based sync (test mode)
            if self._auto_sync_interval:
                await self._check_interval_sync(today, now)

            # Sleep to next minute boundary (avoids drift per RESEARCH.md Pitfall 2)
            seconds_to_next_minute = 60 - now.second
            await asyncio.sleep(seconds_to_next_minute + 1)

    async def _verify_trading_calendar(self) -> None:
        """Ensure trading calendar exists for current and next year."""
        current_year = datetime.now().year
        logger.info(f"Trading calendar verification for {current_year}")
        # TradingCalendarService handles missing calendar on demand

    async def _is_first_non_trading_day_of_month(self, today: date) -> bool:
        """Check if today is the first non-trading day of the month.

        Returns True if:
        - Today is not a trading day
        - Yesterday was a trading day (so today is the immediate break)
        - All days from month_start to yesterday were trading days (no prior breaks)
        """
        # First check if today is a non-trading day
        trading_days_today = await trading_calendar_service.get_trading_days_async(today, today)
        if trading_days_today:
            # Today is a trading day, not eligible
            return False

        # Get month start date
        month_start = today.replace(day=1)

        # If today is the first day of the month and it's non-trading, it's the first
        if today == month_start:
            return True

        # Check if yesterday was a trading day
        yesterday = today - timedelta(days=1)
        yesterday_trading = await trading_calendar_service.get_trading_days_async(yesterday, yesterday)
        if not yesterday_trading:
            # Yesterday was also non-trading, so today is not the FIRST non-trading day
            return False

        # Check if all days from month_start to yesterday were trading days
        prev_days = await trading_calendar_service.get_trading_days_async(month_start, yesterday)
        expected_calendar_days = (yesterday - month_start).days + 1  # inclusive count

        if len(prev_days) == expected_calendar_days:
            return True

        # There were other non-trading days before today (weekends/holidays)
        return False

    async def _check_monthly_full_trigger(self, today: date, current_time: time) -> None:
        """Check and trigger monthly full completeness check.

        Runs on the first non-trading day of each month at configured time.
        Full check covers all data from 2013 (AmazingData data start).
        """
        trigger_hour = self._config.get("monthly_full_check_hour", 10)
        trigger_minute = self._config.get("monthly_full_check_minute", 0)

        if current_time.hour == trigger_hour and current_time.minute == trigger_minute:
            # Check if today is the first non-trading day of the month
            is_first_non_trading = await self._is_first_non_trading_day_of_month(today)
            if not is_first_non_trading:
                logger.debug(f"Monthly full check skipped: {today} is not first non-trading day")
                return

            logger.info(f"Triggering monthly full completeness check for {today}")
            task = asyncio.create_task(
                self._completeness_job.run("monthly_full", today, check_mode="full"),
                name=f"monthly_full_check_{today}"
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _check_completeness_trigger(self, today: date, current_time: time) -> None:
        """Check and trigger daily completeness check at 17:00.

        Per D-19: Only runs on trading days.
        """
        trigger_hour = self._config.get("check_trigger_hour", 17)
        trigger_minute = self._config.get("check_trigger_minute", 0)

        if current_time.hour == trigger_hour and current_time.minute == trigger_minute:
            # Check if today is a trading day
            trading_days = await trading_calendar_service.get_trading_days_async(today, today)
            if not trading_days:
                logger.info(f"Completeness check skipped: {today} is not a trading day")
                return

            logger.info(f"Triggering daily completeness check at {current_time}")
            task = asyncio.create_task(
                self._completeness_job.run("daily_17pm", today),
                name=f"completeness_check_{today}"
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _check_kline_trigger(self, today: date, current_time: time) -> None:
        """Check and trigger K-line sync at 23:00.

        Post-sync verification triggered after K-line sync completes (D-19).
        """
        trigger_hour = self._config.get("kline_trigger_hour", 23)
        trigger_minute = self._config.get("kline_trigger_minute", 0)

        if current_time.hour == trigger_hour and current_time.minute == trigger_minute:
            logger.info(f"Triggering K-line sync at {current_time}")

            # Create task with post-sync verification callback
            task = asyncio.create_task(
                self._run_kline_sync_with_verification(today),
                name=f"kline_sync_{today}"
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _run_kline_sync_with_verification(self, today: date) -> None:
        """Run K-line sync followed by completeness verification and reference data sync.

        Per D-19: Post-sync verification after K-line sync completes.
        Reference data sync runs after K-line (API 不支持并发).
        """
        # Run K-line sync
        await self._kline_job.run(today)

        # Wait briefly for sync to settle
        await asyncio.sleep(5)

        # Run post-sync completeness check
        logger.info(f"Running post-sync completeness verification for {today}")
        await self._completeness_job.run("post_sync", today)

        # Run reference data sync (P0: stock_basic, stock_status, backward_factor)
        logger.info(f"Running reference data sync for {today}")
        await self._refdata_job.run(today)

    async def _check_calendar_trigger(self, today: date, current_time: time) -> None:
        """Check and trigger calendar sync at 00:00."""
        if current_time.hour == 0 and current_time.minute == 0:
            logger.info(f"Triggering calendar check at {current_time}")
            task = asyncio.create_task(
                self._calendar_job.run(today),
                name=f"calendar_sync_{today}"
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _check_interval_sync(self, today: date, now: datetime) -> None:
        """Check and trigger interval-based sync (test mode).

        Triggers K-line sync every auto_sync_interval_minutes if configured.
        First sync waits for interval to elapse (not immediate).
        """
        if not self._auto_sync_interval:
            return

        # Initialize last_sync_time on first check (don't sync immediately)
        if self._last_sync_time is None:
            self._last_sync_time = now
            logger.info(f"Interval sync initialized, first sync in {self._auto_sync_interval} minutes")
            return

        # Check if interval has elapsed
        elapsed_minutes = (now - self._last_sync_time).total_seconds() / 60
        if elapsed_minutes >= self._auto_sync_interval:
            logger.info(f"Triggering interval-based sync (elapsed: {elapsed_minutes:.1f} min)")
            task = asyncio.create_task(
                self._run_kline_sync_with_verification(today),
                name=f"interval_sync_{today}_{now.strftime('%H%M')}"
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            self._last_sync_time = now

    async def stop(self) -> None:
        """Stop scheduler gracefully.

        Cancels all pending tasks and closes database connection.
        """
        logger.info("Stopping scheduler...")
        self._running = False

        # Cancel all pending tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete (with exceptions handled)
        await asyncio.gather(*self._tasks, return_exceptions=True)

        # Close database
        await async_db_manager.close()
        logger.info("Scheduler stopped")


async def run_scheduler() -> None:
    """Entry point to run scheduler.

    Usage:
        python -m galaxy_db_sync.scheduler
        or: asyncio.run(run_scheduler())
    """
    scheduler = AutoSyncScheduler()
    try:
        await scheduler.run_forever()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        await scheduler.stop()
    except Exception as e:
        logger.error(f"Scheduler error: {e}")
        await scheduler.stop()
        raise
