"""交易日历服务."""

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import akshare as ak
import pandas as pd

from sqlalchemy import and_, func
from galaxy_db_bridge.database.core.connection import db_manager
from galaxy_db_bridge.database.models.trading_calendar import TradingCalendar
from galaxy_db_bridge.shared_kernel.enums.akshare import AkshareMarket

logger = logging.getLogger(__name__)


class TradingCalendarService:
    """交易日历服务."""

    def _get_normalized_market(self, market: str) -> str:
        """获取标准化的市场代码."""
        # 使用 AkshareMarket 枚举进行市场标准化
        return AkshareMarket.get_normalized_market(market)

    def get_trading_days(
        self, start_date: date, end_date: date, market: str = "SSE"
    ) -> List[date]:
        """获取指定日期范围内的交易日列表."""
        # 规范化市场参数
        normalized_market = self._get_normalized_market(market)

        session = db_manager.get_session()
        try:
            # 查询数据库中的完整日历记录（包括非交易日）
            # 用于判断缓存是否完全覆盖请求范围
            calendar_query = (
                session.query(TradingCalendar)
                .filter(
                    and_(
                        TradingCalendar.market == normalized_market,
                        TradingCalendar.trade_date >= start_date,
                        TradingCalendar.trade_date <= end_date,
                    )
                )
                .order_by(TradingCalendar.trade_date)
            )

            calendar_results = calendar_query.all()

            # 从完整日历中提取交易日
            cached_dates = [
                row.trade_date for row in calendar_results if row.is_trading_day
            ]

            # 检查缓存是否完全覆盖请求范围
            # 使用完整日历的边界（包括非交易日），而不是仅用交易日的边界
            # 因为 _save_to_db 保存的是完整日历，所以应该用完整日历来判断覆盖范围
            all_cached_dates = [row.trade_date for row in calendar_results]
            cache_has_data = len(all_cached_dates) > 0
            cache_fully_covers_range = (
                cache_has_data
                and min(all_cached_dates) <= start_date
                and max(all_cached_dates) >= end_date
            )

            if not cache_fully_covers_range:
                logger.info(
                    f"数据库缓存不足，从 akshare 获取 {start_date} 到 {end_date} 的交易日历"
                )
                additional_dates = self._fetch_from_akshare(
                    start_date, end_date, normalized_market
                )

                # 将新获取的数据存入数据库，传入请求的日期范围以确保完整覆盖
                self._save_to_db(
                    additional_dates, normalized_market, start_date, end_date
                )

                # 重新查询数据库
                query = (
                    session.query(TradingCalendar.trade_date)
                    .filter(
                        and_(
                            TradingCalendar.market == normalized_market,
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
                logger.info(
                    f"交易日历缓存命中: market={normalized_market}, "
                    f"range={start_date}~{end_date}, "
                    f"calendar_rows={len(all_cached_dates)}, trading_days={len(cached_dates)}"
                )

            return sorted(cached_dates)
        finally:
            session.close()

    def is_trading_day(self, check_date: date, market: str = "SSE") -> bool:
        """判断指定日期是否为交易日."""
        # 规范化市场参数
        normalized_market = self._get_normalized_market(market)

        session = db_manager.get_session()
        try:
            # 先查询数据库
            result = (
                session.query(TradingCalendar)
                .filter(
                    and_(
                        TradingCalendar.market == normalized_market,
                        TradingCalendar.trade_date == check_date,
                    )
                )
                .first()
            )

            if result:
                return result.is_trading_day

            # 如果数据库中没有，从 akshare 获取
            logger.info(f"数据库中无 {check_date} 的交易日信息，从 akshare 获取")
            trading_days = self._fetch_from_akshare(
                check_date, check_date, normalized_market
            )

            # 将数据存入数据库，传入请求的日期
            self._save_to_db(trading_days, normalized_market, check_date, check_date)

            # 再次查询
            result = (
                session.query(TradingCalendar)
                .filter(
                    and_(
                        TradingCalendar.market == normalized_market,
                        TradingCalendar.trade_date == check_date,
                    )
                )
                .first()
            )

            return result.is_trading_day if result else False
        finally:
            session.close()

    def filter_trading_days(self, dates: List[date], market: str = "SSE") -> List[date]:
        """过滤出指定日期列表中的交易日."""
        if not dates:
            return []

        # 规范化市场参数
        normalized_market = self._get_normalized_market(market)

        session = db_manager.get_session()
        try:
            # 找出数据库中已有的交易日
            existing_query = session.query(TradingCalendar).filter(
                and_(
                    TradingCalendar.market == normalized_market,
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

                all_trading_days = self._fetch_from_akshare(
                    min_date, max_date, normalized_market
                )

                # 将新获取的数据存入数据库，传入请求的日期范围
                self._save_to_db(
                    all_trading_days, normalized_market, min_date, max_date
                )

                # 重新查询数据库中对应的交易日
                filtered_query = session.query(TradingCalendar).filter(
                    and_(
                        TradingCalendar.market == normalized_market,
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

    def sync_calendar(self, year: int, market: str = "SSE") -> int:
        """手动同步指定年份的交易日历."""
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

        # 规范化市场参数
        normalized_market = self._get_normalized_market(market)

        logger.info(f"开始同步 {year} 年 {normalized_market} 交易日历...")

        trading_days = self._fetch_from_akshare(start_date, end_date, normalized_market)

        # 清除当年数据
        session = db_manager.get_session()
        try:
            session.query(TradingCalendar).filter(
                and_(
                    TradingCalendar.market == normalized_market,
                    TradingCalendar.year == year,
                )
            ).delete()

            # 保存新数据
            self._save_to_db(trading_days, normalized_market)

            session.commit()
            logger.info(
                f"成功同步 {year} 年 {normalized_market} 交易日历，共 {len(trading_days)} 个交易日"
            )
            return len(trading_days)
        except Exception as e:
            session.rollback()
            logger.error(f"同步 {year} 年 {normalized_market} 交易日历时出错: {e}")
            raise
        finally:
            session.close()

    def sync_current_year(self, market: str = "SSE") -> int:
        """同步当前年份的交易日历."""
        current_year = datetime.now().year
        return self.sync_calendar(current_year, market)

    async def sync_years(
        self, start_year: int, end_year: int, market: str = "SSE"
    ) -> Dict[str, int]:
        """异步同步多个年份的交易日历.

        Args:
            start_year: 开始年份
            end_year: 结束年份
            market: 市场代码，默认为 SSE

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
                count = await asyncio.to_thread(self.sync_calendar, year, market)

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

    def check_and_update_yearly(self, market: str = "SSE") -> bool:
        """年更检查（12月31日自动更新下一年）."""
        # 规范化市场参数
        normalized_market = self._get_normalized_market(market)

        today = date.today()
        if today.month == 12 and today.day == 31:
            next_year = today.year + 1
            logger.info(
                f"年更检查：开始同步 {next_year} 年 {normalized_market} 交易日历"
            )
            try:
                self.sync_calendar(next_year, normalized_market)
                return True
            except Exception as e:
                logger.error(f"年更同步失败: {e}")
                return False
        return False

    def _fetch_from_akshare(
        self, start_date: date, end_date: date, market: str = "SSE"
    ) -> List[date]:
        """从 akshare 获取交易日历."""
        logger.info(
            f"从 akshare 获取 {start_date} 到 {end_date} 的交易日历，市场: {market}"
        )

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

    def _save_to_db(
        self,
        trading_days: List[date],
        market: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ):
        """将交易日历数据保存到数据库.

        Args:
            trading_days: 交易日列表
            market: 市场代码
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
            # 获取所有日期的年份
            years = set(day.year for day, is_trading in full_calendar)

            # 中国市场统一保存为SSE，因为A股市场使用统一的交易日历
            normalized_market = "SSE" if market in ["SSE", "SZSE", "BSE"] else market

            # 删除已存在的年份数据（防止重复）
            session.query(TradingCalendar).filter(
                and_(
                    TradingCalendar.market == normalized_market,
                    TradingCalendar.year.in_(list(years)),
                )
            ).delete(synchronize_session=False)

            # 创建新记录，统一使用标准化的市场代码
            records = []
            for trade_date, is_trading_day in full_calendar:
                record = TradingCalendar(
                    market=normalized_market,
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
