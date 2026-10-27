"""交易日历服务."""

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any

import akshare as ak
import pandas as pd
from sqlalchemy import and_, delete, insert, select

from galaxy_core.database.core.async_connection import AsyncDatabaseManager
from galaxy_core.database.models.trading_calendar import TradingCalendar
from galaxy_core.shared_kernel.utils.constants import CST

logger = logging.getLogger(__name__)


def _to_date(value: object) -> object:
    """ORM trade_date 列(timestamptz)读出是 aware datetime,转 CST 后取 date.

    与 calendar_store_adapter.py:117-121, 157-161 同模式(2026-07-17 timestamptz
    改造后必要的归一)。naive/已是 date 的值透传。
    """
    if hasattr(value, "astimezone"):
        return value.astimezone(CST).date()
    return value


def _date_to_cst_dt(d: date) -> date:
    """date 透传(nocodb 形态 trade_date=date 列,2026-08-26 回迁后)。

    历史:timestamptz 时代须转北京 00:00 的 aware instant(2026-07-29 修复的
    instant 错位问题);date 列后直接传 date。保留函数名以减少调用点改动。
    """
    if isinstance(d, datetime):
        return d.astimezone(CST).date() if d.tzinfo is not None else d.date()
    return d


class TradingCalendarService:
    """交易日历服务.

    职责(2026-07-29 合并双写路径后):
    - akshare 拉取交易日历(业务逻辑,非 DB 操作)
    - DB 读写**委托给 calendar_store**(CalendarStoreAdapter),消除与
      calendar_store_adapter 的双写路径(instant 错位 bug 的根因之一)。
    - 保留 db_manager 参数用于向后兼容(is_trading_day_async 的 akshare fallback
      仍需直接写 DB,未来可进一步收敛到 store)。
    """

    def __init__(
        self,
        db_manager: AsyncDatabaseManager,
        calendar_store: Any = None,
    ) -> None:
        """初始化交易日历服务.

        Args:
            db_manager: 异步数据库管理器实例(向后兼容 + akshare fallback 写入)
            calendar_store: CalendarStorePort(DB 读写委托目标,消除双写路径)。
                None 时退化为直接操作 DB(向后兼容旧调用方)。
        """
        self._db = db_manager
        self._store = calendar_store

    async def get_previous_trading_day_async(self, target_date: date) -> date:
        """异步获取指定日期的上一个交易日。

        Uses async trading calendar methods.
        """
        start_date = target_date - timedelta(days=30)
        trading_days = await self.get_trading_days_async(start_date, target_date)
        if not trading_days:
            raise ValueError(f"无法获取交易日历用于回溯交易日: target_date={target_date}")

        for d in reversed(trading_days):
            if d < target_date:
                return d

        raise ValueError(f"在范围内未找到上一个交易日: target_date={target_date}")

    async def get_trading_days_async(self, start_date: date, end_date: date) -> list[date]:
        """异步获取指定日期范围内的交易日列表（仅从数据库获取）.

        2026-07-29 合并双写路径:委托给 calendar_store(若注入),消除与
        calendar_store_adapter.get_trading_days 的重复实现。store 已正确处理
        timestamptz 的 localize_cst 转换(2026-07-29 calendar instant 错位 bug 修复)。
        """
        if self._store is not None:
            return await self._store.get_trading_days(start_date, end_date)
        # 向后兼容:无 store 时直接查 DB(已修 localize_cst)
        async with self._db.session() as session:
            stmt = (
                select(TradingCalendar.trade_date)
                .where(
                    and_(
                        TradingCalendar.trade_date >= _date_to_cst_dt(start_date),
                        TradingCalendar.trade_date <= _date_to_cst_dt(end_date),
                        TradingCalendar.is_trading_day == True,
                    )
                )
                .order_by(TradingCalendar.trade_date)
            )
            result = await session.execute(stmt)
            rows = result.all()
            return [_to_date(row[0]) for row in rows]

    async def is_trading_day_async(self, check_date: date) -> bool:
        """异步判断指定日期是否为交易日."""
        async with self._db.session() as session:
            stmt = select(TradingCalendar).where(
                TradingCalendar.trade_date == _date_to_cst_dt(check_date)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            if row:
                return row.is_trading_day

            logger.debug(f"数据库中无 {check_date} 的交易日信息，从 akshare 获取")
            trading_days = await asyncio.to_thread(
                self._fetch_from_akshare, check_date, check_date
            )

            await self._save_to_db_async(trading_days, check_date, check_date)

            stmt = select(TradingCalendar).where(
                TradingCalendar.trade_date == _date_to_cst_dt(check_date)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            return row.is_trading_day if row else False

    async def sync_calendar_async(self, year: int) -> int:
        """异步同步指定年份的交易日历."""
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

        logger.debug(f"开始同步 {year} 年交易日历...")

        trading_days = await asyncio.to_thread(
            self._fetch_from_akshare, start_date, end_date
        )

        await self._save_to_db_async(trading_days, start_date, end_date)

        logger.info(
            f"成功同步 {year} 年交易日历，共 {len(trading_days)} 个交易日"
        )
        return len(trading_days)

    async def sync_current_year_async(self) -> int:
        """异步同步当前年份的交易日历."""
        current_year = datetime.now().year
        return await self.sync_calendar_async(current_year)

    async def check_and_update_yearly_async(self) -> bool:
        """异步年更检查（12月31日自动更新下一年）."""
        today = date.today()
        if today.month == 12 and today.day == 31:
            next_year = today.year + 1
            logger.debug(f"年更检查：开始同步 {next_year} 年交易日历")
            try:
                await self.sync_calendar_async(next_year)
                return True
            except Exception as e:
                logger.error(f"年更同步失败: {e}")
                return False
        return False

    async def sync_years(self, start_year: int, end_year: int) -> dict[str, int]:
        """异步同步多个年份的交易日历.

        Args:
            start_year: 开始年份
            end_year: 结束年份

        Returns:
            包含统计信息的字典: total, added, updated, skipped
        """
        logger.debug(f"开始同步 {start_year} 至 {end_year} 年的交易日历...")

        stats = {
            "total": 0,
            "added": 0,
            "updated": 0,
            "skipped": 0,
        }

        for year in range(start_year, end_year + 1):
            try:
                count = await self.sync_calendar_async(year)

                stats["total"] += count
                stats["added"] += count

                logger.debug(f"成功同步 {year} 年交易日历，共 {count} 个交易日")

            except Exception as e:
                logger.error(f"同步 {year} 年交易日历时出错: {e}")
                stats["skipped"] += 1

        logger.info(
            f"交易日历同步完成: 总计 {stats['total']} 条，"
            f"新增 {stats['added']} 条，跳过 {stats['skipped']} 年"
        )

        return stats

    def _fetch_from_akshare(self, start_date: date, end_date: date) -> list[date]:
        """从 akshare 获取交易日历.

        注意:akshare `tool_trade_date_hist_sina` 返回的是交易所**已发布**的交易日历,
        含未来预定交易日(实测能到当年 12-31,如 2026 全年 242 个)。
        不要截断到 today —— scheduler 在每年 12/20-12/31 同步下一年日历时,
        start_date 会是下一年的 1/1(> today),截断会让 CalendarSyncJob 拿到 0 天,
        触发 MIN_TRADING_DAYS_PER_YEAR=200 阈值报错重试 → 下一年日历永远同步不上。
        详见 AGENTS.md 2026-07-04 + 2026-06-25。
        """
        logger.debug(f"从 akshare 获取 {start_date} 到 {end_date} 的交易日历")

        try:
            df = ak.tool_trade_date_hist_sina()

            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

            start_date_check = (
                start_date if isinstance(start_date, date) else start_date.date()
            )
            end_date_check = (
                end_date if isinstance(end_date, date) else end_date.date()
            )

            filtered_df = df[
                (df["trade_date"] >= start_date_check)
                & (df["trade_date"] <= end_date_check)
            ]

            trading_days = filtered_df["trade_date"].tolist()

            logger.debug(f"从 akshare 获取到 {len(trading_days)} 个交易日")
            return trading_days
        except Exception as e:
            logger.error(f"从 akshare 获取交易日历时出错: {e}")
            return []

    def _generate_full_calendar(
        self, start_date: date, end_date: date, trading_days: list[date]
    ) -> list[tuple[date, bool]]:
        """生成完整日历，包括交易日和非交易日."""
        logger.debug(f"生成 {start_date} 到 {end_date} 的完整日历")

        trading_day_set = set(trading_days)

        current_date = start_date
        full_calendar = []

        while current_date <= end_date:
            is_trading_day = current_date in trading_day_set
            full_calendar.append((current_date, is_trading_day))
            current_date += timedelta(days=1)

        logger.debug(
            f"生成了 {len(full_calendar)} 条日历记录，其中交易日 {len(trading_day_set)} 个"
        )
        return full_calendar

    def _merge_dates_to_ranges(
        self,
        dates: list[date],
    ) -> list[tuple[date, date]]:
        """将日期列表合并为连续区间."""
        if not dates:
            return []

        ranges: list[tuple[date, date]] = []
        range_start = dates[0]
        range_end = dates[0]

        for current in dates[1:]:
            if current > range_end + timedelta(days=1):
                ranges.append((range_start, range_end))
                range_start = current
            range_end = current

        ranges.append((range_start, range_end))
        return ranges

    async def _save_to_db_async(
        self,
        trading_days: list[date],
        start_date: date | None = None,
        end_date: date | None = None,
    ):
        """异步将交易日历数据保存到数据库.

        2026-07-29 合并双写路径:委托给 calendar_store.save_calendar(若注入)。
        store 内部用 localize_cst 处理 timestamptz(已修 instant 错位 bug),
        并自己生成完整日历(含非交易日)。start_date/end_date 参数在 store 路径
        下忽略(store 用 min/max(trading_days) 推导范围,含非交易日)。
        """
        if not trading_days:
            return

        if self._store is not None:
            # 委托 store(单写路径,正确 localize_cst)
            await self._store.save_calendar(trading_days)
            logger.info(
                f"成功保存交易日历到数据库(委托 store,交易日: {len(trading_days)} 个)"
            )
            return

        # 向后兼容:无 store 时直接写 DB(已修 localize_cst)
        calendar_start = start_date if start_date else min(trading_days)
        calendar_end = end_date if end_date else max(trading_days)
        full_calendar = self._generate_full_calendar(
            calendar_start, calendar_end, trading_days
        )

        async with self._db.session() as session:
            await session.execute(
                delete(TradingCalendar).where(
                    and_(
                        TradingCalendar.trade_date >= _date_to_cst_dt(calendar_start),
                        TradingCalendar.trade_date <= _date_to_cst_dt(calendar_end),
                    )
                )
            )

            records = [
                {
                    "trade_date": _date_to_cst_dt(trade_date),
                    "is_trading_day": is_trading_day,
                }
                for trade_date, is_trading_day in full_calendar
            ]
            await session.execute(insert(TradingCalendar), records)

        logger.info(
            f"成功保存 {len(full_calendar)} 条交易日历记录到数据库（交易日: {len(trading_days)} 个）"
        )
