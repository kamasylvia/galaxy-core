"""周期边界检查器

用于判断长周期（周、月、季、年）是否已完全结束，
并提供周期边界日期的查询功能。
"""

from datetime import date, timedelta
from typing import Optional, Set, Protocol, Union

from galaxy_core.shared_kernel.enums.interval import Interval
from galaxy_core.domain.interval.boundary import (
    is_long_interval as domain_is_long_interval,
    is_interval_complete as domain_is_interval_complete,
    get_interval_start_date as domain_get_interval_start_date,
    get_quarter as domain_get_quarter,
    _get_quarter_start_month,
    _get_quarter_end_month,
    _is_week_complete,
    _is_month_complete,
    _is_season_complete,
    _is_year_complete,
)


class TradingCalendarProtocol(Protocol):
    """交易日历协议，定义所需接口。"""

    async def get_previous_trading_day_async(self, target_date: date) -> date:
        """异步获取指定日期的上一个交易日。"""
        ...


class IntervalBoundaryChecker:
    """周期边界检查器

    用于判断长周期（周、月、季、年）是否已完全结束，
    并提供周期边界日期的查询功能。

    核心原则：只同步已完全结束的周期，确保数据是最终的、稳定的。

    周期边界定义：
    - 周线：周一到周日，下周一到来即为本周结束
    - 月线：月初到月末，下月1日到来即为本月结束
    - 季线：季初到季末，下季首月1日到来即为本季结束
    - 年线：年初到年末，下年1月1日到来即为本年结束
    """

    # 长周期集合
    LONG_INTERVALS: Set[Interval] = {
        Interval.WEEK,
        Interval.MONTH,
        Interval.SEASON,
        Interval.YEAR
    }

    def __init__(self, trading_calendar: TradingCalendarProtocol):
        """初始化周期边界检查器

        Args:
            trading_calendar: 交易日历实例（必填，通过 DI 注入）。
        """
        self._trading_calendar = trading_calendar

    @property
    def trading_calendar(self) -> TradingCalendarProtocol:
        """获取交易日历实例"""
        return self._trading_calendar

    def is_long_interval(self, interval: Union[Interval, str]) -> bool:
        """判断是否为长周期（调用 domain 纯函数）"""
        interval_value = interval.value if isinstance(interval, Interval) else interval
        return domain_is_long_interval(interval_value)

    def is_interval_complete(
        self,
        interval: Interval,
        target_date: date,
        today: Optional[date] = None
    ) -> bool:
        """判断指定日期所在的周期是否已结束（调用 domain 纯函数）"""
        return domain_is_interval_complete(interval.value, target_date, today)

    async def get_interval_end_date_async(self, interval: Interval, target_date: date) -> date:
        """异步获取指定日期所在周期的结束日期（最后一个交易日）

        Args:
            interval: 周期类型
            target_date: 目标日期

        Returns:
            date: 周期结束日期（最后一个交易日）
        """
        if interval == Interval.WEEK:
            return await self._get_week_end_date_async(target_date)
        elif interval == Interval.MONTH:
            return await self._get_month_end_date_async(target_date)
        elif interval == Interval.SEASON:
            return await self._get_season_end_date_async(target_date)
        elif interval == Interval.YEAR:
            return await self._get_year_end_date_async(target_date)
        else:
            return target_date

    async def get_last_complete_interval_end_async(
        self,
        interval: Interval,
        reference_date: Optional[date] = None,
        today: Optional[date] = None
    ) -> date:
        """异步获取最后一个已结束周期的结束日期。

        这是用于同步的主要接口，确保只同步已完全结束的周期。

        Args:
            interval: 周期类型
            reference_date: 参考日期，默认为今天
            today: 今天的日期，默认为系统当前日期（主要用于测试）

        Returns:
            date: 最后一个已结束周期的结束日期
        """
        if reference_date is None:
            reference_date = date.today()

        if today is None:
            today = date.today()

        # 对于非长周期，返回上一个交易日
        if not self.is_long_interval(interval):
            return await self._trading_calendar.get_previous_trading_day_async(reference_date)

        # 找到 reference_date 所在周期的开始日期
        interval_start = self._get_interval_start_date(interval, reference_date)

        # 如果当前周期未结束，返回上一个周期的结束日期
        if not self.is_interval_complete(interval, interval_start, today):
            return await self._get_previous_interval_end_date_async(interval, interval_start)

        # 如果当前周期已结束，返回当前周期的结束日期
        return await self.get_interval_end_date_async(interval, interval_start)

    # ==================== 周线相关方法 ====================

    def _get_interval_start_date(self, interval: Interval, target_date: date) -> date:
        """获取指定日期所在周期的开始日期（调用 domain 纯函数）"""
        return domain_get_interval_start_date(interval.value, target_date)

    async def _get_week_end_date_async(self, target_date: date) -> date:
        """异步获取指定日期所在周的结束日期（最后一个交易日）

        Args:
            target_date: 目标日期

        Returns:
            date: 周结束日期（最后一个交易日）
        """
        week_end = target_date + timedelta(days=6 - target_date.weekday())
        return await self._trading_calendar.get_previous_trading_day_async(week_end + timedelta(days=1))

    # ==================== 月线相关方法 ====================

    async def _get_month_end_date_async(self, target_date: date) -> date:
        """异步获取指定日期所在月的结束日期（最后一个交易日）

        Args:
            target_date: 目标日期

        Returns:
            date: 月结束日期（最后一个交易日）
        """
        if target_date.month == 12:
            last_day = date(target_date.year, 12, 31)
        else:
            last_day = date(target_date.year, target_date.month + 1, 1) - timedelta(days=1)
        return await self._trading_calendar.get_previous_trading_day_async(last_day + timedelta(days=1))

    # ==================== 季线相关方法 ====================

    def _get_quarter(self, target_date: date) -> int:
        """获取指定日期所在的季度（调用 domain 纯函数）"""
        return domain_get_quarter(target_date)

    def _get_quarter_start_month(self, quarter: int) -> int:
        """获取季度的起始月份（调用 domain 纯函数）"""
        return _get_quarter_start_month(quarter)

    def _get_quarter_end_month(self, quarter: int) -> int:
        """获取季度的结束月份（调用 domain 纯函数）"""
        return _get_quarter_end_month(quarter)

    async def _get_season_end_date_async(self, target_date: date) -> date:
        """异步获取指定日期所在季的结束日期（最后一个交易日）

        Args:
            target_date: 目标日期

        Returns:
            date: 季结束日期（最后一个交易日）
        """
        quarter = self._get_quarter(target_date)
        quarter_end_month = self._get_quarter_end_month(quarter)

        if quarter_end_month == 12:
            last_day = date(target_date.year, 12, 31)
        else:
            last_day = date(target_date.year, quarter_end_month + 1, 1) - timedelta(days=1)

        return await self._trading_calendar.get_previous_trading_day_async(last_day + timedelta(days=1))

    # ==================== 年线相关方法 ====================

    async def _get_year_end_date_async(self, target_date: date) -> date:
        """异步获取指定日期所在年的结束日期（最后一个交易日）

        Args:
            target_date: 目标日期

        Returns:
            date: 年结束日期（最后一个交易日）
        """
        last_day = date(target_date.year, 12, 31)
        return await self._trading_calendar.get_previous_trading_day_async(last_day + timedelta(days=1))

    # ==================== 辅助方法 ====================

    async def _get_previous_interval_end_date_async(
        self, interval: Interval, interval_start: date
    ) -> date:
        """异步获取上一个周期的结束日期

        Args:
            interval: 周期类型
            interval_start: 当前周期的开始日期

        Returns:
            date: 上一个周期的结束日期
        """
        if interval == Interval.WEEK:
            previous_week_end = interval_start - timedelta(days=1)
            return await self._get_week_end_date_async(previous_week_end)
        elif interval == Interval.MONTH:
            previous_month_end = interval_start - timedelta(days=1)
            return await self._get_month_end_date_async(previous_month_end)
        elif interval == Interval.SEASON:
            previous_season_end = interval_start - timedelta(days=1)
            return await self._get_season_end_date_async(previous_season_end)
        elif interval == Interval.YEAR:
            previous_year_end = interval_start - timedelta(days=1)
            return await self._get_year_end_date_async(previous_year_end)
        else:
            return interval_start - timedelta(days=1)

    # ==================== Scheduler Support Methods ====================

    async def is_last_trading_day_of_period(
        self,
        interval: Interval,
        today: date
    ) -> bool:
        """Check if today is the last trading day of the period.

        Per SCHED-02: This method reuses existing get_interval_end_date_async() logic.

        Args:
            interval: Period type (DAY, WEEK, MONTH, SEASON, YEAR)
            today: Today's date

        Returns:
            True if today is the last trading day in this period
        """
        if not self.is_long_interval(interval):
            # DAY and shorter intervals: sync daily at 23:00, no boundary check needed
            # For DAY, we consider every trading day as a "last day" to trigger sync
            return True

        # Get the period's end date (last trading day from trading calendar)
        period_end = await self.get_interval_end_date_async(interval, today)

        # Check if today matches that end date
        return today == period_end

    async def get_periods_to_sync_today(self, today: date) -> list[Interval]:
        """Get list of periods where today is the last trading day.

        Per SCHED-02: Returns all periods where today is the last trading day.
        Used by scheduler at 23:00 to determine which intervals to sync.

        Returns:
            List of Interval enums where today is the last trading day
        """
        # DAY is always synced at 23:00 (included by default)
        periods_to_sync = [Interval.DAY]

        # Check long intervals
        for interval in self.LONG_INTERVALS:
            if await self.is_last_trading_day_of_period(interval, today):
                periods_to_sync.append(interval)

        return periods_to_sync
