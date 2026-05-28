"""Completeness check job for scheduler.

Per D-19: Dual trigger mechanism - 17:00 daily + post-sync verification.
Per D-20: Check intervals configurable via [scheduler.check_intervals].
Per D-21: Auto-trigger repair sync using KlineSyncJob logic.

Check modes:
- full: Start from AmazingData data start date (2013 per security_type config)
- routine: Start from last N periods ago (configurable, default 10)

Check range per SecurityType:
- Start: determined by check_mode + listing date consideration
- End: current period end
- Listing date: for DAY/WEEK/MONTH/SEASON/YEAR, check starts from listing date
"""

import asyncio
import logging
import time
from datetime import date, timedelta
from typing import Literal

from galaxy_db_sync.amazing_data.api.client import amazing_data_client
from galaxy_db_sync.application.scheduler.state_manager import SyncStateManager
from galaxy_db_sync.database.services.completeness_check_log_manager import (
    completeness_check_log_manager,
)
from galaxy_db_sync.database.services.kline_completeness_checker import KlineCompletenessChecker
from galaxy_db_sync.shared_kernel.enums.interval import Interval
from galaxy_db_sync.shared_kernel.enums.security_type import SecurityType
from galaxy_db_sync.shared_kernel.utils.config_loader import get_section
from galaxy_db_sync.shared_kernel.utils.time_parser import pad_date_to_full_format

logger = logging.getLogger(__name__)

CheckMode = Literal["full", "routine"]


