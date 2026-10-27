"""K-line sync job for scheduler.

Per SCHED-06: Uses IntervalBoundaryChecker to detect which periods end today.
Uses sync_common.resolve_symbols + prepare_sync_args for unified preprocessing (D-08).
"""

import logging
from datetime import date, timedelta
from typing import Any

from galaxy_core.application.kline.sync_common import prepare_sync_args, resolve_symbols
from galaxy_core.application.scheduler.retry_handler import sync_with_retry
from galaxy_core.application.scheduler.state_manager import SyncStateManager
from galaxy_core.domain.ports.reference_provider import ReferenceProviderPort
from galaxy_core.shared_kernel.enums.interval import Interval
from galaxy_core.shared_kernel.enums.security_type import SecurityType
from galaxy_core.shared_kernel.utils.config_loader import get_section
from galaxy_core.shared_kernel.utils.interval_boundary_checker import IntervalBoundaryChecker

logger = logging.getLogger(__name__)


class KlineSyncJob:
    """K-line synchronization job.

    Runs at 23:00 to sync K-line data for periods ending today.
    Uses resolve_symbols + prepare_sync_args from sync_common (D-08).
    """

    def __init__(
        self,
        state_manager: SyncStateManager,
        kline_service: Any = None,
        reference_provider: ReferenceProviderPort | None = None,
        calendar_store: Any = None,
        trading_calendar: Any = None,
        db_manager: Any = None,
    ) -> None:
        self._state_manager = state_manager
        self._kline_service = kline_service
        self._reference_provider = reference_provider
        self._boundary_checker = IntervalBoundaryChecker(trading_calendar=trading_calendar)
        self._db_manager = db_manager
        self._config = get_section("scheduler")

    # ========================================================================
    # 主入口（向后兼容）
    # ========================================================================

    async def run(self, today: date) -> None:
        """Run all K-line sync for backward compatibility.

        Args:
            today: Current date (syncs yesterday's data per T+1 pattern)
        """
        await self.run_minute(today)
        await self.run_day(today)
        await self.run_week(today)
        await self.run_month(today)
        await self.run_season(today)
        await self.run_year(today)

    # ========================================================================
    # 各周期独立入口
    # ========================================================================

    async def run_minute(self, today: date) -> None:
        """Sync minute intervals (MIN1-120) for yesterday's data."""
        sync_date = today - timedelta(days=1)
        minute_intervals = [
            Interval.MIN1,
            Interval.MIN3,
            Interval.MIN5,
            Interval.MIN10,
            Interval.MIN15,
            Interval.MIN30,
            Interval.MIN60,
            Interval.MIN120,
        ]
        enabled = self._enabled_intervals()
        intervals_to_sync = [i for i in minute_intervals if i in enabled]

        if not intervals_to_sync:
            logger.debug(f"{sync_date} 无分钟线需同步")
            return

        logger.info(f"分钟线同步: {sync_date}，{len(intervals_to_sync)} 个周期")
        for interval in intervals_to_sync:
            try:
                await self._sync_interval(interval, sync_date)
            except Exception:
                logger.exception(f"分钟线 {interval.value} 同步失败，继续下一个")

    async def run_day(self, today: date) -> None:
        """Sync daily K-line for yesterday's data."""
        sync_date = today - timedelta(days=1)
        if Interval.DAY not in self._enabled_intervals():
            logger.debug(f"{sync_date} 日线未启用，跳过")
            return

        logger.info(f"日线同步: {sync_date}")
        try:
            await self._sync_interval(Interval.DAY, sync_date)
        except Exception:
            logger.exception("日线同步失败")

    async def run_week(self, today: date) -> None:
        """Sync weekly K-line when yesterday was the last trading day of the week."""
        await self._sync_long_interval(Interval.WEEK, today)

    async def run_month(self, today: date) -> None:
        """Sync monthly K-line when yesterday was the last trading day of the month."""
        await self._sync_long_interval(Interval.MONTH, today)

    async def run_season(self, today: date) -> None:
        """Sync seasonal K-line when yesterday was the last trading day of the quarter."""
        await self._sync_long_interval(Interval.SEASON, today)

    async def run_year(self, today: date) -> None:
        """Sync yearly K-line when yesterday was the last trading day of the year."""
        await self._sync_long_interval(Interval.YEAR, today)

    # ========================================================================
    # 向后兼容包装（已弃用，由调度器直接调用各周期方法）
    # ========================================================================

    async def run_short(self, today: date) -> None:
        """Sync short intervals (MIN + DAY) — deprecated, use run_minute + run_day."""
        await self.run_minute(today)
        await self.run_day(today)

    async def run_long(self, today: date) -> None:
        """Sync long intervals (WEEK+) — deprecated, use run_week/month/season/year."""
        await self.run_week(today)
        await self.run_month(today)
        await self.run_season(today)
        await self.run_year(today)

    # ========================================================================
    # 内部方法
    # ========================================================================

    async def _sync_long_interval(self, interval: Interval, today: date) -> None:
        """Sync a single long interval if yesterday was the last trading day."""
        sync_date = today - timedelta(days=1)
        if interval not in self._enabled_intervals():
            return

        is_last = await self._boundary_checker.is_last_trading_day_of_period(
            interval, sync_date
        )
        if not is_last:
            logger.debug(f"{sync_date} 不是 {interval.value} 周期最后一个交易日，跳过")
            return

        logger.info(f"{interval.value} 同步: {sync_date}")
        try:
            await self._sync_interval(interval, sync_date)
        except Exception:
            logger.exception(f"{interval.value} 同步失败")

    async def _sync_interval(self, interval: Interval, sync_date: date) -> None:
        """Sync single interval with retry per SCHED-03."""
        sync_type = f"kline_{interval.value}"
        period_id = self._get_period_identifier(interval, sync_date)

        # Check if already synced
        if await self._state_manager.is_synced(sync_type, period_id):
            logger.info(f"{sync_type} {period_id} 已同步，跳过")
            return

        # Mark as running
        await self._state_manager.mark_running(sync_type, period_id)

        # Execute sync with retry
        # sync_type(如 "kline_day")透传给 RetryPolicy 选 [scheduler.kline]
        # 子表(凌晨 AM 返空需更长重试窗口,见 2026-08-11 根治)
        success = await sync_with_retry(
            self._do_sync,
            f"{sync_type} {period_id}",
            interval,
            sync_date,
            sync_type=sync_type,
        )

        # Update state
        if success:
            await self._state_manager.mark_success(sync_type, period_id)
        else:
            await self._state_manager.mark_failed(
                sync_type, period_id, "All retries exhausted"
            )

    def _security_types_for(self, interval: Interval) -> list[str]:
        """按周期取 security_types:分钟周期用 minute_security_types,其余用全集.

        分钟若沿用 security_types 全集(EXTRA_ETF+EXTRA_STOCK_A+EXTRA_INDEX_A),
        每日全量分钟查询会为股票/指数拉取数据,击穿 100G/年配额
        (2026-10-27 裁决:分钟定稿只覆盖 ETF)。缺省回落全集保持旧行为。
        """
        security_type_strs = list(
            self._config.get("security_types", ["EXTRA_ETF"])
        )
        if interval in (
            Interval.MIN1,
            Interval.MIN3,
            Interval.MIN5,
            Interval.MIN10,
            Interval.MIN15,
            Interval.MIN30,
            Interval.MIN60,
            Interval.MIN120,
        ):
            minute_types = self._config.get("minute_security_types")
            if minute_types:
                return list(minute_types)
        return security_type_strs

    async def _do_sync(self, interval: Interval, sync_date: date) -> None:
        """Actual sync implementation using resolve_symbols + prepare_sync_args (D-08).

        Short intervals pass start=None to rely on last_sync_date.
        Long intervals use _get_period_dates to calculate period boundaries.
        """
        # Get security types from config (list)
        # 分钟周期独立收窄(2026-10-27 裁决:分钟定稿只覆盖 ETF,见 minute_security_types)
        security_type_strs = self._security_types_for(interval)
        valid_types: list[str] = []
        for s in security_type_strs:
            try:
                valid_types.append(SecurityType(s).name)
            except ValueError:
                logger.warning(f"无效的 security_type 配置: {s}，跳过")

        if not valid_types:
            logger.warning("无有效的 security_type 配置，跳过同步")
            return

        # Resolve symbols using shared preprocessing (D-08, D-09)
        symbols = await resolve_symbols(
            valid_types, self._reference_provider, sync_date
        )

        # Fallback: SDK 返空(凌晨 AM 时段不稳,见 AGENTS.md 2026-07-28 Bug 2)
        # 时从 stock_basic 表读 codes,scheduler 路径专用(CLI 不传 db_manager)
        if not symbols and self._db_manager is not None:
            symbols = await _fallback_universe_from_db(
                self._db_manager, valid_types
            )

        # Calculate date range based on interval type
        if self._boundary_checker.is_long_interval(interval):
            # Long period: calculate period boundaries
            period_start, period_end = await self._get_period_dates(
                interval, sync_date
            )
            start_str = period_start.strftime("%Y%m%d")
            end_str = period_end.strftime("%Y%m%d")
        else:
            # Short period: start=None to rely on last_sync_date (D-08)
            start_str = None
            end_str = sync_date.strftime("%Y%m%d")
            # 分钟周期显式回补窗(2026-10-27):kline.default_start_date(20130101)
            # 对分钟是灾难——新 symbol 首启会拉全史分钟(1636 ETF ≈ 12 亿行,
            # margin_detail 9/10 全史重拉同型前科)。显式 N 天窗与 rescan 对齐。
            if interval in (
                Interval.MIN1,
                Interval.MIN3,
                Interval.MIN5,
                Interval.MIN10,
                Interval.MIN15,
                Interval.MIN30,
                Interval.MIN60,
                Interval.MIN120,
            ):
                backfill_days = int(self._config.get("minute_backfill_days", 8))
                start_str = (sync_date - timedelta(days=backfill_days)).strftime("%Y%m%d")

        # Prepare sync args using shared preprocessing
        domain_interval, expanded_start, expanded_end = prepare_sync_args(
            interval.value, start_str, end_str
        )

        logger.info(
            f"同步 {interval.value}: {len(symbols)} 只证券"
            f" 从 {expanded_start or 'last_sync_date'} 到 {expanded_end}"
        )

        # Call kline_service.sync directly (D-08)
        await self._kline_service.sync(
            symbols=symbols,
            interval=domain_interval,
            start=expanded_start,
            end=expanded_end,
        )

    async def _get_period_dates(
        self, interval: Interval, today: date
    ) -> tuple[date, date]:
        """Get start and end dates for long interval sync.

        Only handles long intervals (WEEK, MONTH, SEASON, YEAR).
        Short intervals are handled directly in _do_sync with start=None.
        """
        if interval == Interval.WEEK:
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
            # DAY and minute intervals: use date
            return today.strftime("%Y%m%d")

    def _enabled_intervals(self) -> set[Interval]:
        """Get enabled intervals from config."""
        enabled = self._config.get(
            "enabled_intervals",
            ["day", "week", "month", "season", "year"],
        )
        result: set[Interval] = set()
        for name in enabled:
            try:
                result.add(Interval(name))
            except ValueError:
                logger.warning(f"无效的 enabled_intervals 配置: {name}，跳过")
        return result


async def _fallback_universe_from_db(
    db_manager: Any, security_types: list[str]
) -> list[str]:
    """SDK 返空时从 stock_basic 表读 universe(scheduler 专用 fallback)。

    对每个 security_type 调 resolve_universe_with_fallback 的 DB-only 模式
    (跳过 SDK,直接查 stock_basic)。security_type 用 to_broad_security_type 归一。
    """
    from galaxy_core.shared_kernel.utils.universe import (
        _read_active_symbols_from_db,
    )

    all_codes: list[str] = []
    for sec_type in security_types:
        from galaxy_core.domain.symbol.type_inference import to_broad_security_type
        broad = to_broad_security_type(sec_type)
        codes = await _read_active_symbols_from_db(db_manager, broad)
        all_codes.extend(codes)
        if codes:
            logger.info(
                f"universe DB fallback ({sec_type}→{broad}): {len(codes)} 只"
            )
    return list(set(all_codes))
