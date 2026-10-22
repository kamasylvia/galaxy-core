"""交易日历存储适配器 — 直接操作 SQLAlchemy model 为 CalendarStorePort."""

import logging
from datetime import date, timedelta

from sqlalchemy import and_, delete, insert, select
from sqlalchemy.exc import SQLAlchemyError

from galaxy_core.database.core.async_connection import AsyncDatabaseManager
from galaxy_core.database.models.trading_calendar import TradingCalendar
from galaxy_core.shared_kernel.exceptions import CacheError
from galaxy_core.shared_kernel.utils.constants import CST

logger = logging.getLogger(__name__)


class CalendarStoreAdapter:
    """CalendarStorePort 实现 — 直接操作 SQLAlchemy model.

    不通过现有 TradingCalendarService 类中转，直接操作数据库。
    """

    def __init__(self, db_manager: AsyncDatabaseManager) -> None:
        self._db = db_manager

    async def save_calendar(self, dates: list[date]) -> None:
        """保存交易日历数据.

        生成完整日历（包括非交易日），删除范围内已有记录后批量插入。

        Args:
            dates: 交易日列表
        """
        if not dates:
            return

        calendar_start = min(dates)
        calendar_end = max(dates)
        trading_day_set = set(dates)

        # 生成完整日历（包括非交易日）
        # trade_date 列是 date(nocodb 形态),直接用 date 对象
        full_calendar: list[dict] = []
        current = calendar_start
        while current <= calendar_end:
            full_calendar.append(
                {
                    "trade_date": current,
                    "is_trading_day": current in trading_day_set,
                }
            )
            current += timedelta(days=1)

        try:
            async with self._db.session() as session:
                # 删除范围内已有记录(date 比较)
                await session.execute(
                    delete(TradingCalendar).where(
                        and_(
                            TradingCalendar.trade_date >= calendar_start,
                            TradingCalendar.trade_date <= calendar_end,
                        )
                    )
                )

                # 批量插入新记录
                await session.execute(insert(TradingCalendar), full_calendar)
        except SQLAlchemyError as e:
            raise CacheError(
                message=f"保存交易日历失败: {e}",
                operation="save_calendar",
                key=f"{calendar_start}~{calendar_end}",
            ) from e

        logger.debug(
            f"保存 {len(full_calendar)} 条日历记录，交易日 {len(dates)} 个，"
            f"范围 {calendar_start} ~ {calendar_end}"
        )

    async def get_trading_calendar(self, year: int) -> list[date]:
        """获取指定年份的交易日列表.

        Args:
            year: 年份

        Returns:
            该年份的交易日列表
        """
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

        try:
            async with self._db.session() as session:
                stmt = (
                    select(TradingCalendar.trade_date)
                    .where(
                        and_(
                            TradingCalendar.trade_date >= start_date,
                            TradingCalendar.trade_date <= end_date,
                            TradingCalendar.is_trading_day == True,  # noqa: E712
                        )
                    )
                    .order_by(TradingCalendar.trade_date)
                )
                result = await session.execute(stmt)
                rows = result.all()
        except SQLAlchemyError as e:
            raise CacheError(
                message=f"查询交易日历失败: {e}",
                operation="get_trading_calendar",
                key=str(year),
            ) from e

        # 读出 aware datetime → date(转 CST 后取日期,避免 UTC 日界线偏移)
        trading_dates = [
            r[0].astimezone(CST).date() if hasattr(r[0], "astimezone") else r[0] for r in rows
        ]
        logger.debug(f"查询到 {year} 年 {len(trading_dates)} 个交易日")
        return trading_dates

    async def get_trading_days(self, start_date: date, end_date: date) -> list[date]:
        """获取指定日期范围内的交易日列表.

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            该范围内 is_trading_day=True 的日期列表（升序）
        """
        try:
            async with self._db.session() as session:
                stmt = (
                    select(TradingCalendar.trade_date)
                    .where(
                        and_(
                            TradingCalendar.trade_date >= start_date,
                            TradingCalendar.trade_date <= end_date,
                            TradingCalendar.is_trading_day == True,  # noqa: E712
                        )
                    )
                    .order_by(TradingCalendar.trade_date)
                )
                result = await session.execute(stmt)
                rows = result.all()
        except SQLAlchemyError as e:
            raise CacheError(
                message=f"查询交易日失败: {e}",
                operation="get_trading_days",
                key=f"{start_date}~{end_date}",
            ) from e

        # 读出 aware datetime → date(转 CST 后取日期)
        trading_dates = [
            r[0].astimezone(CST).date() if hasattr(r[0], "astimezone") else r[0] for r in rows
        ]
        logger.debug(f"查询到 {start_date} ~ {end_date} 范围内 {len(trading_dates)} 个交易日")
        return trading_dates