class CompletenessCheckJob:
    """Completeness check job for daily data integrity verification.

    Checks database completeness for configured intervals and triggers
    repair sync if missing data is found.

    Supports per-security-type check ranges via config.

    Check modes:
    - full: Check from AmazingData data start (2013) to now
    - routine: Check last N periods (default 10)
    """

    def __init__(self, state_manager: SyncStateManager) -> None:
        self._state_manager = state_manager
        self._checker = KlineCompletenessChecker()
        self._config = get_section("scheduler")
        self._routine_lookback = self._config.get("routine_lookback_periods", 10)
        # Cache listing dates to avoid repeated API calls
        self._listing_dates_cache: dict[str, date] = {}

    async def run(
        self,
        check_type: str,
        check_date: date,
        check_mode: CheckMode = "routine",
    ) -> dict:
        """Run completeness check for configured intervals.

        Args:
            check_type: 'daily_17pm' or 'post_sync'
            check_date: Date to check data for
            check_mode: 'full' (from 2013) or 'routine' (last N periods)

        Returns:
            dict with check results: {total_missing, repair_triggered,
            intervals_checked, check_mode}
        """
        # Get intervals to check from config (D-20)
        check_intervals = self._config.get("check_intervals", ["day", "week"])
        intervals = [Interval(i) for i in check_intervals]

        # Get security type from config
        security_type_str = self._config.get("security_type", "SH_A")
        try:
            security_type = SecurityType(security_type_str)
        except ValueError:
            logger.warning(f"Invalid security_type config: {security_type_str}, using SH_A")
            security_type = SecurityType.SH_A

        # Get symbol list
        logger.info(f"Fetching symbol list for {security_type}")
        symbols_df = await amazing_data_client.get_stock_list_async(security_type.name)
        # 索引是 code_market，获取索引值作为证券代码列表
        symbol_list = symbols_df.index.tolist()

        # Limit symbols for efficiency (first 100)
        symbol_list = symbol_list[:100]

        logger.info(
            f"Completeness check ({check_type}, mode={check_mode}) for {check_date}: "
            f"{len(intervals)} intervals, {len(symbol_list)} symbols, security_type={security_type}"
        )

        # Fetch listing dates for all symbols (for 日线及以上 consideration)
        await self._fetch_listing_dates(symbol_list, security_type)

        # Create log entry
        log = await completeness_check_log_manager.create_log(
            check_type=check_type,
            check_date=check_date.strftime("%Y-%m-%d"),
            check_intervals=check_intervals,
            symbols_checked=len(symbol_list),
        )

        start_time = time.time()
        total_missing = 0
        repair_triggered = "no"
        repair_results = []

        # Check each interval
        for interval in intervals:
            missing_info = await self._check_interval(
                symbol_list, interval, check_date, security_type, check_mode
            )
            total_missing += missing_info["missing_count"]

            # Trigger repair if missing found (D-21)
            if missing_info["missing_count"] > 0:
                repair_result = await self._repair_missing(
                    missing_info["missing_symbols"], interval, check_date
                )
                repair_results.append(repair_result)
                repair_triggered = "yes" if repair_result["success"] else "partial"

        # Complete log entry
        duration_ms = int((time.time() - start_time) * 1000)
        await completeness_check_log_manager.complete_log(
            log_id=log.id,
            total_missing=total_missing,
            repair_triggered=repair_triggered,
            repair_result=str(repair_results) if repair_results else None,
            check_duration_ms=duration_ms,
        )

        logger.info(
            f"Completeness check complete: missing={total_missing}, "
            f"repair={repair_triggered}, duration={duration_ms}ms, mode={check_mode}"
        )

        return {
            "total_missing": total_missing,
            "repair_triggered": repair_triggered,
            "intervals_checked": check_intervals,
            "check_mode": check_mode,
        }

    async def _check_interval(
        self,
        symbols: list[str],
        interval: Interval,
        check_date: date,
        security_type: SecurityType,
        check_mode: CheckMode,
    ) -> dict:
        """Check completeness for one interval.

        Args:
            symbols: List of symbol codes
            interval: Interval to check
            check_date: Date to check
            security_type: Security type for check range lookup
            check_mode: 'full' or 'routine'

        Returns:
            dict with missing_count and missing_symbols list
        """
        missing_count = 0
        missing_symbols: list[tuple[str, list]] = []

        # Check each symbol (using asyncio.to_thread for synchronous checker)
        for symbol in symbols:
            try:
                # Get check range with listing date consideration
                start_date, end_date = self._get_check_range(
                    interval, check_date, security_type, check_mode, symbol
                )

                # Skip if start_date > end_date (listing date after check end)
                if start_date > end_date:
                    logger.debug(
                        f"{symbol} {interval.value}: listing date after check range, skipped"
                    )
                    continue

                # KlineCompletenessChecker.check_async is async
                result = await self._checker.check_async(
                    symbol,
                    interval,
                    start_date,
                    end_date,
                )

                if not result.is_complete:
                    missing_count += result.missing_count
                    missing_symbols.append((symbol, result.missing_ranges))
                    logger.debug(
                        f"{symbol} {interval.value}: missing {result.missing_count} "
                        f"ranges: {result.missing_ranges}"
                    )
            except Exception as e:
                logger.warning(f"Failed to check {symbol} {interval.value}: {e}")

        return {
            "missing_count": missing_count,
            "missing_symbols": missing_symbols,
        }

    async def _repair_missing(
        self,
        missing_symbols: list[tuple[str, list]],
        interval: Interval,
        check_date: date,
    ) -> dict:
        """Trigger repair sync for missing data.

        Per D-21: Reuse KlineDataSyncService for repair.

        Args:
            missing_symbols: List of (symbol, missing_ranges) tuples
            interval: Interval to repair
            check_date: Date being checked

        Returns:
            dict with success status and records synced
        """
        from galaxy_db_sync.database.services.kline_data_sync import (
            kline_data_sync_service,
        )

        if not missing_symbols:
            return {"success": True, "records_synced": 0}

        sync_type = f"repair_{interval.value}"
        period_id = check_date.strftime("%Y%m%d")

        # Check if repair already triggered for this period
        if await self._state_manager.is_synced(sync_type, period_id):
            logger.info(f"Repair {interval.value} {period_id} already done")
            return {"success": True, "records_synced": 0, "reason": "already_repaired"}

        # Mark repair as running
        await self._state_manager.mark_running(sync_type, period_id)

        total_synced = 0
        success = True

        # Repair each missing symbol
        for symbol, missing_ranges in missing_symbols[:50]:  # Limit to 50
            for range_start, range_end in missing_ranges[:5]:  # Limit to 5 ranges per symbol
                try:
                    start_str = pad_date_to_full_format(
                        range_start.strftime("%Y%m%d"), interval.value, is_end=False
                    )
                    end_str = pad_date_to_full_format(
                        range_end.strftime("%Y%m%d"), interval.value, is_end=True
                    )

                    if start_str is None or end_str is None:
                        logger.warning(f"Failed to parse dates for {symbol}")
                        continue

                    # Use KlineDataSyncService.sync_kline_data_async
                    count = await kline_data_sync_service.sync_kline_data_async(
                        symbol,
                        interval.value,
                        start_str,
                        end_str,
                    )
                    total_synced += count
                    logger.info(f"Repaired {symbol} {interval.value}: {count} records")
                except Exception as e:
                    logger.warning(f"Failed to repair {symbol} {interval.value}: {e}")
                    success = False

        # Update state
        if success:
            await self._state_manager.mark_success(sync_type, period_id, total_synced)
        else:
            await self._state_manager.mark_failed(sync_type, period_id, "Partial repair failure")

        return {"success": success, "records_synced": total_synced}

    async def _fetch_listing_dates(
        self,
        symbols: list[str],
        security_type: SecurityType,
    ) -> None:
        """Fetch listing dates for symbols and cache them.

        Args:
            symbols: List of symbol codes
            security_type: Security type for API call
        """
        try:
            listing_dates_dict = await amazing_data_client.get_listing_dates_async(
                symbols, security_type.name
            )
            for symbol, list_day_str in listing_dates_dict.items():
                if list_day_str:
                    try:
                        # Parse YYYYMMDD format
                        self._listing_dates_cache[symbol] = date(
                            int(list_day_str[:4]),
                            int(list_day_str[4:6]),
                            int(list_day_str[6:8]),
                        )
                    except (ValueError, IndexError):
                        logger.warning(f"Invalid listing date format for {symbol}: {list_day_str}")
                else:
                    # No listing date means data starts from AmazingData start
                    self._listing_dates_cache[symbol] = self._get_data_start_date(security_type)
            logger.debug(f"Cached listing dates for {len(symbols)} symbols")
        except Exception as e:
            logger.warning(f"Failed to fetch listing dates: {e}, using data start date for all")
            data_start = self._get_data_start_date(security_type)
            for symbol in symbols:
                self._listing_dates_cache[symbol] = data_start

    def _get_data_start_date(self, security_type: SecurityType) -> date:
        """Get AmazingData data start date for security type.

        Args:
            security_type: Security type for config lookup

        Returns:
            Start date from config (default 2013-01-01)
        """
        check_ranges = self._config.get("check_ranges", {})
        type_config = check_ranges.get(security_type.value, {})
        if not type_config:
            type_config = check_ranges.get("default", {})
        start_year = type_config.get("start_year", 2013)
        return date(start_year, 1, 1)

    def _calculate_routine_start(
        self,
        interval: Interval,
        check_date: date,
    ) -> date:
        """Calculate start date for routine check (last N periods).

        Args:
            interval: Interval type
            check_date: Current check date

        Returns:
            Start date N periods ago
        """
        lookback = self._routine_lookback

        if interval == Interval.DAY:
            # For day, look back N trading days (approximate with calendar days * 1.4)
            # Conservative: use more calendar days to ensure coverage
            return check_date - timedelta(days=int(lookback * 1.5))
        elif interval == Interval.WEEK:
            # For week, look back N weeks
            return check_date - timedelta(weeks=lookback)
        elif interval == Interval.MONTH:
            # For month, look back N months (approximate)
            year = check_date.year
            month = check_date.month - lookback
            while month <= 0:
                year -= 1
                month += 12
            return date(year, month, 1)
        elif interval == Interval.SEASON:
            # For quarter, look back N quarters
            year = check_date.year
            quarter = (check_date.month - 1) // 3 + 1
            quarter -= lookback
            while quarter <= 0:
                year -= 1
                quarter += 4
            start_month = (quarter - 1) * 3 + 1
            return date(year, start_month, 1)
        elif interval == Interval.YEAR:
            # For year, look back N years
            return date(check_date.year - lookback, 1, 1)
        else:
            # Default: use day lookback
            return check_date - timedelta(days=int(lookback * 1.5))

    def _get_check_range(
        self,
        interval: Interval,
        check_date: date,
        security_type: SecurityType,
        check_mode: CheckMode,
        symbol: str,
    ) -> tuple[date, date]:
        """Get date range to check based on mode, interval, and listing date.

        Args:
            interval: Interval type
            check_date: Current check date
            security_type: Security type for config lookup
            check_mode: 'full' or 'routine'
            symbol: Symbol for listing date consideration

        Returns:
            (start_date, end_date) tuple

        Logic:
        - full mode: Start from AmazingData data start (2013)
        - routine mode: Start from last N periods ago
        - For DAY/WEEK/MONTH/SEASON/YEAR: Adjust start to listing date
        - End: current period end
        """
        # Get base start date based on mode
        if check_mode == "full":
            base_start = self._get_data_start_date(security_type)
        else:
            base_start = self._calculate_routine_start(interval, check_date)

        # Get end date (current period end)
        end_date = self._get_period_end(interval, check_date)

        # Consider listing date for日线及以上 (DAY and longer intervals)
        listing_date = self._listing_dates_cache.get(symbol)
        # Adjust start to max(base_start, listing_date)
        start_date = max(base_start, listing_date) if listing_date else base_start

        logger.debug(
            f"Check range for {symbol} {interval.value}: {start_date} to {end_date} "
            f"(mode={check_mode}, listing={listing_date})"
        )

        return start_date, end_date

    def _get_period_end(self, interval: Interval, check_date: date) -> date:
        """Get the end date of current period.

        Args:
            interval: Interval type
            check_date: Current check date

        Returns:
            End date of the period (last trading day is handled by checker)
        """
        if interval == Interval.DAY:
            # Day: check today
            return check_date
        elif interval == Interval.WEEK:
            # Week: ends on Sunday (check_date is usually the last trading day)
            return check_date
        elif interval == Interval.MONTH:
            # Month: last day of month
            import calendar

            last_day = calendar.monthrange(check_date.year, check_date.month)[1]
            return date(check_date.year, check_date.month, last_day)
        elif interval == Interval.SEASON:
            # Quarter: last day of quarter
            quarter = (check_date.month - 1) // 3 + 1
            season_end_month = quarter * 3
            import calendar

            last_day = calendar.monthrange(check_date.year, season_end_month)[1]
            return date(check_date.year, season_end_month, last_day)
        elif interval == Interval.YEAR:
            # Year: December 31
            return date(check_date.year, 12, 31)
        else:
            return check_date
