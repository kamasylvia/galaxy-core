"""K-line sync job for scheduler.

Per SCHED-06: Uses IntervalBoundaryChecker to detect which periods end today.
"""

import asyncio
import logging
from datetime import date, timedelta

from galaxy_db_sync.amazing_data.api.client import amazing_data_client
from galaxy_db_sync.database.services.trading_calendar import trading_calendar_service
from galaxy_db_sync.shared_kernel.enums.interval import Interval
from galaxy_db_sync.shared_kernel.enums.security_type import SecurityType
from galaxy_db_sync.shared_kernel.utils.interval_boundary_checker import IntervalBoundaryChecker
from galaxy_db_sync.shared_kernel.utils.config_loader import get_section
from galaxy_db_sync.application.scheduler.state_manager import SyncStateManager
from galaxy_db_sync.application.scheduler.retry_handler import sync_with_retry
from galaxy_db_sync.application.kline.sync_orchestrator import sync_kline_data
from galaxy_db_sync.shared_kernel.utils.time_parser import pad_date_to_full_format

logger = logging.getLogger(__name__)

# Sync lookback: number of trading days to check (including today)
_MIN_LOOKBACK_TRADING_DAYS = 5
_DAY_LOOKBACK_TRADING_DAYS = 30


class KlineSyncJob:
    """K-line synchronization job.

    Runs at 23:00 to sync K-line data for periods ending today.
    """

    def __init__(self, state_manager: SyncStateManager) -> None:
        self._state_manager = state_manager
        self._boundary_checker = IntervalBoundaryChecker()
        self._config = get_section("scheduler")

    async def run(self, today: date) -> None:
        """Run K-line sync for configured intervals.

        Short intervals (MIN + DAY): synced every trading day with lookback.
        Long intervals (WEEK+): synced only on the last trading day of the period.

        Args:
            today: Current date
        """
        # Long intervals: only sync on last trading day of period
        long_intervals = await self._boundary_checker.get_periods_to_sync_today(today)

        # Short intervals (MIN + DAY): sync every trading day
        short_intervals = [i for i in Interval if not self._boundary_checker.is_long_interval(i)]

        all_intervals = short_intervals + long_intervals

        # Filter by enabled intervals from config
        enabled = self._config.get("enabled_intervals", ["day", "week", "month", "season", "year"])
        enabled_intervals = [Interval(i) for i in enabled]

        intervals_to_sync = [i for i in all_intervals if i in enabled_intervals]

        if not intervals_to_sync:
            logger.info(f"No intervals to sync on {today}")
            return

        logger.info(f"K-line sync: {len(intervals_to_sync)} intervals to sync on {today}")

        # Sort: MIN first, then DAY, then long intervals
        sync_order = [
            Interval.MIN1, Interval.MIN3, Interval.MIN5, Interval.MIN10,
            Interval.MIN15, Interval.MIN30, Interval.MIN60, Interval.MIN120,
            Interval.DAY, Interval.WEEK, Interval.MONTH, Interval.SEASON, Interval.YEAR,
        ]

        def _sort_key(interval: Interval) -> int:
            try:
                return sync_order.index(interval)
            except ValueError:
                return 999

        intervals_to_sync = sorted(intervals_to_sync, key=_sort_key)

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

        Uses asyncio.to_thread to wrap synchronous sync_kline_data for batch sync.
        """
        # Get security type from config (default to SH_A for A-shares)
        security_type_str = self._config.get("security_type", "SH_A")
        try:
            security_type = SecurityType(security_type_str)
        except ValueError:
            logger.warning(f"Invalid security_type config: {security_type_str}, using SH_A")
            security_type = SecurityType.SH_A

        # Get symbol list from AmazingData client
        logger.info(f"Fetching symbol list for {security_type}")
        symbols_df = await amazing_data_client.get_stock_list_async(security_type.name)
        # 索引是 code_market，获取索引值作为证券代码列表
        symbol_list = symbols_df.index.tolist()

        # Calculate period dates
        period_start, period_end = await self._get_period_dates(interval, today)

        # Format dates
        start_str = pad_date_to_full_format(period_start.strftime("%Y%m%d"), interval.value, is_end=False)
        end_str = pad_date_to_full_format(period_end.strftime("%Y%m%d"), interval.value, is_end=True)

        logger.info(
            f"Syncing {interval.value} for {len(symbol_list)} symbols "
            f"from {start_str} to {end_str}"
        )

        # Call async _batch_sync_symbols directly
        await self._batch_sync_symbols(
            symbol_list,
            interval.value,
            start_str,
            end_str,
        )

    async def _batch_sync_symbols(
        self,
        symbols: list[str],
        interval: str,
        start_date: str,
        end_date: str,
    ) -> int:
        """Batch sync multiple symbols using proper batch sync flow.

        1. Check completeness for all symbols
        2. Call sync_kline_data_async_impl with completeness results
        """
        from galaxy_db_sync.database.services.kline_completeness_checker import (
            kline_completeness_checker,
        )
        from galaxy_db_sync.application.kline.sync_orchestrator import (
            sync_kline_data_async_impl,
        )
        from datetime import date as date_type

        # Parse dates
        from datetime import datetime as dt_type
        start_dt = dt_type.strptime(start_date[:8] if len(start_date) > 8 else start_date, "%Y%m%d").date()
        end_dt = dt_type.strptime(end_date[:8] if len(end_date) > 8 else end_date, "%Y%m%d").date()

        # Step 1: Completeness check for all symbols
        logger.info(f"Completeness check for {len(symbols)} symbols ({interval})")
        completeness_results = {}
        for symbol in symbols:
            result = await kline_completeness_checker.check_async(
                symbol=symbol,
                interval=interval,
                start_date=start_dt,
                end_date=end_dt,
            )
            completeness_results[symbol] = result

        complete_count = sum(1 for r in completeness_results.values() if r.is_complete)
        incomplete_count = len(symbols) - complete_count
        logger.info(f"完整性检查完成: 完整 {complete_count}, 需同步 {incomplete_count}")

        # Step 2: Batch sync with completeness results
        if incomplete_count == 0:
            logger.info("所有证券数据已完整，无需同步")
            return 0

        result = await sync_kline_data_async_impl(
            completeness_results=completeness_results,
            interval=interval,
            full_start=start_date,
            full_end=end_date,
        )

        logger.info(f"批量同步完成: {result.synced_records} 条记录, 成功 {result.success_count}")
        return result.synced_records

    async def _get_lookback_start(
        self, today: date, lookback_trading_days: int
    ) -> date:
        """Get start date for lookback (N trading days including today).

        Args:
            today: End date (today)
            lookback_trading_days: Number of trading days to look back

        Returns:
            Start date that covers N trading days up to and including today
        """
        buffer = lookback_trading_days * 2 + 15
        start = today - timedelta(days=buffer)
        trading_days = await trading_calendar_service.get_trading_days_async(start, today)
        if len(trading_days) < lookback_trading_days:
            logger.warning(
                f"Only {len(trading_days)} trading days found in buffer, "
                f"expected at least {lookback_trading_days}"
            )
            return trading_days[0] if trading_days else start
        return trading_days[-lookback_trading_days]

    async def _get_period_dates(self, interval: Interval, today: date) -> tuple[date, date]:
        """Get start and end dates for sync.

        Short intervals use trading-day lookback to auto-repair recent gaps.
        Long intervals sync the full period up to today (only triggered on last trading day).
        """
        if interval.value.startswith("min"):
            # MIN levels: last N trading days (covers weekends + 1-2 failure days)
            start = await self._get_lookback_start(today, _MIN_LOOKBACK_TRADING_DAYS)
            return start, today
        elif interval == Interval.DAY:
            # DAY: last N trading days (covers recent gaps without full scan)
            start = await self._get_lookback_start(today, _DAY_LOOKBACK_TRADING_DAYS)
            return start, today
        elif interval == Interval.WEEK:
            # Week starts on Monday
            week_start = today - timedelta(days=today.weekday())
            return week_start, today
        elif interval == Interval.MONTH:
            return date(today.year, today.month, 1), today
        elif interval == Interval.SEASON:
            quarter = (today.month - 1) // 3 + 1
            season_start_month = (quarter - 1) * 3 + 1
            return date(today.year, season_start_month, 1), today
        elif interval == Interval.YEAR:
            return date(today.year, 1, 1), today
        else:
            return today, today

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