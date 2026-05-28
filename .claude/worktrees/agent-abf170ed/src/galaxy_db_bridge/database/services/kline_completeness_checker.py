"""K 线数据完整性检查器.

提供分层数据完整性检测策略，支持长周期和短周期不同的检测方法。
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum, auto
from typing import List, Optional, Set, Tuple, Union

from galaxy_db_bridge.database.services.kline import kline_service
from galaxy_db_bridge.database.services.trading_calendar import trading_calendar_service
from galaxy_db_bridge.shared_kernel.enums.interval import Interval

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
        market: str = "SSE",
    ) -> CompletenessResult:
        """检查数据完整性.

        Args:
            symbol: 证券代码
            interval: K 线周期
            start_date: 开始日期
            end_date: 结束日期
            market: 市场代码

        Returns:
            CompletenessResult: 完整性检查结果
        """
        pass

    def _get_market_from_symbol(self, symbol: str) -> str:
        """根据证券代码推断市场."""
        if symbol.endswith(".SH"):
            return "SSE"
        elif symbol.endswith(".SZ"):
            return "SZSE"
        elif symbol.endswith(".BJ"):
            return "BSE"
        return "SSE"


class LongPeriodChecker(BaseCompletenessChecker):
    """长周期数据完整性检查器 (月线及以上).

    长周期数据使用连续性检测，因为长周期数据点数量较少，
    且每个数据点都代表一个完整的周期，可以通过连续性来判断完整性。
    """

    def check(
        self,
        symbol: str,
        interval: Interval,
        start_date: date,
        end_date: date,
        market: str = "SSE",
    ) -> CompletenessResult:
        """检查长周期数据完整性."""
        logger.debug(f"{symbol}: 使用长周期连续性检测 ({interval.value})")

        # 1. 查询数据库中的数据
        db_data = kline_service.query_kline_from_db(
            symbols=[symbol],
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            interval=interval.value,
        )

        existing_dates: Set[date] = set()
        if symbol in db_data and not db_data[symbol].empty:
            # 提取日期部分
            existing_dates = set(
                d.date() if isinstance(d, datetime) else d
                for d in db_data[symbol].index
            )

        # 2. 根据周期生成期望的日期序列
        expected_dates = self._generate_expected_dates(
            interval, start_date, end_date, market
        )

        # 3. 计算缺失的日期
        missing_dates = expected_dates - existing_dates

        # 4. 合并连续的缺失日期为范围
        missing_ranges = self._merge_to_ranges(sorted(missing_dates))

        # 5. 构建结果
        total_count = len(expected_dates)
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

    def _generate_expected_dates(
        self,
        interval: Interval,
        start_date: date,
        end_date: date,
        market: str = "SSE",
    ) -> Set[date]:
        """生成长周期期望的日期序列."""
        dates = set()
        current = start_date

        if interval == Interval.MONTH:
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
                trading_days = trading_calendar_service.get_trading_days(
                    period_start,
                    period_end,
                    market=market,
                )
                if trading_days:
                    dates.add(trading_days[-1])
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
                trading_days = trading_calendar_service.get_trading_days(
                    period_start,
                    period_end,
                    market=market,
                )
                if trading_days:
                    dates.add(trading_days[-1])
                current = next_period_start

        elif interval == Interval.YEAR:
            while current <= end_date:
                period_start = date(current.year, 1, 1)
                next_period_start = date(current.year + 1, 1, 1)
                period_end = min(next_period_start - timedelta(days=1), end_date)
                trading_days = trading_calendar_service.get_trading_days(
                    period_start,
                    period_end,
                    market=market,
                )
                if trading_days:
                    dates.add(trading_days[-1])
                current = next_period_start

        return dates

    def _merge_to_ranges(self, dates: List[date]) -> List[Tuple[date, date]]:
        """将连续的日期合并为范围."""
        if not dates:
            return []

        ranges = []
        range_start = dates[0]
        range_end = dates[0]

        for i in range(1, len(dates)):
            # 检查是否连续（考虑长周期可能间隔一个月或更久）
            if dates[i] > range_end + timedelta(days=32):  # 超过一个月视为不连续
                ranges.append((range_start, range_end))
                range_start = dates[i]
            range_end = dates[i]

        ranges.append((range_start, range_end))
        return ranges


class ShortPeriodChecker(BaseCompletenessChecker):
    """短周期数据完整性检查器 (周线及以下).

    短周期数据使用交易日对比检测，因为短周期数据点数量多，
    且只存在于交易日，需要通过交易日历来判断哪些日期应该有数据。
    """

    def check(
        self,
        symbol: str,
        interval: Interval,
        start_date: date,
        end_date: date,
        market: str = "SSE",
    ) -> CompletenessResult:
        """检查短周期数据完整性."""
        logger.debug(f"{symbol}: 使用短周期交易日对比检测 ({interval.value})")

        # 1. 获取交易日历
        trading_days = trading_calendar_service.get_trading_days(
            start_date, end_date, market=market
        )

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

        # 2. 查询数据库中的数据
        db_data = kline_service.query_kline_from_db(
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
            check_method="short_period_trading_day",
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
    - 月线及以上：使用连续性检测
    - 周线及以下：使用交易日对比检测
    """

    # 定义长周期阈值
    LONG_PERIOD_THRESHOLD = Interval.MONTH

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
        market: Optional[str] = None,
    ) -> CompletenessResult:
        """检查 K 线数据完整性.

        Args:
            symbol: 证券代码
            interval: K 线周期 (Interval 枚举或字符串)
            start_date: 开始日期
            end_date: 结束日期
            market: 市场代码 (可选，自动从代码推断)

        Returns:
            CompletenessResult: 完整性检查结果
        """
        # 标准化参数
        interval_enum = self._normalize_interval(interval)
        start_date_obj = self._normalize_date(start_date)
        end_date_obj = self._normalize_date(end_date)

        if market is None:
            market = self._long_checker._get_market_from_symbol(symbol)

        logger.info(
            f"{symbol}: 开始数据完整性检查 "
            f"({interval_enum.value}, {start_date_obj} ~ {end_date_obj})"
        )

        # 根据周期选择合适的检查器
        if self._is_long_period(interval_enum):
            result = self._long_checker.check(
                symbol, interval_enum, start_date_obj, end_date_obj, market
            )
        else:
            result = self._short_checker.check(
                symbol, interval_enum, start_date_obj, end_date_obj, market
            )

        logger.info(f"{symbol}: 完整性检查完成 - {result}")
        return result

    def get_missing_dates(
        self,
        symbol: str,
        interval: Union[Interval, str],
        start_date: Union[date, str, datetime],
        end_date: Union[date, str, datetime],
        market: Optional[str] = None,
    ) -> List[date]:
        """获取缺失的日期列表.

        Args:
            symbol: 证券代码
            interval: K 线周期
            start_date: 开始日期
            end_date: 结束日期
            market: 市场代码

        Returns:
            List[date]: 缺失的日期列表
        """
        result = self.check(symbol, interval, start_date, end_date, market)

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
        market: Optional[str] = None,
        min_coverage: float = 1.0,
    ) -> bool:
        """快速检查数据是否完整.

        Args:
            symbol: 证券代码
            interval: K 线周期
            start_date: 开始日期
            end_date: 结束日期
            market: 市场代码
            min_coverage: 最小覆盖率要求 (默认 100%)

        Returns:
            bool: 是否满足完整性要求
        """
        result = self.check(symbol, interval, start_date, end_date, market)
        return result.coverage_ratio >= min_coverage

    def _normalize_interval(self, interval: Union[Interval, str]) -> Interval:
        """标准化 interval 参数."""
        if isinstance(interval, Interval):
            return interval
        return Interval(interval.lower())

    def _normalize_date(self, date_value: Union[date, str, datetime]) -> date:
        """标准化日期参数."""
        if isinstance(date_value, date) and not isinstance(date_value, datetime):
            return date_value
        if isinstance(date_value, datetime):
            return date_value.date()
        if isinstance(date_value, str):
            # 尝试多种格式
            for fmt in ["%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"]:
                try:
                    return datetime.strptime(date_value, fmt).date()
                except ValueError:
                    continue
            raise ValueError(f"无法解析日期格式: {date_value}")
        raise ValueError(f"不支持的日期类型: {type(date_value)}")

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
