"""K 线数据完整性检查器.

提供分层数据完整性检测策略，支持长周期和短周期不同的检测方法。
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple, Union

from galaxy_db_sync.database.services.kline import kline_service
from galaxy_db_sync.database.services.trading_calendar import trading_calendar_service
from galaxy_db_sync.shared_kernel.enums.interval import Interval
from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.models.kline import INTERVAL_MODEL_MAP

logger = logging.getLogger(__name__)


class CompletenessLevel(Enum):
    """数据完整性级别."""

    COMPLETE = auto()  # 数据完整
    PARTIAL = auto()  # 部分缺失
    EMPTY = auto()  # 完全缺失


@dataclass
class CompletenessResult:
    """数据完整性检查结果."""

    is_complete: bool  # 是否完整
    missing_count: int  # 缺失数据点数量
    total_count: int  # 应有点数
    coverage_ratio: float  # 覆盖率 (0.0 - 1.0)
    missing_ranges: List[Tuple[date, date]]  # 缺失的日期范围列表
    check_method: str  # 使用的检测方法

    def __str__(self) -> str:
        return (
            f"CompletenessResult("
            f"complete={self.is_complete}, "
            f"missing={self.missing_count}/{self.total_count}, "
            f"coverage={self.coverage_ratio:.2%}, "
            f"method={self.check_method})"
        )


class BaseCompletenessChecker(ABC):
    """数据完整性检查器基类."""

    @abstractmethod
    def check(
        self,
        symbol: str,
        interval: Interval,
        start_date: date,
        end_date: date,
    ) -> CompletenessResult:
        """检查数据完整性.

        Args:
            symbol: 证券代码
            interval: K 线周期
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            CompletenessResult: 完整性检查结果
        """
        pass



class LongPeriodChecker(BaseCompletenessChecker):
    """长周期数据完整性检查器 (月线及以上).

    长周期数据使用连续性检测，因为长周期数据点数量较少，
    且每个数据点都代表一个完整的周期，可以通过连续性来判断完整性。
    """

    def __init__(self):
        """初始化检查器，创建期望周期缓存."""
        self._expected_periods_cache: dict = {}

    def _get_cache_key(
        self, interval: Interval, start_date: date, end_date: date
    ) -> tuple:
        """生成缓存键."""
        return (interval.value, start_date, end_date)

    def _get_expected_periods(
        self, interval: Interval, start_date: date, end_date: date
    ) -> List[Tuple[date, date]]:
        """获取期望周期列表（带缓存）."""
        cache_key = self._get_cache_key(interval, start_date, end_date)

        if cache_key not in self._expected_periods_cache:
            self._expected_periods_cache[cache_key] = self._generate_expected_periods(
                interval, start_date, end_date
            )

        return self._expected_periods_cache[cache_key]

    def clear_cache(self):
        """清空期望周期缓存."""
        self._expected_periods_cache.clear()

    def check(
        self,
        symbol: str,
        interval: Interval,
        start_date: date,
        end_date: date,
    ) -> CompletenessResult:
        """检查长周期数据完整性."""
        logger.debug(f"{symbol}: 使用长周期连续性检测 ({interval.value})")

        # 1. 使用同步数据库连接查询数据
        interval_lower = interval.value.lower()
        if interval_lower not in INTERVAL_MODEL_MAP:
            raise ValueError(f"不支持的周期: {interval_lower}")

        table_model = INTERVAL_MODEL_MAP[interval_lower]

        session = db_manager.get_session()
        try:
            from sqlalchemy import and_, select

            stmt = (
                select(table_model.trade_time)
                .where(
                    and_(
                        table_model.symbol == symbol,
                        table_model.trade_time >= datetime.combine(start_date, datetime.min.time()),
                        table_model.trade_time <= datetime.combine(end_date, datetime.max.time()),
                    )
                )
                .order_by(table_model.trade_time)
            )

            result = session.execute(stmt)
            rows = result.all()

            existing_dates: Set[date] = set()
            for row in rows:
                trade_time = row[0]
                if isinstance(trade_time, datetime):
                    existing_dates.add(trade_time.date())
                else:
                    existing_dates.add(trade_time)
        finally:
            session.close()

        # 2. 确定实际应该检查的日期范围
        # 对于年线，基于数据库中实际存在的数据年份范围检查
        # 这样可以避免将 ETF 上市前的年份或退市后的年份误判为缺失
        actual_start_date = start_date
        actual_end_date = end_date
        if interval == Interval.YEAR and existing_dates:
            earliest_data_date = min(existing_dates)
            latest_data_date = max(existing_dates)
            earliest_data_year_start = date(earliest_data_date.year, 1, 1)
            latest_data_year_end = date(latest_data_date.year, 12, 31)

            # 调整起始年份
            if earliest_data_year_start > start_date:
                logger.debug(
                    f"{symbol}: 调整年线检查起点 {start_date} -> {earliest_data_year_start} "
                    f"(基于最早数据年份 {earliest_data_date.year})"
                )
                actual_start_date = earliest_data_year_start

            # 调整结束年份
            if latest_data_year_end < end_date:
                logger.debug(
                    f"{symbol}: 调整年线检查终点 {end_date} -> {latest_data_year_end} "
                    f"(基于最新数据年份 {latest_data_date.year})"
                )
                actual_end_date = latest_data_year_end

        # 3. 根据周期生成期望的日期序列（基于调整后的起止日期）
        # 返回 (period_start, period_end, first_trading_day) 元组
        expected_periods = self._get_expected_periods(interval, actual_start_date, actual_end_date)

        # 4. 提取期望的第一个交易日和周期边界映射
        expected_first_trading_days: Set[date] = set()
        period_to_first_trading_day: Dict[Tuple[date, date], date] = {}
        for period_start, period_end, first_trading_day in expected_periods:
            expected_first_trading_days.add(first_trading_day)
            period_to_first_trading_day[(period_start, period_end)] = first_trading_day

        # 5. 计算缺失的日期（根据周期类型使用不同的比较策略）
        if interval == Interval.YEAR:
            # 年线：按年份比较
            existing_years = {d.year for d in existing_dates}
            expected_years = {d.year for d in expected_first_trading_days}
            missing_years = expected_years - existing_years
            year_to_first_trading_day = {d.year: d for d in expected_first_trading_days}
            missing_dates = {year_to_first_trading_day[y] for y in missing_years}
        elif interval == Interval.SEASON:
            # 季线：按年份+季度比较
            def get_quarter(d: date) -> tuple[int, int]:
                return (d.year, (d.month - 1) // 3 + 1)
            existing_seasons = {get_quarter(d) for d in existing_dates}
            expected_seasons = {get_quarter(d) for d in expected_first_trading_days}
            missing_seasons = expected_seasons - existing_seasons
            season_to_first_trading_day = {get_quarter(d): d for d in expected_first_trading_days}
            missing_dates = {season_to_first_trading_day[s] for s in missing_seasons}
        elif interval == Interval.MONTH:
            # 月线：按年份+月份比较
            existing_months = {(d.year, d.month) for d in existing_dates}
            expected_months = {(d.year, d.month) for d in expected_first_trading_days}
            missing_months = expected_months - existing_months
            month_to_first_trading_day = {(d.year, d.month): d for d in expected_first_trading_days}
            missing_dates = {month_to_first_trading_day[m] for m in missing_months}
        elif interval == Interval.WEEK:
            # 周线：按 ISO 周比较
            def get_iso_week(d: date) -> tuple[int, int]:
                iso_cal = d.isocalendar()
                return (iso_cal[0], iso_cal[1])  # (year, week_number)
            existing_weeks = {get_iso_week(d) for d in existing_dates}
            expected_weeks = {get_iso_week(d) for d in expected_first_trading_days}
            missing_weeks = expected_weeks - existing_weeks
            week_to_first_trading_day = {get_iso_week(d): d for d in expected_first_trading_days}
            missing_dates = {week_to_first_trading_day[w] for w in missing_weeks}
        else:
            # 其他周期：按具体日期比较（日线等短周期）
            missing_dates = expected_first_trading_days - existing_dates

        # 6. 合并连续的缺失日期为范围（使用周期边界）
        # 需要将 first_trading_day 映射回 period 边界
        first_trading_day_to_period = {v: k for k, v in period_to_first_trading_day.items()}
        missing_ranges = self._merge_to_ranges(sorted(missing_dates), first_trading_day_to_period)

        # 7. 构建结果
        total_count = len(expected_first_trading_days)
        missing_count = len(missing_dates)
        coverage_ratio = (
            (total_count - missing_count) / total_count if total_count > 0 else 0.0
        )

        return CompletenessResult(
            is_complete=missing_count == 0,
            missing_count=missing_count,
            total_count=total_count,
            coverage_ratio=coverage_ratio,
            missing_ranges=missing_ranges,
            check_method="long_period_continuity",
        )

    async def check_async(
        self,
        symbol: str,
        interval: Interval,
        start_date: date,
        end_date: date,
    ) -> CompletenessResult:
        """检查长周期数据完整性（异步版本）."""
        logger.debug(f"{symbol}: 使用长周期连续性检测 ({interval.value}) [async]")

        # 1. 查询数据库中的数据（使用异步方法）
        db_data = await kline_service.query_kline_from_db(
            symbols=[symbol],
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            interval=interval.value,
        )

        existing_dates: Set[date] = set()
        if symbol in db_data and not db_data[symbol].empty:
            existing_dates = set(
                d.date() if isinstance(d, datetime) else d
                for d in db_data[symbol].index
            )

        # 2. 确定实际应该检查的日期范围（年线特殊处理）
        actual_start_date = start_date
        actual_end_date = end_date
        if interval == Interval.YEAR and existing_dates:
            earliest_data_date = min(existing_dates)
            latest_data_date = max(existing_dates)
            earliest_data_year_start = date(earliest_data_date.year, 1, 1)
            latest_data_year_end = date(latest_data_date.year, 12, 31)

            if earliest_data_year_start > start_date:
                logger.debug(
                    f"{symbol}: 调整年线检查起点 {start_date} -> {earliest_data_year_start}"
                )
                actual_start_date = earliest_data_year_start

            if latest_data_year_end < end_date:
                logger.debug(
                    f"{symbol}: 调整年线检查终点 {end_date} -> {latest_data_year_end}"
                )
                actual_end_date = latest_data_year_end

        # 3. 根据周期生成期望的日期序列（异步方法）
        expected_periods = await self._generate_expected_periods_async(
            interval, actual_start_date, actual_end_date
        )

        # 4. 提取期望的第一个交易日和周期边界映射
        expected_first_trading_days: Set[date] = set()
        period_to_first_trading_day: Dict[Tuple[date, date], date] = {}
        for period_start, period_end, first_trading_day in expected_periods:
            expected_first_trading_days.add(first_trading_day)
            period_to_first_trading_day[(period_start, period_end)] = first_trading_day

        # 5. 计算缺失的日期（根据周期类型使用不同的比较策略）
        if interval == Interval.YEAR:
            # 年线：按年份比较
            existing_years = {d.year for d in existing_dates}
            expected_years = {d.year for d in expected_first_trading_days}
            missing_years = expected_years - existing_years
            year_to_first_trading_day = {d.year: d for d in expected_first_trading_days}
            missing_dates = {year_to_first_trading_day[y] for y in missing_years}
        elif interval == Interval.SEASON:
            # 季线：按年份+季度比较
            def get_quarter(d: date) -> tuple[int, int]:
                return (d.year, (d.month - 1) // 3 + 1)
            existing_seasons = {get_quarter(d) for d in existing_dates}
            expected_seasons = {get_quarter(d) for d in expected_first_trading_days}
            missing_seasons = expected_seasons - existing_seasons
            season_to_first_trading_day = {get_quarter(d): d for d in expected_first_trading_days}
            missing_dates = {season_to_first_trading_day[s] for s in missing_seasons}
        elif interval == Interval.MONTH:
            # 月线：按年份+月份比较
            existing_months = {(d.year, d.month) for d in existing_dates}
            expected_months = {(d.year, d.month) for d in expected_first_trading_days}
            missing_months = expected_months - existing_months
            month_to_first_trading_day = {(d.year, d.month): d for d in expected_first_trading_days}
            missing_dates = {month_to_first_trading_day[m] for m in missing_months}
        elif interval == Interval.WEEK:
            # 周线：按 ISO 周比较
            def get_iso_week(d: date) -> tuple[int, int]:
                iso_cal = d.isocalendar()
                return (iso_cal[0], iso_cal[1])  # (year, week_number)
            existing_weeks = {get_iso_week(d) for d in existing_dates}
            expected_weeks = {get_iso_week(d) for d in expected_first_trading_days}
            missing_weeks = expected_weeks - existing_weeks
            week_to_first_trading_day = {get_iso_week(d): d for d in expected_first_trading_days}
            missing_dates = {week_to_first_trading_day[w] for w in missing_weeks}
        else:
            # 其他周期：按具体日期比较（日线等短周期）
            missing_dates = expected_first_trading_days - existing_dates

        # 6. 合并连续的缺失日期为范围
        first_trading_day_to_period = {v: k for k, v in period_to_first_trading_day.items()}
        missing_ranges = self._merge_to_ranges(sorted(missing_dates), first_trading_day_to_period)

        # 7. 构建结果
        total_count = len(expected_first_trading_days)
        missing_count = len(missing_dates)
        coverage_ratio = (
            (total_count - missing_count) / total_count if total_count > 0 else 0.0
        )

        return CompletenessResult(
            is_complete=missing_count == 0,
            missing_count=missing_count,
            total_count=total_count,
            coverage_ratio=coverage_ratio,
            missing_ranges=missing_ranges,
            check_method="long_period_continuity_async",
        )

    def _generate_expected_periods(
        self,
        interval: Interval,
        start_date: date,
        end_date: date,
    ) -> List[Tuple[date, date, date]]:
        """生成长周期期望的周期列表，返回 (周期开始, 周期结束, 第一个交易日) 的列表.

        周期开始日期是周期的第一天（月初/季初/年初），
        周期结束日期是该周期的最后一天（月末/季末/年末），
        第一个交易日是该周期的第一个交易日（用于与数据库数据比较）。

        优化：一次性获取整个日期范围的交易日历，避免每个周期单独查询。
        """
        periods = []
        current = start_date

        # 一次性获取整个日期范围的交易日历
        all_trading_days = trading_calendar_service.get_trading_days(start_date, end_date)
        trading_days_set = set(all_trading_days)

        def find_first_trading_day(period_start: date, period_end: date) -> Optional[date]:
            """在指定周期内找到第一个交易日."""
            current_day = period_start
            while current_day <= period_end:
                if current_day in trading_days_set:
                    return current_day
                current_day += timedelta(days=1)
            return None

        if interval == Interval.WEEK:
            # 周线：每周为一个周期
            # period_start 是周一，period_end 是周日
            # 使用 weekday() 来找到周一（weekday() 返回 0 表示周一）
            # 先调整 current 到所在周的周一
            current = current - timedelta(days=current.weekday())
            while current <= end_date:
                period_start = current  # 周一
                period_end = min(current + timedelta(days=6), end_date)  # 周日
                first_trading = find_first_trading_day(period_start, period_end)
                if first_trading:
                    periods.append((period_start, period_end, first_trading))
                current = current + timedelta(days=7)  # 下周一

        elif interval == Interval.MONTH:
            while current <= end_date:
                period_start = current.replace(day=1)
                if current.month == 12:
                    next_period_start = current.replace(
                        year=current.year + 1,
                        month=1,
                        day=1,
                    )
                else:
                    next_period_start = current.replace(month=current.month + 1, day=1)
                period_end = min(next_period_start - timedelta(days=1), end_date)
                first_trading = find_first_trading_day(period_start, period_end)
                if first_trading:
                    periods.append((period_start, period_end, first_trading))
                current = next_period_start

        elif interval == Interval.SEASON:
            while current <= end_date:
                quarter = (current.month - 1) // 3 + 1
                period_start = date(current.year, (quarter - 1) * 3 + 1, 1)
                if quarter == 4:
                    next_period_start = date(current.year + 1, 1, 1)
                else:
                    next_period_start = date(current.year, quarter * 3 + 1, 1)
                period_end = min(next_period_start - timedelta(days=1), end_date)
                first_trading = find_first_trading_day(period_start, period_end)
                if first_trading:
                    periods.append((period_start, period_end, first_trading))
                current = next_period_start

        elif interval == Interval.YEAR:
            while current <= end_date:
                period_start = date(current.year, 1, 1)
                next_period_start = date(current.year + 1, 1, 1)
                period_end = min(next_period_start - timedelta(days=1), end_date)
                first_trading = find_first_trading_day(period_start, period_end)
                if first_trading:
                    periods.append((period_start, period_end, first_trading))
                current = next_period_start

        return periods

    async def _generate_expected_periods_async(
        self,
        interval: Interval,
        start_date: date,
        end_date: date,
    ) -> List[Tuple[date, date, date]]:
        """生成长周期期望的周期列表（异步版本）."""
        periods = []
        current = start_date

        # 一次性获取整个日期范围的交易日历（异步）
        all_trading_days = await trading_calendar_service.get_trading_days_async(start_date, end_date)
        trading_days_set = set(all_trading_days)

        async def find_first_trading_day_async(period_start: date, period_end: date) -> Optional[date]:
            """在指定周期内找到第一个交易日."""
            current_day = period_start
            while current_day <= period_end:
                if current_day in trading_days_set:
                    return current_day
                current_day += timedelta(days=1)
            return None

        if interval == Interval.WEEK:
            # 周线：每周为一个周期
            # period_start 是周一，period_end 是周日
            current = current - timedelta(days=current.weekday())  # 调整到周一
            while current <= end_date:
                period_start = current  # 周一
                period_end = min(current + timedelta(days=6), end_date)  # 周日
                first_trading = await find_first_trading_day_async(period_start, period_end)
                if first_trading:
                    periods.append((period_start, period_end, first_trading))
                current = current + timedelta(days=7)  # 下周一

        elif interval == Interval.MONTH:
            while current <= end_date:
                period_start = current.replace(day=1)
                if current.month == 12:
                    next_period_start = current.replace(
                        year=current.year + 1,
                        month=1,
                        day=1,
                    )
                else:
                    next_period_start = current.replace(month=current.month + 1, day=1)
                period_end = min(next_period_start - timedelta(days=1), end_date)
                first_trading = await find_first_trading_day_async(period_start, period_end)
                if first_trading:
                    periods.append((period_start, period_end, first_trading))
                current = next_period_start

        elif interval == Interval.SEASON:
            while current <= end_date:
                quarter = (current.month - 1) // 3 + 1
                period_start = date(current.year, (quarter - 1) * 3 + 1, 1)
                if quarter == 4:
                    next_period_start = date(current.year + 1, 1, 1)
                else:
                    next_period_start = date(current.year, quarter * 3 + 1, 1)
                period_end = min(next_period_start - timedelta(days=1), end_date)
                first_trading = await find_first_trading_day_async(period_start, period_end)
                if first_trading:
                    periods.append((period_start, period_end, first_trading))
                current = next_period_start

        elif interval == Interval.YEAR:
            while current <= end_date:
                period_start = date(current.year, 1, 1)
                next_period_start = date(current.year + 1, 1, 1)
                period_end = min(next_period_start - timedelta(days=1), end_date)
                first_trading = await find_first_trading_day_async(period_start, period_end)
                if first_trading:
                    periods.append((period_start, period_end, first_trading))
                current = next_period_start

        return periods

    def _merge_to_ranges(
        self,
        missing_dates: List[date],
        first_trading_day_to_period: Dict[date, Tuple[date, date]],
    ) -> List[Tuple[date, date]]:
        """将连续的缺失日期合并为范围，使用周期边界作为范围.

        Args:
            missing_dates: 缺失的第一个交易日列表
            first_trading_day_to_period: 第一个交易日到周期边界的映射
                {first_trading_day: (period_start, period_end), ...}

        Returns:
            缺失范围列表 [(范围开始, 范围结束), ...]
            范围开始是周期的第一天（年初/季初/月初），
            范围结束是周期的最后一天（年末/季末/月末）。
        """
        if not missing_dates:
            return []

        ranges = []
        current_range_start = None
        current_range_end = None

        for missing_first_day in sorted(missing_dates):
            if missing_first_day not in first_trading_day_to_period:
                continue

            period_start, period_end = first_trading_day_to_period[missing_first_day]

            if current_range_start is None:
                # 第一个缺失周期
                current_range_start = period_start
                current_range_end = period_end
            elif period_start <= current_range_end + timedelta(days=1):
                # 当前周期与上一个连续，扩展范围
                current_range_end = period_end
            else:
                # 不连续，保存当前范围并开始新范围
                ranges.append((current_range_start, current_range_end))
                current_range_start = period_start
                current_range_end = period_end

        # 添加最后一个范围
        if current_range_start is not None:
            ranges.append((current_range_start, current_range_end))

        return ranges


class ShortPeriodChecker(BaseCompletenessChecker):
    """短周期数据完整性检查器 (日线及以下).

    短周期数据使用交易日对比检测，因为短周期数据点数量多，
    且每个交易日都有数据，需要通过交易日历来判断哪些日期应该有数据。

    注意：周线及以上使用 LongPeriodChecker，因为周线每周只有一条记录。
    """

    def __init__(self):
        """初始化检查器，创建交易日缓存."""
        self._trading_days_cache: dict = {}

    def _get_cache_key(self, start_date: date, end_date: date) -> tuple:
        """生成缓存键."""
        return (start_date, end_date)

    def _get_trading_days(self, start_date: date, end_date: date) -> List[date]:
        """获取交易日列表（带缓存）."""
        cache_key = self._get_cache_key(start_date, end_date)

        if cache_key not in self._trading_days_cache:
            self._trading_days_cache[cache_key] = trading_calendar_service.get_trading_days(
                start_date, end_date
            )

        return self._trading_days_cache[cache_key]

    async def _get_trading_days_async(self, start_date: date, end_date: date) -> List[date]:
        """获取交易日列表（异步版本，带缓存）."""
        cache_key = self._get_cache_key(start_date, end_date)

        if cache_key not in self._trading_days_cache:
            self._trading_days_cache[cache_key] = await trading_calendar_service.get_trading_days_async(
                start_date, end_date
            )

        return self._trading_days_cache[cache_key]

    def clear_cache(self):
        """清空交易日缓存."""
        self._trading_days_cache.clear()

    def check(
        self,
        symbol: str,
        interval: Interval,
        start_date: date,
        end_date: date,
    ) -> CompletenessResult:
        """检查短周期数据完整性."""
        logger.debug(f"{symbol}: 使用短周期交易日对比检测 ({interval.value})")

        # 1. 获取交易日历（使用缓存）
        trading_days = self._get_trading_days(start_date, end_date)

        if not trading_days:
            logger.warning(f"{symbol}: 在指定范围内没有找到交易日")
            return CompletenessResult(
                is_complete=True,
                missing_count=0,
                total_count=0,
                coverage_ratio=1.0,
                missing_ranges=[],
                check_method="short_period_trading_day",
            )

        # 2. 使用同步数据库连接查询数据
        interval_lower = interval.value.lower()
        if interval_lower not in INTERVAL_MODEL_MAP:
            raise ValueError(f"不支持的周期: {interval_lower}")

        table_model = INTERVAL_MODEL_MAP[interval_lower]

        session = db_manager.get_session()
        try:
            from sqlalchemy import and_, select

            stmt = (
                select(table_model.trade_time)
                .where(
                    and_(
                        table_model.symbol == symbol,
                        table_model.trade_time >= datetime.combine(start_date, datetime.min.time()),
                        table_model.trade_time <= datetime.combine(end_date, datetime.max.time()),
                    )
                )
                .order_by(table_model.trade_time)
            )

            result = session.execute(stmt)
            rows = result.all()

            existing_dates: Set[date] = set()
            for row in rows:
                trade_time = row[0]
                if isinstance(trade_time, datetime):
                    existing_dates.add(trade_time.date())
                else:
                    existing_dates.add(trade_time)
        finally:
            session.close()

        # 3. 计算缺失的交易日
        trading_days_set = set(trading_days)
        missing_dates = sorted(trading_days_set - existing_dates)

        # 4. 合并连续的缺失日期为范围
        missing_ranges = self._merge_to_ranges(missing_dates)

        # 5. 构建结果
        total_count = len(trading_days)
        missing_count = len(missing_dates)
        coverage_ratio = (
            (total_count - missing_count) / total_count if total_count > 0 else 0.0
        )

        return CompletenessResult(
            is_complete=missing_count == 0,
            missing_count=missing_count,
            total_count=total_count,
            coverage_ratio=coverage_ratio,
            missing_ranges=missing_ranges,
            check_method="short_period_trading_day",
        )

    async def check_async(
        self,
        symbol: str,
        interval: Interval,
        start_date: date,
        end_date: date,
    ) -> CompletenessResult:
        """检查短周期数据完整性（异步版本）."""
        logger.debug(f"{symbol}: 使用短周期交易日对比检测 ({interval.value}) [async]")

        # 1. 获取交易日历（异步方法）
        trading_days = await self._get_trading_days_async(start_date, end_date)

        if not trading_days:
            logger.warning(f"{symbol}: 在指定范围内没有找到交易日")
            return CompletenessResult(
                is_complete=True,
                missing_count=0,
                total_count=0,
                coverage_ratio=1.0,
                missing_ranges=[],
                check_method="short_period_trading_day_async",
            )

        # 2. 查询数据库中的数据（异步方法）
        db_data = await kline_service.query_kline_from_db(
            symbols=[symbol],
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            interval=interval.value,
        )

        existing_dates: Set[date] = set()
        if symbol in db_data and not db_data[symbol].empty:
            existing_dates = set(
                d.date() if isinstance(d, datetime) else d
                for d in db_data[symbol].index
            )

        # 3. 计算缺失的交易日
        trading_days_set = set(trading_days)
        missing_dates = sorted(trading_days_set - existing_dates)

        # 4. 合并连续的缺失日期为范围
        missing_ranges = self._merge_to_ranges(missing_dates)

        # 5. 构建结果
        total_count = len(trading_days)
        missing_count = len(missing_dates)
        coverage_ratio = (
            (total_count - missing_count) / total_count if total_count > 0 else 0.0
        )

        return CompletenessResult(
            is_complete=missing_count == 0,
            missing_count=missing_count,
            total_count=total_count,
            coverage_ratio=coverage_ratio,
            missing_ranges=missing_ranges,
            check_method="short_period_trading_day_async",
        )

    def _merge_to_ranges(self, dates: List[date]) -> List[Tuple[date, date]]:
        """将连续的日期合并为范围."""
        if not dates:
            return []

        ranges = []
        range_start = dates[0]
        range_end = dates[0]

        for i in range(1, len(dates)):
            # 检查是否连续（交易日应该连续）
            if dates[i] > range_end + timedelta(days=1):
                ranges.append((range_start, range_end))
                range_start = dates[i]
            range_end = dates[i]

        ranges.append((range_start, range_end))
        return ranges


class KlineCompletenessChecker:
    """K 线数据完整性检查器.

    根据 K 线周期自动选择合适的检测策略：
    - 周线及以上：使用连续性检测（每周/每月/每季/每年只有一条记录）
    - 日线及以下：使用交易日对比检测（每个交易日都有数据）
    """

    # 定义长周期阈值：周线及以上使用连续性检测
    # 原因：周线数据每周只有一条记录（trade_time 是周开始时间），
    # 不是每个交易日都有数据，需要按周检测连续性而非按交易日对比
    LONG_PERIOD_THRESHOLD = Interval.WEEK

    def __init__(self):
        """初始化检查器."""
        self._long_checker = LongPeriodChecker()
        self._short_checker = ShortPeriodChecker()

    def check(
        self,
        symbol: str,
        interval: Union[Interval, str],
        start_date: Union[date, str, datetime],
        end_date: Union[date, str, datetime],
    ) -> CompletenessResult:
        """检查 K 线数据完整性.

        Args:
            symbol: 证券代码
            interval: K 线周期 (Interval 枚举或字符串)
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            CompletenessResult: 完整性检查结果
        """
        # 标准化参数
        interval_enum = self._normalize_interval(interval)
        start_date_obj = self._normalize_date(
            start_date,
            interval_enum,
            is_end_date=False,
        )
        end_date_obj = self._normalize_date(
            end_date,
            interval_enum,
            is_end_date=True,
        )

        logger.debug(
            f"{symbol}: 开始数据完整性检查 "
            f"({interval_enum.value}, {start_date_obj} ~ {end_date_obj})"
        )

        # 根据周期选择合适的检查器
        if self._is_long_period(interval_enum):
            result = self._long_checker.check(
                symbol, interval_enum, start_date_obj, end_date_obj
            )
        else:
            result = self._short_checker.check(
                symbol, interval_enum, start_date_obj, end_date_obj
            )

        logger.debug(f"{symbol}: 完整性检查完成 - {result}")
        return result

    async def check_async(
        self,
        symbol: str,
        interval: Union[Interval, str],
        start_date: Union[date, str, datetime],
        end_date: Union[date, str, datetime],
    ) -> CompletenessResult:
        """检查 K 线数据完整性（异步版本）.

        Args:
            symbol: 证券代码
            interval: K 线周期 (Interval 枚举或字符串)
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            CompletenessResult: 完整性检查结果
        """
        # 标准化参数
        interval_enum = self._normalize_interval(interval)
        start_date_obj = self._normalize_date(
            start_date,
            interval_enum,
            is_end_date=False,
        )
        end_date_obj = self._normalize_date(
            end_date,
            interval_enum,
            is_end_date=True,
        )

        logger.debug(
            f"{symbol}: 开始数据完整性检查 [async] "
            f"({interval_enum.value}, {start_date_obj} ~ {end_date_obj})"
        )

        # 根据周期选择合适的检查器
        if self._is_long_period(interval_enum):
            result = await self._long_checker.check_async(
                symbol, interval_enum, start_date_obj, end_date_obj
            )
        else:
            result = await self._short_checker.check_async(
                symbol, interval_enum, start_date_obj, end_date_obj
            )

        logger.debug(f"{symbol}: 完整性检查完成 - {result}")
        return result

    def get_missing_dates(
        self,
        symbol: str,
        interval: Union[Interval, str],
        start_date: Union[date, str, datetime],
        end_date: Union[date, str, datetime],
    ) -> List[date]:
        """获取缺失的日期列表.

        Args:
            symbol: 证券代码
            interval: K 线周期
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            List[date]: 缺失的日期列表
        """
        result = self.check(symbol, interval, start_date, end_date)

        # 展开缺失范围
        missing_dates = []
        for range_start, range_end in result.missing_ranges:
            current = range_start
            while current <= range_end:
                missing_dates.append(current)
                current += timedelta(days=1)

        return missing_dates

    async def get_missing_dates_async(
        self,
        symbol: str,
        interval: Union[Interval, str],
        start_date: Union[date, str, datetime],
        end_date: Union[date, str, datetime],
    ) -> List[date]:
        """获取缺失的日期列表（异步版本）.

        Args:
            symbol: 证券代码
            interval: K 线周期
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            List[date]: 缺失的日期列表
        """
        result = await self.check_async(symbol, interval, start_date, end_date)

        # 展开缺失范围
        missing_dates = []
        for range_start, range_end in result.missing_ranges:
            current = range_start
            while current <= range_end:
                missing_dates.append(current)
                current += timedelta(days=1)

        return missing_dates

    def is_data_complete(
        self,
        symbol: str,
        interval: Union[Interval, str],
        start_date: Union[date, str, datetime],
        end_date: Union[date, str, datetime],
        min_coverage: float = 1.0,
    ) -> bool:
        """快速检查数据是否完整.

        Args:
            symbol: 证券代码
            interval: K 线周期
            start_date: 开始日期
            end_date: 结束日期
            min_coverage: 最小覆盖率要求 (默认 100%)

        Returns:
            bool: 是否满足完整性要求
        """
        result = self.check(symbol, interval, start_date, end_date)
        return result.coverage_ratio >= min_coverage

    def clear_cache(self):
        """清空所有缓存.

        在批量检查完成后调用，释放内存。
        """
        self._long_checker.clear_cache()
        self._short_checker.clear_cache()

    def _normalize_interval(self, interval: Union[Interval, str]) -> Interval:
        """标准化 interval 参数."""
        if isinstance(interval, Interval):
            return interval
        return Interval(interval.lower())

    def _normalize_date(
        self,
        date_value: Union[date, str, datetime],
        interval: Interval = None,
        is_end_date: bool = False,
    ) -> date:
        """标准化日期参数.

        支持不同周期的日期格式：
        - 年线(year): 4位数字 (YYYY)
        - 季线(season)/月线(month): 6位数字 (YYYYMM)
        - 日线(day)/周线(week): 8位数字 (YYYYMMDD)
        """
        if isinstance(date_value, date) and not isinstance(date_value, datetime):
            return date_value
        if isinstance(date_value, datetime):
            return date_value.date()
        if isinstance(date_value, str):
            # 首先尝试直接解析标准格式（带分隔符或完整8位数字）
            for fmt in ["%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"]:
                try:
                    return datetime.strptime(date_value, fmt).date()
                except ValueError:
                    continue

            # 如果直接解析失败，且提供了 interval，则根据周期类型进行扩展
            if interval:
                try:
                    date_str = self._expand_date_by_interval(
                        date_value,
                        interval,
                        is_end_date=is_end_date,
                    )
                    return datetime.strptime(date_str, "%Y%m%d").date()
                except (ValueError, TypeError):
                    pass

            raise ValueError(f"无法解析日期格式: {date_value}")
        raise ValueError(f"不支持的日期类型: {type(date_value)}")

    def _expand_date_by_interval(
        self, date_value: str, interval: Interval, is_end_date: bool = False
    ) -> str:
        """根据周期类型将短日期格式扩展为完整的 YYYYMMDD 格式.

        Args:
            date_value: 日期字符串
            interval: 周期类型
            is_end_date: 是否是结束日期，如果是则补全为周期最后一天，否则补全为第一天

        Returns:
            YYYYMMDD 格式的日期字符串
        """
        import calendar

        # 处理年线特殊情况：即使是完整格式，也需要根据is_end_date调整
        if interval == Interval.YEAR:
            # 年线：4位数字 (YYYY)
            year = int(date_value[:4])
            if is_end_date:
                return f"{year}1231"  # 年末
            else:
                return f"{year}0101"  # 年初

        elif interval in (Interval.SEASON, Interval.MONTH):
            # 月线/季线：6位数字 (YYYYMM)
            # 处理4位年份格式（如 "2013"）→ 根据 is_end_date 补全为年初或年末月份
            if len(date_value) <= 4:
                # 只有年份，没有月份
                year = int(date_value[:4])
                if is_end_date:
                    # 结束日期：补全为年末（12月）的最后一天
                    return f"{year}1231"
                else:
                    # 开始日期：补全为年初（1月）的第一天
                    return f"{year}0101"
            else:
                # 有年月信息（6位或更多）
                date_str = date_value.zfill(6)
                year = int(date_str[:4])
                month = int(date_str[4:6])

                if is_end_date:
                    # 结束日期：补全为该月的最后一天
                    last_day = calendar.monthrange(year, month)[1]
                    return f"{year}{month:02d}{last_day:02d}"
                else:
                    # 开始日期：补全为该月的第一天
                    return f"{year}{month:02d}01"

        elif interval in (Interval.DAY, Interval.WEEK):
            # 日线/周线：8位数字 (YYYYMMDD)
            # 如果长度不足8位，补全为当月第一天或最后一天
            if len(date_value) < 8:
                # 处理4位年份格式（如 "2013"）→ 根据 is_end_date 补全为年初或年末
                if len(date_value) <= 4:
                    year = int(date_value[:4])
                    if is_end_date:
                        # 结束日期：补全为年末
                        return f"{year}1231"
                    else:
                        # 开始日期：补全为年初
                        return f"{year}0101"
                else:
                    # 6位年月格式（YYYYMM）
                    date_str = date_value.zfill(6)
                    year = int(date_str[:4])
                    month = int(date_str[4:6])
                    if is_end_date:
                        # 结束日期：补全为该月最后一天
                        last_day = calendar.monthrange(year, month)[1]
                        return f"{year}{month:02d}{last_day:02d}"
                    else:
                        # 开始日期：补全为该月第一天
                        return f"{year}{month:02d}01"
            return date_value[:8]

        else:
            # 其他周期（分钟、小时）：默认按8位处理
            return date_value.zfill(8)[:8]

    def _is_long_period(self, interval: Interval) -> bool:
        """判断是否为长周期."""
        # 定义周期顺序
        period_order = [
            Interval.MIN1,
            Interval.MIN3,
            Interval.MIN5,
            Interval.MIN10,
            Interval.MIN15,
            Interval.MIN30,
            Interval.MIN60,
            Interval.MIN120,
            Interval.DAY,
            Interval.WEEK,
            Interval.MONTH,
            Interval.SEASON,
            Interval.YEAR,
        ]

        current_idx = period_order.index(interval)
        threshold_idx = period_order.index(self.LONG_PERIOD_THRESHOLD)

        return current_idx >= threshold_idx


# 全局检查器实例
kline_completeness_checker = KlineCompletenessChecker()
