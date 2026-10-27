"""Calendar sync job for scheduler.

- Dec 20: 强制同步下一年交易日历
- Dec 20-31: 检查下一年日历是否存在，缺失则补
- 非 12 月: 校验当前年日历完整性，有缺口则补全年（2026-07-14 修复）
"""

import logging
from datetime import date
from typing import Any

from galaxy_core.application.scheduler.retry_handler import sync_with_retry
from galaxy_core.application.scheduler.state_manager import SyncStateManager
from galaxy_core.domain.ports.calendar_store import CalendarStorePort
from galaxy_core.shared_kernel.utils.config_loader import get_section

logger = logging.getLogger(__name__)


class CalendarSyncJob:
    """Calendar synchronization job.

    Runs at 00:00:
    - Dec 20: Sync next year calendar
    - Dec 20-31: Check if next year calendar exists, sync if missing
    - 非 12 月: 校验当前年日历完整性，有缺口则补全年
    """

    def __init__(
        self,
        state_manager: SyncStateManager,
        calendar_service: Any = None,
        calendar_store: CalendarStorePort | None = None,
    ) -> None:
        self._state_manager = state_manager
        self._config = get_section("scheduler")
        self._calendar_service = calendar_service
        self._calendar_store = calendar_store

    async def run(self, today: date) -> None:
        """Run calendar sync job.

        Args:
            today: Current date
        """
        # 非 12 月: 校验当前年完整性（2026-07-14 修复）。
        # 历史教训: 原 run() 只在 12 月运行,非 12 月立即 return。一旦当前年日历
        # 出现缺口(akshare 偶发漏数据/手动删/同步中断),_check_kline_trigger 查
        # "昨天是否交易日"返回空 → K线同步静默哑火(只发 debug 日志,INFO 级无告警),
        # 数据静默滞后。修复: 每天 00:00 都校验当前年,有缺口自愈补全年。
        if today.month != 12:
            await self._verify_current_year_completeness(today)
            return

        # Get window from config
        window_start = self._config.get("calendar_check_window_start", 20)
        window_end = self._config.get("calendar_check_window_end", 31)

        # Outside window
        if today.day < window_start:
            logger.debug(f"日历同步跳过: 12月{window_start}日之前 ({today})")
            return

        # Determine next year
        next_year = today.year + 1
        sync_type = "calendar"
        period_id = str(next_year)

        # Dec 20: force sync
        sync_day = self._config.get("calendar_sync_day", 20)
        if today.day == sync_day:
            logger.info(f"12月{sync_day}日: 同步 {next_year} 年交易日历")
            await self._sync_calendar(next_year, sync_type, period_id)
            return

        # Dec 20-31: check if exists, sync if missing
        if today.day <= window_end:
            logger.info(f"12月{today.day}日: 检查 {next_year} 年交易日历是否存在")
            exists = await self._check_calendar_exists(next_year)
            if not exists:
                logger.info(f"{next_year} 年交易日历缺失，开始同步")
                await self._sync_calendar(next_year, sync_type, period_id)
            else:
                logger.info(f"{next_year} 年交易日历已存在")

    async def _verify_current_year_completeness(self, today: date) -> None:
        """校验当前年交易日历完整性，有缺口则补全年。

        判据: 当前年已有交易日数应不低于「已过完整月数 × 月均交易日」阈值。
        公式 expected_min = (today.month - 1) × calendar_min_trading_days_per_month。
        例如 7 月中旬: (7-1) × 18 = 108,A 股实际到 7 月中旬应有 ~120 个交易日,
        阈值 108 留足容差。低于阈值说明日历有缺口(akshare 漏数据/同步中断等),
        触发补全年同步。

        为什么不用固定阈值(如 _check_calendar_exists 的 200): 年初(1-8 月)天然
        不足 200,固定阈值会误判。按月数线性增长更符合日历积累规律。
        """
        if self._calendar_store is None:
            logger.debug("当前年日历校验跳过: 未注入 calendar_store")
            return

        year = today.year
        days = await self._calendar_store.get_trading_days(
            date(year, 1, 1), today
        )
        actual = len(days)

        days_per_month = self._config.get(
            "calendar_min_trading_days_per_month", 18
        )
        expected_min = (today.month - 1) * days_per_month

        if actual >= expected_min:
            logger.debug(
                f"当前年日历完整: {year} 年已有 {actual} 个交易日"
                f"(阈值 {expected_min}, {today})"
            )
            return

        logger.warning(
            f"当前年日历缺口: {year} 年仅 {actual} 个交易日"
            f"< 阈值 {expected_min},触发补全年同步 ({today})"
        )
        await self._sync_calendar(year, "calendar", str(year))

    async def _sync_calendar(self, year: int, sync_type: str, period_id: str) -> None:
        """Sync calendar with retry."""
        # Check if already synced
        if await self._state_manager.is_synced(sync_type, period_id):
            logger.info(f"{year} 年交易日历已同步，跳过")
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

        Validates result: a full year should have ~240-250 trading days.
        If count is too low, akshare likely hasn't published the calendar yet.
        """
        MIN_TRADING_DAYS_PER_YEAR = 200

        count = await self._calendar_service.sync_calendar_async(year)
        logger.info(f"已同步 {year} 年交易日历，共 {count} 个交易日")

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
            days = await self._calendar_store.get_trading_days(start_date, end_date)
            exists = len(days) >= MIN_TRADING_DAYS_PER_YEAR
            if 0 < len(days) < MIN_TRADING_DAYS_PER_YEAR:
                logger.warning(
                    f"{year} 年交易日历仅有 {len(days)} 个交易日，"
                    f"低于阈值 {MIN_TRADING_DAYS_PER_YEAR}"
                )
            return exists
        except Exception:
            return False
