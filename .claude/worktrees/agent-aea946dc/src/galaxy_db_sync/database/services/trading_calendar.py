"""交易日历服务."""

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import akshare as ak
import pandas as pd

from sqlalchemy import and_, select
from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.core.async_connection import async_db_manager
from galaxy_db_sync.database.models.trading_calendar import TradingCalendar

logger = logging.getLogger(__name__)


class TradingCalendarService:
    """交易日历服务."""

    def get_previous_trading_day(self, target_date: date) -> date:
        """获取指定日期的上一个交易日。

        该方法主要为 IntervalBoundaryChecker 提供依赖接口。
        """
        start_date = target_date - timedelta(days=30)
        trading_days = self.get_trading_days(start_date, target_date)
        if not trading_days:
            raise ValueError(f"无法获取交易日历用于回溯交易日: target_date={target_date}")

        # get_trading_days 返回的是范围内的交易日（升序）
        # 取严格小于 target_date 的最后一个交易日
        for d in reversed(trading_days):
            if d < target_date:
                return d

        raise ValueError(f"在范围内未找到上一个交易日: target_date={target_date}")

    async def get_previous_trading_day_async(self, target_date: date) -> date:
        """异步获取指定日期的上一个交易日。

        Uses async trading calendar methods.
        """
        start_date = target_date - timedelta(days=30)
        trading_days = await self.get_trading_days_async(start_date, target_date)
        if not trading_days:
            raise ValueError(f"无法获取交易日历用于回溯交易日: target_date={target_date}")

        # get_trading_days_async 返回的是范围内的交易日（升序）
        # 取严格小于 target_date 的最后一个交易日
        for d in reversed(trading_days):
            if d < target_date:
                return d

        raise ValueError(f"在范围内未找到上一个交易日: target_date={target_date}")

    def get_trading_days(self, start_date: date, end_date: date) -> List[date]:
        """获取指定日期范围内的交易日列表."""
        session = db_manager.get_session()
        try:
            # 计算请求范围内的预期日期总数
            expected_days = (end_date - start_date).days + 1

            # 查询数据库中请求范围内的所有日期记录
            calendar_query = (
                session.query(TradingCalendar)
                .filter(
                    and_(
                        TradingCalendar.trade_date >= start_date,
                        TradingCalendar.trade_date <= end_date,
                    )
                )
                .order_by(TradingCalendar.trade_date)
            )

            calendar_results = calendar_query.all()
            all_cached_dates = [row.trade_date for row in calendar_results]

            # 检查缓存是否完全覆盖请求范围：通过日期计数而非边界比较
            # 这样可以正确处理重叠范围的情况
            cache_fully_covers_range = len(all_cached_dates) == expected_days

            if not cache_fully_covers_range:
                # 计算缺失的日期范围
                cached_set = set(all_cached_dates)
                missing_dates = []
                current = start_date
                while current <= end_date:
                    if current not in cached_set:
                        missing_dates.append(current)
                    current += timedelta(days=1)

                if missing_dates:
                    # 找出缺失的连续区间
                    missing_ranges = self._merge_dates_to_ranges(missing_dates)

                    for range_start, range_end in missing_ranges:
                        logger.info(
                            f"交易日历缓存部分缺失，从 akshare 补充 {range_start} 到 {range_end}"
                        )
                        additional_dates = self._fetch_from_akshare(range_start, range_end)
                        self._save_to_db(additional_dates, range_start, range_end)

                    # 重新查询数据库
                    query = (
                        session.query(TradingCalendar.trade_date)
                        .filter(
                            and_(
                                TradingCalendar.trade_date >= start_date,
                                TradingCalendar.trade_date <= end_date,
                                TradingCalendar.is_trading_day == True,
                            )
                        )
                        .order_by(TradingCalendar.trade_date)
                    )

                    results = query.all()
                    cached_dates = [row.trade_date for row in results]
                else:
                    # 没有缺失日期，提取交易日
                    cached_dates = [
                        row.trade_date for row in calendar_results if row.is_trading_day
                    ]
            else:
                # 缓存完全覆盖，直接提取交易日
                cached_dates = [
                    row.trade_date for row in calendar_results if row.is_trading_day
                ]

            return sorted(cached_dates)
        finally:
            session.close()

    async def get_trading_days_async(self, start_date: date, end_date: date) -> List[date]:
        """异步获取指定日期范围内的交易日列表.

        Uses async_db_manager for async database operations.
        """
        async with async_db_manager.session() as session:
            # 计算请求范围内的预期日期总数
            expected_days = (end_date - start_date).days + 1

            # 查询数据库中请求范围内的所有日期记录
            stmt = (
                select(TradingCalendar)
                .where(
                    and_(
                        TradingCalendar.trade_date >= start_date,
                        TradingCalendar.trade_date <= end_date,
                    )
                )
                .order_by(TradingCalendar.trade_date)
            )
            result = await session.execute(stmt)
            calendar_results = result.scalars().all()
            all_cached_dates = [row.trade_date for row in calendar_results]

            # 检查缓存是否完全覆盖请求范围：通过日期计数而非边界比较
            cache_fully_covers_range = len(all_cached_dates) == expected_days

            if not cache_fully_covers_range:
                # 计算缺失的日期
                cached_set = set(all_cached_dates)
                missing_dates = []
                current = start_date
                while current <= end_date:
                    if current not in cached_set:
                        missing_dates.append(current)
                    current += timedelta(days=1)

                if missing_dates:
                    # 找出缺失的连续区间
                    missing_ranges = self._merge_dates_to_ranges(missing_dates)

                    for range_start, range_end in missing_ranges:
                        logger.info(
                            f"交易日历缓存部分缺失，从 akshare 补充 {range_start} 到 {range_end}"
                        )
                        additional_dates = await asyncio.to_thread(
                            self._fetch_from_akshare, range_start, range_end
                        )
                        await asyncio.to_thread(
                            self._save_to_db, additional_dates, range_start, range_end
                        )

                    # 重新查询数据库
                    stmt = (
                        select(TradingCalendar.trade_date)
                        .where(
                            and_(
                                TradingCalendar.trade_date >= start_date,
                                TradingCalendar.trade_date <= end_date,
                                TradingCalendar.is_trading_day == True,
                            )
                        )
                        .order_by(TradingCalendar.trade_date)
                    )
                    result = await session.execute(stmt)
                    rows = result.all()
                    cached_dates = [row.trade_date for row in rows]
                else:
                    cached_dates = [
                        row.trade_date for row in calendar_results if row.is_trading_day
                    ]
            else:
                cached_dates = [
                    row.trade_date for row in calendar_results if row.is_trading_day
                ]

            return sorted(cached_dates)

    async def is_trading_day_async(self, check_date: date) -> bool:
        """异步判断指定日期是否为交易日.

        Uses async_db_manager for async database operations.
        """
        async with async_db_manager.session() as session:
            # 先查询数据库
            stmt = select(TradingCalendar).where(
                TradingCalendar.trade_date == check_date
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            if row:
                return row.is_trading_day

            # 如果数据库中没有，从 akshare 获取
            logger.info(f"数据库中无 {check_date} 的交易日信息，从 akshare 获取")
            trading_days = await asyncio.to_thread(
                self._fetch_from_akshare, check_date, check_date
            )

            # 将数据存入数据库
            await asyncio.to_thread(
                self._save_to_db, trading_days, check_date, check_date
            )

            # 再次查询
            stmt = select(TradingCalendar).where(
                TradingCalendar.trade_date == check_date
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            return row.is_trading_day if row else False

    def is_trading_day(self, check_date: date) -> bool:
        """判断指定日期是否为交易日."""
        session = db_manager.get_session()
        try:
            # 先查询数据库
            result = (
                session.query(TradingCalendar)
                .filter(TradingCalendar.trade_date == check_date)
                .first()
            )

            if result:
                return result.is_trading_day

            # 如果数据库中没有，从 akshare 获取
            logger.info(f"数据库中无 {check_date} 的交易日信息，从 akshare 获取")
            trading_days = self._fetch_from_akshare(check_date, check_date)

            # 将数据存入数据库，传入请求的日期
            self._save_to_db(trading_days, check_date, check_date)

            # 再次查询
            result = (
                session.query(TradingCalendar)
                .filter(TradingCalendar.trade_date == check_date)
                .first()
            )

            return result.is_trading_day if result else False
        finally:
            session.close()

    def filter_trading_days(self, dates: List[date]) -> List[date]:
        """过滤出指定日期列表中的交易日."""
        if not dates:
            return []

        session = db_manager.get_session()
        try:
            # 找出数据库中已有的交易日
            existing_query = session.query(TradingCalendar).filter(
                and_(
                    TradingCalendar.trade_date.in_(dates),
                    TradingCalendar.is_trading_day == True,
                )
            )
            existing_results = existing_query.all()

            existing_trading_days = {result.trade_date for result in existing_results}
            remaining_dates = [d for d in dates if d not in existing_trading_days]

            # 如果还有未缓存的日期，从 akshare 获取
            if remaining_dates:
                logger.info(
                    f"数据库中缺少 {len(remaining_dates)} 个日期的交易日信息，从 akshare 获取"
                )
                min_date = min(remaining_dates)
                max_date = max(remaining_dates)

                all_trading_days = self._fetch_from_akshare(min_date, max_date)

                # 将新获取的数据存入数据库，传入请求的日期范围
                self._save_to_db(all_trading_days, min_date, max_date)

                # 重新查询数据库中对应的交易日
                filtered_query = session.query(TradingCalendar).filter(
                    and_(
                        TradingCalendar.trade_date.in_(dates),
                        TradingCalendar.is_trading_day == True,
                    )
                )
                filtered_results = filtered_query.all()

                return sorted([result.trade_date for result in filtered_results])
            else:
                # 所有日期都在数据库中
                return sorted(list(existing_trading_days))
        finally:
            session.close()

    def sync_calendar(self, year: int) -> int:
        """手动同步指定年份的交易日历."""
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

        logger.info(f"开始同步 {year} 年交易日历...")

        trading_days = self._fetch_from_akshare(start_date, end_date)

        # 直接调用 _save_to_db，它会处理删除和保存
        # 不再使用两个 session 以避免锁冲突
        self._save_to_db(trading_days, start_date, end_date)

        logger.info(
            f"成功同步 {year} 年交易日历，共 {len(trading_days)} 个交易日"
        )
        return len(trading_days)

    def sync_current_year(self) -> int:
        """同步当前年份的交易日历."""
        current_year = datetime.now().year
        return self.sync_calendar(current_year)

    async def sync_years(self, start_year: int, end_year: int) -> Dict[str, int]:
        """异步同步多个年份的交易日历.

        Args:
            start_year: 开始年份
            end_year: 结束年份

        Returns:
            包含统计信息的字典: total, added, updated, skipped
        """
        logger.info(f"开始同步 {start_year} 至 {end_year} 年的交易日历...")

        stats = {
            "total": 0,
            "added": 0,
            "updated": 0,
            "skipped": 0,
        }

        for year in range(start_year, end_year + 1):
            try:
                # 使用 asyncio.to_thread 在后台线程中运行同步方法
                count = await asyncio.to_thread(self.sync_calendar, year)

                # 更新统计信息
                stats["total"] += count
                stats["added"] += count

                logger.info(f"成功同步 {year} 年交易日历，共 {count} 个交易日")

            except Exception as e:
                logger.error(f"同步 {year} 年交易日历时出错: {e}")
                stats["skipped"] += 1

        logger.info(
            f"交易日历同步完成: 总计 {stats['total']} 条，"
            f"新增 {stats['added']} 条，跳过 {stats['skipped']} 年"
        )

        return stats

    def check_and_update_yearly(self) -> bool:
        """年更检查（12月31日自动更新下一年）."""
        today = date.today()
        if today.month == 12 and today.day == 31:
            next_year = today.year + 1
            logger.info(f"年更检查：开始同步 {next_year} 年交易日历")
            try:
                self.sync_calendar(next_year)
                return True
            except Exception as e:
                logger.error(f"年更同步失败: {e}")
                return False
        return False

    def _fetch_from_akshare(self, start_date: date, end_date: date) -> List[date]:
        """从 akshare 获取交易日历."""
        logger.info(f"从 akshare 获取 {start_date} 到 {end_date} 的交易日历")

        try:
            # 使用 akshare 获取交易日历
            # 注意：akshare的tool_trade_date_hist_sina返回的是全市场的交易日历
            df = ak.tool_trade_date_hist_sina()

            # 转换日期格式
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

            # 确保比较的日期类型一致
            start_date_check = (
                start_date if isinstance(start_date, date) else start_date.date()
            )
            end_date_check = end_date if isinstance(end_date, date) else end_date.date()

            # 筛选指定日期范围
            filtered_df = df[
                (df["trade_date"] >= start_date_check)
                & (df["trade_date"] <= end_date_check)
            ]

            trading_days = filtered_df["trade_date"].tolist()

            logger.info(f"从 akshare 获取到 {len(trading_days)} 个交易日")
            return trading_days
        except Exception as e:
            logger.error(f"从 akshare 获取交易日历时出错: {e}")
            # 如果 akshare 获取失败，返回空列表
            return []

    def _generate_full_calendar(
        self, start_date: date, end_date: date, trading_days: List[date]
    ) -> List[tuple[date, bool]]:
        """生成完整日历，包括交易日和非交易日."""
        logger.info(f"生成 {start_date} 到 {end_date} 的完整日历")

        # 将交易日列表转换为集合，便于快速查找
        trading_day_set = set(trading_days)

        # 生成指定范围内的所有日期
        current_date = start_date
        full_calendar = []

        while current_date <= end_date:
            is_trading_day = current_date in trading_day_set
            full_calendar.append((current_date, is_trading_day))
            current_date += timedelta(days=1)

        logger.info(
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

    def _save_to_db(
        self,
        trading_days: List[date],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ):
        """将交易日历数据保存到数据库.

        Args:
            trading_days: 交易日列表
            start_date: 请求的开始日期，如果提供则使用此日期作为完整日历的起始
            end_date: 请求的结束日期，如果提供则使用此日期作为完整日历的结束
        """
        if not trading_days:
            return

        # 从 akshare 获取的 trading_days 只是交易日，我们需要生成完整的日历
        if not trading_days:
            logger.info("没有交易日数据需要保存")
            return

        # 确定完整日历的日期范围
        # 使用用户请求的日期范围（如果提供），否则使用交易日的边界
        calendar_start = start_date if start_date else min(trading_days)
        calendar_end = end_date if end_date else max(trading_days)

        # 生成完整的日历（包括非交易日）
        full_calendar = self._generate_full_calendar(
            calendar_start, calendar_end, trading_days
        )

        session = db_manager.get_session()
        try:
            # 只删除要插入的日期范围内的数据，而不是整个年份
            # 这样在补充缺失范围时不会删除已有数据
            session.query(TradingCalendar).filter(
                and_(
                    TradingCalendar.trade_date >= calendar_start,
                    TradingCalendar.trade_date <= calendar_end,
                )
            ).delete(synchronize_session=False)

            # 创建新记录
            records = []
            for trade_date, is_trading_day in full_calendar:
                record = TradingCalendar(
                    trade_date=trade_date,
                    is_trading_day=is_trading_day,
                    year=trade_date.year,
                )
                records.append(record)

            # 批量插入
            session.bulk_save_objects(records)
            session.commit()

            logger.info(
                f"成功保存 {len(full_calendar)} 条交易日历记录到数据库（交易日: {len(trading_days)} 个）"
            )
        except Exception as e:
            session.rollback()
            logger.error(f"保存交易日历到数据库时出错: {e}")
            raise
        finally:
            session.close()


# 全局交易日历服务实例
trading_calendar_service = TradingCalendarService()
