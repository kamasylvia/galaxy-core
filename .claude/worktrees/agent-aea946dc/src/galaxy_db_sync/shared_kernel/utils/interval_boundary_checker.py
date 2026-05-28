"""周期边界检查器

用于判断长周期（周、月、季、年）是否已完全结束，
并提供周期边界日期的查询功能。
"""

import threading
from datetime import date, timedelta
from typing import Optional, Set, Protocol, Union

from galaxy_db_sync.shared_kernel.enums.interval import Interval


class TradingCalendarProtocol(Protocol):
    """交易日历协议，定义所需接口。"""

    def get_previous_trading_day(self, target_date: date) -> date:
        """获取指定日期的上一个交易日。"""
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

    _trading_calendar_service = None
    _lock = threading.Lock()

    def __init__(self, trading_calendar: Optional[TradingCalendarProtocol] = None):
        """初始化周期边界检查器

        Args:
            trading_calendar: 交易日历实例，如果为 None 则使用默认服务
        """
        if trading_calendar is not None:
            self._trading_calendar = trading_calendar
        else:
            # 延迟初始化默认服务，避免循环导入
            # 使用锁确保线程安全
            with IntervalBoundaryChecker._lock:
                if IntervalBoundaryChecker._trading_calendar_service is None:
                    from galaxy_db_sync.database.services.trading_calendar import (
                        trading_calendar_service,
                    )
                    IntervalBoundaryChecker._trading_calendar_service = trading_calendar_service
                self._trading_calendar = IntervalBoundaryChecker._trading_calendar_service

    @property
    def trading_calendar(self) -> TradingCalendarProtocol:
        """获取交易日历实例"""
        return self._trading_calendar

    def is_long_interval(self, interval: Union[Interval, str]) -> bool:
        """判断是否为长周期

        Args:
            interval: 周期类型，可以是 Interval 枚举或字符串（如 "week", "month" 等）

        Returns:
            bool: 是否为长周期
        """
        if isinstance(interval, str):
            interval = Interval(interval)
        return interval in self.LONG_INTERVALS

    def is_interval_complete(
        self,
        interval: Interval,
        target_date: date,
        today: Optional[date] = None
    ) -> bool:
        """判断指定日期所在的周期是否已结束

        对于非长周期（分钟、小时、日线），始终返回 True。

        Args:
            interval: 周期类型
            target_date: 目标日期
            today: 今天的日期，默认为系统当前日期（主要用于测试）

        Returns:
            bool: 周期是否已结束

        Examples:
            >>> checker = IntervalBoundaryChecker()
            >>> # 假设今天是 2025-03-26（周三）
            >>> checker.is_interval_complete(Interval.WEEK, date(2025, 3, 24))  # 本周一
            False  # 本周未结束
            >>> checker.is_interval_complete(Interval.WEEK, date(2025, 3, 17))  # 上周一
            True  # 上周已结束
        """
        if not self.is_long_interval(interval):
            return True

        if today is None:
            today = date.today()

        if interval == Interval.WEEK:
            return self._is_week_complete(target_date, today)
        elif interval == Interval.MONTH:
            return self._is_month_complete(target_date, today)
        elif interval == Interval.SEASON:
            return self._is_season_complete(target_date, today)
        elif interval == Interval.YEAR:
            return self._is_year_complete(target_date, today)

        return True

    def get_interval_end_date(self, interval: Interval, target_date: date) -> date:
        """获取指定日期所在周期的结束日期（最后一个交易日）

        注意：返回的是周期内最后一个交易日，而不是周期的自然结束日期。

        Args:
            interval: 周期类型
            target_date: 目标日期

        Returns:
            date: 周期结束日期（最后一个交易日）

        Examples:
            >>> checker = IntervalBoundaryChecker()
            >>> checker.get_interval_end_date(Interval.WEEK, date(2025, 3, 24))  # 2025-03-24 是周一
            date(2025, 3, 28)  # 返回该周最后一个交易日（假设是周五）
        """
        if interval == Interval.WEEK:
            return self._get_week_end_date(target_date)
        elif interval == Interval.MONTH:
            return self._get_month_end_date(target_date)
        elif interval == Interval.SEASON:
            return self._get_season_end_date(target_date)
        elif interval == Interval.YEAR:
            return self._get_year_end_date(target_date)
        else:
            # 对于短周期，返回当天
            return target_date

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

    def get_last_complete_interval_end(
        self,
        interval: Interval,
        reference_date: Optional[date] = None,
        today: Optional[date] = None
    ) -> date:
        """获取最后一个已结束周期的结束日期

        这是用于同步的主要接口，确保只同步已完全结束的周期。

        Args:
            interval: 周期类型
            reference_date: 参考日期，默认为今天
            today: 今天的日期，默认为系统当前日期（主要用于测试）

        Returns:
            date: 最后一个已结束周期的结束日期

        Examples:
            >>> checker = IntervalBoundaryChecker()
            >>> # 假设今天是 2025-03-26（周三）
            >>> checker.get_last_complete_interval_end(Interval.WEEK)
            date(2025, 3, 21)  # 上周五（上周已结束）
            >>> checker.get_last_complete_interval_end(Interval.MONTH)
            date(2025, 2, 28)  # 上月末（上月已结束）
            >>> checker.get_last_complete_interval_end(Interval.YEAR)
            date(2024, 12, 31)  # 上年末（上年已结束）
        """
        if reference_date is None:
            reference_date = date.today()

        if today is None:
            today = date.today()

        # 对于非长周期，返回上一个交易日
        if not self.is_long_interval(interval):
            return self._trading_calendar.get_previous_trading_day(reference_date)

        # 找到 reference_date 所在周期的开始日期
        interval_start = self._get_interval_start_date(interval, reference_date)

        # 如果当前周期未结束，返回上一个周期的结束日期
        if not self.is_interval_complete(interval, interval_start, today):
            return self._get_previous_interval_end_date(interval, interval_start)

        # 如果当前周期已结束，返回当前周期的结束日期
        return self.get_interval_end_date(interval, interval_start)

    # ==================== 周线相关方法 ====================

    def _is_week_complete(self, target_date: date, today: date) -> bool:
        """判断指定日期所在的周是否已结束

        周结束的标志是下周一已经到来。

        Args:
            target_date: 目标日期
            today: 今天日期

        Returns:
            bool: 周是否已结束
        """
        # 获取目标日期所在周的周一（周一为一周的开始，weekday() 返回 0）
        week_start = target_date - timedelta(days=target_date.weekday())
        # 下周一
        next_week_start = week_start + timedelta(days=7)
        # 如果今天 >= 下周一，则本周已结束
        return today >= next_week_start

    def _get_week_end_date(self, target_date: date) -> date:
        """获取指定日期所在周的结束日期（最后一个交易日）

        Args:
            target_date: 目标日期

        Returns:
            date: 周结束日期（最后一个交易日）
        """
        # 获取目标日期所在周的周日
        week_end = target_date + timedelta(days=6 - target_date.weekday())
        # 获取该周最后一个交易日（周日通常不是交易日，回溯到周五或更早）
        return self._trading_calendar.get_previous_trading_day(week_end + timedelta(days=1))

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

    def _is_month_complete(self, target_date: date, today: date) -> bool:
        """判断指定日期所在的月是否已结束

        月结束的标志是下月1日已经到来。

        Args:
            target_date: 目标日期
            today: 今天日期

        Returns:
            bool: 月是否已结束
        """
        # 计算下月1日
        if target_date.month == 12:
            first_of_next_month = date(target_date.year + 1, 1, 1)
        else:
            first_of_next_month = date(target_date.year, target_date.month + 1, 1)
        # 如果今天 >= 下月1日，则本月已结束
        return today >= first_of_next_month

    def _get_month_end_date(self, target_date: date) -> date:
        """获取指定日期所在月的结束日期（最后一个交易日）

        Args:
            target_date: 目标日期

        Returns:
            date: 月结束日期（最后一个交易日）
        """
        # 计算本月最后一天
        if target_date.month == 12:
            last_day = date(target_date.year, 12, 31)
        else:
            # 下月1日 - 1天 = 本月最后一天
            last_day = date(target_date.year, target_date.month + 1, 1) - timedelta(days=1)
        # 获取最后一个交易日
        return self._trading_calendar.get_previous_trading_day(last_day + timedelta(days=1))

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
        """获取指定日期所在的季度

        Args:
            target_date: 目标日期

        Returns:
            int: 季度（1-4）
        """
        return (target_date.month - 1) // 3 + 1

    def _get_quarter_start_month(self, quarter: int) -> int:
        """获取季度的起始月份

        Args:
            quarter: 季度（1-4）

        Returns:
            int: 起始月份（1, 4, 7, 10）
        """
        return (quarter - 1) * 3 + 1

    def _get_quarter_end_month(self, quarter: int) -> int:
        """获取季度的结束月份

        Args:
            quarter: 季度（1-4）

        Returns:
            int: 结束月份（3, 6, 9, 12）
        """
        return quarter * 3

    def _is_season_complete(self, target_date: date, today: date) -> bool:
        """判断指定日期所在的季是否已结束

        季结束的标志是下季首月1日已经到来。

        Args:
            target_date: 目标日期
            today: 今天日期

        Returns:
            bool: 季是否已结束
        """
        quarter = self._get_quarter(target_date)

        # 计算下季首月1日
        if quarter == 4:
            first_of_next_quarter = date(target_date.year + 1, 1, 1)
        else:
            first_of_next_quarter = date(target_date.year, self._get_quarter_start_month(quarter + 1), 1)

        # 如果今天 >= 下季首月1日，则本季已结束
        return today >= first_of_next_quarter

    def _get_season_end_date(self, target_date: date) -> date:
        """获取指定日期所在季的结束日期（最后一个交易日）

        Args:
            target_date: 目标日期

        Returns:
            date: 季结束日期（最后一个交易日）
        """
        quarter = self._get_quarter(target_date)
        quarter_end_month = self._get_quarter_end_month(quarter)

        # 计算本季最后一天
        if quarter_end_month == 12:
            last_day = date(target_date.year, 12, 31)
        else:
            last_day = date(target_date.year, quarter_end_month + 1, 1) - timedelta(days=1)

        # 获取最后一个交易日
        return self._trading_calendar.get_previous_trading_day(last_day + timedelta(days=1))

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

    def _is_year_complete(self, target_date: date, today: date) -> bool:
        """判断指定日期所在的年是否已结束

        年结束的标志是下年1月1日已经到来。

        Args:
            target_date: 目标日期
            today: 今天日期

        Returns:
            bool: 年是否已结束
        """
        first_of_next_year = date(target_date.year + 1, 1, 1)
        return today >= first_of_next_year

    def _get_year_end_date(self, target_date: date) -> date:
        """获取指定日期所在年的结束日期（最后一个交易日）

        Args:
            target_date: 目标日期

        Returns:
            date: 年结束日期（最后一个交易日）
        """
        last_day = date(target_date.year, 12, 31)
        return self._trading_calendar.get_previous_trading_day(last_day + timedelta(days=1))

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

    def _get_interval_start_date(self, interval: Interval, target_date: date) -> date:
        """获取指定日期所在周期的开始日期

        Args:
            interval: 周期类型
            target_date: 目标日期

        Returns:
            date: 周期开始日期
        """
        if interval == Interval.WEEK:
            # 周一为一周的开始
            return target_date - timedelta(days=target_date.weekday())
        elif interval == Interval.MONTH:
            # 月初为一个月的开始
            return date(target_date.year, target_date.month, 1)
        elif interval == Interval.SEASON:
            # 季初为一个季度的开始
            quarter = self._get_quarter(target_date)
            start_month = self._get_quarter_start_month(quarter)
            return date(target_date.year, start_month, 1)
        elif interval == Interval.YEAR:
            # 年初为一年的开始
            return date(target_date.year, 1, 1)
        else:
            return target_date

    def _get_previous_interval_end_date(self, interval: Interval, interval_start: date) -> date:
        """获取上一个周期的结束日期

        Args:
            interval: 周期类型
            interval_start: 当前周期的开始日期

        Returns:
            date: 上一个周期的结束日期
        """
        if interval == Interval.WEEK:
            # 上一周的最后一天 = 本周一 - 1天
            previous_week_end = interval_start - timedelta(days=1)
            return self._get_week_end_date(previous_week_end)
        elif interval == Interval.MONTH:
            # 上月最后一天 = 本月1日 - 1天
            previous_month_end = interval_start - timedelta(days=1)
            return self._get_month_end_date(previous_month_end)
        elif interval == Interval.SEASON:
            # 上季最后一天 = 本季首月1日 - 1天
            previous_season_end = interval_start - timedelta(days=1)
            return self._get_season_end_date(previous_season_end)
        elif interval == Interval.YEAR:
            # 上年最后一天 = 本年1月1日 - 1天
            previous_year_end = interval_start - timedelta(days=1)
            return self._get_year_end_date(previous_year_end)
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

