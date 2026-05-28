"""K 线数据同步服务.

专门用于 K 线数据的同步服务，从 API 获取数据并存储到数据库。
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple

import pandas as pd

from galaxy_db_sync.amazing_data.api.client import amazing_data_client
from galaxy_db_sync.database.services.kline import kline_service
from galaxy_db_sync.database.services.empty_query import empty_query_service
from galaxy_db_sync.database.services.kline_completeness_checker import (
    CompletenessResult,
    kline_completeness_checker,
)
from galaxy_db_sync.database.services.missing_data_tracker import missing_data_tracker
from galaxy_db_sync.shared_kernel.utils.time_parser import (
    datetime_to_int,
    parse_date_to_datetime,
)
from galaxy_db_sync.database.services.trading_calendar import trading_calendar_service
from galaxy_db_sync.shared_kernel.utils import infer_security_type
from galaxy_db_sync.shared_kernel.enums.security_type import SecurityType
from galaxy_db_sync.shared_kernel.utils.interval_boundary_checker import IntervalBoundaryChecker
from galaxy_db_sync.shared_kernel.exceptions import SDKError

logger = logging.getLogger(__name__)


class KlineDataSyncService:
    """K 线数据同步服务."""

    def __init__(self):
        """初始化 K 线数据同步服务."""
        self.kline_service = kline_service
        self._interval_boundary_checker = IntervalBoundaryChecker()

    @property
    def interval_boundary_checker(self) -> IntervalBoundaryChecker:
        """获取周期边界检查器实例"""
        return self._interval_boundary_checker

    def get_kline_data_range(
        self,
        code: str,
        interval: str,
    ):
        """查询数据库中已有 K 线数据的日期范围."""
        return self.kline_service.get_data_range_for_symbol(code, interval)

    def save_kline_data(
        self,
        code: str,
        df: pd.DataFrame,
        interval: str,
        security_type: str = "stock",
    ) -> int:
        """将 K 线数据保存到数据库."""
        return self.kline_service.save_kline_to_db(code, df, interval, security_type)

    def _check_data_completeness(
        self,
        symbol: str,
        interval: str,
        start_date: date,
        end_date: date,
    ) -> CompletenessResult:
        """检查数据完整性并返回统一结果对象."""
        try:
            completeness_result = kline_completeness_checker.check(
                symbol=symbol,
                interval=interval,
                start_date=start_date,
                end_date=end_date,
            )

            logger.info(f"{symbol}: 完整性检查完成 - {completeness_result}")
            return completeness_result

        except Exception as e:
            logger.error(f"{symbol}: 完整性检查失败 - {e}")
            return self._fallback_completeness_check(
                symbol, interval, start_date, end_date
            )

    async def _check_data_completeness_async(
        self,
        symbol: str,
        interval: str,
        start_date: date,
        end_date: date,
    ) -> CompletenessResult:
        """检查数据完整性（异步版本）."""
        try:
            completeness_result = await kline_completeness_checker.check_async(
                symbol=symbol,
                interval=interval,
                start_date=start_date,
                end_date=end_date,
            )

            logger.info(f"{symbol}: 完整性检查完成 - {completeness_result}")
            return completeness_result

        except Exception as e:
            logger.error(f"{symbol}: 完整性检查失败 - {e}")
            return await self._fallback_completeness_check_async(
                symbol, interval, start_date, end_date
            )

    def _fallback_completeness_check(
        self,
        symbol: str,
        interval: str,
        start_date: date,
        end_date: date,
    ) -> CompletenessResult:
        """回退的完整性检查方法."""
        logger.warning(f"{symbol}: 使用回退方法检查完整性")

        trading_days = trading_calendar_service.get_trading_days(start_date, end_date)

        db_data = kline_service.query_kline_from_db(
            symbols=[symbol],
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            interval=interval,
        )

        existing_dates = set()
        if symbol in db_data and not db_data[symbol].empty:
            existing_dates = set(db_data[symbol].index.date)

        missing_dates = sorted(day for day in trading_days if day not in existing_dates)
        missing_ranges = self._merge_dates_to_ranges(missing_dates)
        total_count = len(trading_days)
        missing_count = len(missing_dates)
        coverage_ratio = (
            (total_count - missing_count) / total_count if total_count > 0 else 1.0
        )

        return CompletenessResult(
            is_complete=missing_count == 0,
            missing_count=missing_count,
            total_count=total_count,
            coverage_ratio=coverage_ratio,
            missing_ranges=missing_ranges,
            check_method="fallback_trading_day",
        )

    async def _fallback_completeness_check_async(
        self,
        symbol: str,
        interval: str,
        start_date: date,
        end_date: date,
    ) -> CompletenessResult:
        """回退的完整性检查方法（异步版本）."""
        logger.warning(f"{symbol}: 使用回退方法检查完整性 [async]")

        trading_days = await trading_calendar_service.get_trading_days_async(start_date, end_date)

        db_data = await kline_service.query_kline_from_db(
            symbols=[symbol],
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            interval=interval,
        )

        existing_dates = set()
        if symbol in db_data and not db_data[symbol].empty:
            existing_dates = set(db_data[symbol].index.date)

        missing_dates = sorted(day for day in trading_days if day not in existing_dates)
        missing_ranges = self._merge_dates_to_ranges(missing_dates)
        total_count = len(trading_days)
        missing_count = len(missing_dates)
        coverage_ratio = (
            (total_count - missing_count) / total_count if total_count > 0 else 1.0
        )

        return CompletenessResult(
            is_complete=missing_count == 0,
            missing_count=missing_count,
            total_count=total_count,
            coverage_ratio=coverage_ratio,
            missing_ranges=missing_ranges,
            check_method="fallback_trading_day_async",
        )

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

    def sync_kline_data(
        self,
        symbol: str,
        interval: str,
        start_date: str | None,
        end_date: str | None,
    ) -> int:
        """同步单个证券的 K 线数据.

        Args:
            symbol: 证券代码
            interval: K 线周期
            start_date: 开始日期字符串
            end_date: 结束日期字符串

        Returns:
            同步的数据条数
        """
        total_synced = 0

        try:
            logger.info(f"{symbol}: 开始同步 K 线数据...")

            start_dt = parse_date_to_datetime(start_date, interval)
            end_dt = parse_date_to_datetime(end_date, interval)

            # 需要将 datetime 对象转换为 date 对象
            start_date_obj = (
                start_dt.date() if isinstance(start_dt, datetime) else start_dt
            )
            end_date_obj = end_dt.date() if isinstance(end_dt, datetime) else end_dt

            # 对于长周期，自动调整 end_date 到已结束周期的边界
            if self._interval_boundary_checker.is_long_interval(interval):
                adjusted_end = self._interval_boundary_checker.get_last_complete_interval_end(
                    interval, end_date_obj
                )
                if adjusted_end < end_date_obj:
                    logger.info(
                        f"长周期 {interval} 调整 end_date: "
                        f"{end_date_obj.strftime('%Y%m%d')} -> {adjusted_end.strftime('%Y%m%d')} "
                        f"(当前周期未结束，使用上一周期结束日期)"
                    )
                    end_date_obj = adjusted_end

            logger.info(f"{symbol}: 请求日期范围 {start_date_obj} ~ {end_date_obj}")

            completeness_result = self._check_data_completeness(
                symbol=symbol,
                interval=interval,
                start_date=start_date_obj,
                end_date=end_date_obj,
            )

            if completeness_result.is_complete:
                logger.info(f"{symbol}: 数据已完整，无需获取新数据")
                return 0

            if not completeness_result.missing_ranges:
                logger.info(f"{symbol}: 未识别到需要同步的缺失区间")
                return 0

            missing_ranges_to_query = [
                (range_start, range_end)
                for range_start, range_end in completeness_result.missing_ranges
                if not empty_query_service.is_confirmed_empty(
                    symbol, interval, range_start, range_end
                )
            ]

            if not missing_ranges_to_query:
                logger.info(f"{symbol}: 所有缺失区间都已被确认为空数据，跳过 API 查询")
                return 0

            logger.info(
                f"开始同步K线数据: {symbol} {interval} "
                f"{start_date_obj.strftime('%Y%m%d')} - {end_date_obj.strftime('%Y%m%d')}"
            )

            for range_start, range_end in missing_ranges_to_query:
                range_start_int = datetime_to_int(range_start)
                range_end_int = datetime_to_int(range_end)

                logger.info(
                    f"{symbol}: 正在获取 {range_start_int} ~ {range_end_int} 的数据..."
                )

                try:
                    kline_dict = amazing_data_client.get_kline(
                        code_list=[symbol],
                        begin_date=range_start_int,
                        end_date=range_end_int,
                        interval=interval,
                    )
                except TypeError as e:
                    if "'NoneType' object cannot be interpreted as an integer" in str(e):
                        logger.warning(
                            f"{symbol}: API 调用遇到已知 SDK 错误，跳过区间 "
                            f"{range_start_int} ~ {range_end_int} 且不写入空结果缓存: {e}"
                        )
                        continue
                    raise
                except SDKError as e:
                    logger.error(f"{symbol}: SDK 错误: {e.message}")
                    raise
                except Exception as e:
                    logger.error(f"{symbol}: API 调用失败: {type(e).__name__}: {e}")
                    raise

                if symbol in kline_dict:
                    df = kline_dict[symbol]
                    if df is not None and not df.empty:
                        inferred_security_type = infer_security_type(symbol)

                        if interval.lower() == "year" and inferred_security_type not in [
                            SecurityType.SH_ETF.value,
                            SecurityType.SZ_ETF.value,
                            SecurityType.EXTRA_ETF.value,
                        ]:
                            logger.warning(
                                f"{symbol}: 年线数据同步中发现非 ETF 代码（推断类型为 {inferred_security_type}），跳过保存"
                            )
                            continue

                        saved_count = self.save_kline_data(
                            code=symbol,
                            df=df,
                            interval=interval,
                            security_type=inferred_security_type or "stock",
                        )
                        total_synced += saved_count
                        logger.info(f"{symbol}: 获取并保存了 {saved_count} 条数据")
                    else:
                        logger.warning(
                            f"{symbol}: API 返回空数据，跳过区间 "
                            f"{range_start_int} ~ {range_end_int} 并记录到空结果缓存"
                        )
                        empty_query_service.record_empty_result(
                            symbol, interval, range_start, range_end
                        )
                else:
                    logger.warning(
                        f"{symbol}: 未找到 {range_start_int} ~ {range_end_int} 的数据，"
                        f"记录到空结果缓存"
                    )
                    empty_query_service.record_empty_result(
                        symbol, interval, range_start, range_end
                    )

        except Exception as e:
            logger.error(f"{symbol}: 处理失败 - {e}")
            import traceback

            traceback.print_exc()
            raise

        return total_synced

    async def sync_kline_data_async(
        self,
        symbol: str,
        interval: str,
        start_date: str | None,
        end_date: str | None,
    ) -> int:
        """同步单个证券的 K 线数据（异步版本）.

        Args:
            symbol: 证券代码
            interval: K 线周期
            start_date: 开始日期字符串
            end_date: 结束日期字符串

        Returns:
            同步的数据条数
        """
        total_synced = 0

        try:
            logger.info(f"{symbol}: 开始同步 K 线数据 [async]...")

            start_dt = parse_date_to_datetime(start_date, interval)
            end_dt = parse_date_to_datetime(end_date, interval)

            start_date_obj = (
                start_dt.date() if isinstance(start_dt, datetime) else start_dt
            )
            end_date_obj = end_dt.date() if isinstance(end_dt, datetime) else end_dt

            # 对于长周期，自动调整 end_date 到已结束周期的边界
            if self._interval_boundary_checker.is_long_interval(interval):
                adjusted_end = await asyncio.to_thread(
                    self._interval_boundary_checker.get_last_complete_interval_end,
                    interval, end_date_obj
                )
                if adjusted_end < end_date_obj:
                    logger.info(
                        f"长周期 {interval} 调整 end_date: "
                        f"{end_date_obj.strftime('%Y%m%d')} -> {adjusted_end.strftime('%Y%m%d')} "
                        f"(当前周期未结束，使用上一周期结束日期)"
                    )
                    end_date_obj = adjusted_end

            logger.info(f"{symbol}: 请求日期范围 {start_date_obj} ~ {end_date_obj}")

            completeness_result = await self._check_data_completeness_async(
                symbol=symbol,
                interval=interval,
                start_date=start_date_obj,
                end_date=end_date_obj,
            )

            if completeness_result.is_complete:
                logger.info(f"{symbol}: 数据已完整，无需获取新数据")
                return 0

            if not completeness_result.missing_ranges:
                logger.info(f"{symbol}: 未识别到需要同步的缺失区间")
                return 0

            # 异步检查缺失区间是否已确认为空
            missing_ranges_to_query = []
            for range_start, range_end in completeness_result.missing_ranges:
                if not await empty_query_service.is_confirmed_empty_async(
                    symbol, interval, range_start, range_end
                ):
                    missing_ranges_to_query.append((range_start, range_end))

            if not missing_ranges_to_query:
                logger.info(f"{symbol}: 所有缺失区间都已被确认为空数据，跳过 API 查询")
                return 0

            logger.info(
                f"开始同步K线数据: {symbol} {interval} "
                f"{start_date_obj.strftime('%Y%m%d')} - {end_date_obj.strftime('%Y%m%d')}"
            )

            for range_start, range_end in missing_ranges_to_query:
                range_start_int = datetime_to_int(range_start)
                range_end_int = datetime_to_int(range_end)

                logger.info(
                    f"{symbol}: 正在获取 {range_start_int} ~ {range_end_int} 的数据..."
                )

                try:
                    # SDK is sync, use asyncio.to_thread
                    kline_dict = await asyncio.to_thread(
                        amazing_data_client.get_kline,
                        code_list=[symbol],
                        begin_date=range_start_int,
                        end_date=range_end_int,
                        interval=interval,
                    )
                except TypeError as e:
                    if "'NoneType' object cannot be interpreted as an integer" in str(e):
                        logger.warning(
                            f"{symbol}: API 调用遇到已知 SDK 错误，跳过区间 "
                            f"{range_start_int} ~ {range_end_int} 且不写入空结果缓存: {e}"
                        )
                        continue
                    raise
                except SDKError as e:
                    logger.error(f"{symbol}: SDK 错误: {e.message}")
                    raise
                except Exception as e:
                    logger.error(f"{symbol}: API 调用失败: {type(e).__name__}: {e}")
                    raise

                if symbol in kline_dict:
                    df = kline_dict[symbol]
                    if df is not None and not df.empty:
                        inferred_security_type = infer_security_type(symbol)

                        if interval.lower() == "year" and inferred_security_type not in [
                            SecurityType.SH_ETF.value,
                            SecurityType.SZ_ETF.value,
                            SecurityType.EXTRA_ETF.value,
                        ]:
                            logger.warning(
                                f"{symbol}: 年线数据同步中发现非 ETF 代码（推断类型为 {inferred_security_type}），跳过保存"
                            )
                            continue

                        saved_count = await self.kline_service.save_kline_to_db(
                            symbol=symbol,
                            df=df,
                            interval=interval,
                            security_type=inferred_security_type or "stock",
                        )
                        total_synced += saved_count
                        logger.info(f"{symbol}: 获取并保存了 {saved_count} 条数据")
                    else:
                        logger.warning(
                            f"{symbol}: API 返回空数据，跳过区间 "
                            f"{range_start_int} ~ {range_end_int} 并记录到空结果缓存"
                        )
                        await empty_query_service.record_empty_result_async(
                            symbol, interval, range_start, range_end
                        )
                else:
                    logger.warning(
                        f"{symbol}: 未找到 {range_start_int} ~ {range_end_int} 的数据，"
                        f"记录到空结果缓存"
                    )
                    await empty_query_service.record_empty_result_async(
                        symbol, interval, range_start, range_end
                    )

        except Exception as e:
            logger.error(f"{symbol}: 处理失败 - {e}")
            import traceback

            traceback.print_exc()
            raise

        return total_synced


    def batch_sync_kline_data(
        self,
        symbols: List[str],
        interval: str,
        start_date: str,
        end_date: str,
        completeness_results: dict = None,
        batch_size: int = 500,
    ) -> "BatchSyncResult":
        """批量同步 K 线数据（按日期缺失区间分批）.

        Args:
            symbols: 证券代码列表
            interval: K线周期
            start_date: 开始日期 (YYYYMMDD 格式)
            end_date: 结束日期 (YYYYMMDD 格式)
            completeness_results: 完整性检查结果，用于按缺失区间分批
            batch_size: 每批处理的最大证券数量（在单个日期区间内）

        Returns:
            BatchSyncResult: 批量同步结果
        """
        # 如果没有提供完整性结果，或没有缺失区间，按原来的方式处理
        if not completeness_results:
            return self._batch_sync_by_symbol_count(
                symbols, interval, start_date, end_date, batch_size
            )

        # 按日期缺失区间分组（使用统一的完整日期范围）
        range_groups = self._group_by_missing_ranges(
            {s: completeness_results[s] for s in symbols if s in completeness_results},
            interval,
            full_start=start_date,
            full_end=end_date,
        )

        if not range_groups:
            logger.info("没有需要同步的日期区间")
            return BatchSyncResult(
                success_count=len(symbols),
                synced_records=0,
                failed_codes=[],
            )

        total_saved = 0
        success_count = 0
        failed_codes = []
        api_call_count = 0

        # 按日期区间分批处理
        for (begin_int, end_int), symbols_in_range in range_groups.items():
            logger.debug(
                f"同步区间 {begin_int} ~ {end_int}: {len(symbols_in_range)} 个证券"
            )

            # 解析日期区间
            start_dt = datetime.strptime(str(begin_int), "%Y%m%d").date()
            end_dt = datetime.strptime(str(end_int), "%Y%m%d").date()

            # 在单个日期区间内，再按 batch_size 分批处理证券
            for i in range(0, len(symbols_in_range), batch_size):
                batch = symbols_in_range[i : i + batch_size]

                try:
                    # 批量 API 查询
                    kline_dict = amazing_data_client.get_kline(
                        code_list=batch,
                        begin_date=begin_int,
                        end_date=end_int,
                        interval=interval,
                    )
                    api_call_count += 1
                except TypeError as e:
                    if "'NoneType' object cannot be interpreted as an integer" in str(e):
                        logger.warning(
                            f"批次 API 调用遇到已知 SDK 错误，跳过区间 {begin_int} ~ {end_int} 且不写入空结果缓存: {e}"
                        )
                        continue
                    raise

                try:
                    # 扟量保存
                    saved_count = self.kline_service.batch_save_kline_to_db(kline_dict, interval)
                    total_saved += saved_count

                    # 统计成功/失败
                    for symbol in batch:
                        if (
                            symbol in kline_dict
                            and kline_dict[symbol] is not None
                            and not kline_dict[symbol].empty
                        ):
                            success_count += 1
                            # 检查 API 返回的数据是否覆盖请求范围
                            # 对于新上市 ETF，上市前的日期不会有数据，需要确认缺失
                            df = kline_dict[symbol]
                            if len(df) > 0:
                                from datetime import timedelta as td
                                # API 返回的 DataFrame 使用 RangeIndex，日期在 kline_time 列
                                min_time = df['kline_time'].min()
                                max_time = df['kline_time'].max()
                                min_date = min_time.date() if isinstance(min_time, datetime) else min_time
                                max_date = max_time.date() if isinstance(max_time, datetime) else max_time

                                # 如果返回数据的最早日期晚于请求的开始日期
                                # 说明上市前的日期没有数据，确认缺失
                                if min_date > start_dt:
                                    logger.info(
                                        f"{symbol}: API 返回数据从 {min_date} 开始，"
                                        f"请求范围 {start_dt}~{end_dt}，确认 {start_dt}~{min_date - td(days=1)} 为缺失"
                                    )
                                    missing_data_tracker.confirm_missing_as_api_empty(
                                        symbol, interval, start_dt, min_date - td(days=1),
                                        api_response=f"Data starts from {min_date}, likely pre-listing period"
                                    )

                                # 如果返回数据的最晚日期早于请求的结束日期
                                # 说明结束后的日期没有数据，确认缺失
                                if max_date < end_dt:
                                    logger.info(
                                        f"{symbol}: API 返回数据到 {max_date} 结束，"
                                        f"请求范围 {start_dt}~{end_dt}，确认 {max_date + td(days=1)}~{end_dt} 为缺失"
                                    )
                                    missing_data_tracker.confirm_missing_as_api_empty(
                                        symbol, interval, max_date + td(days=1), end_dt,
                                        api_response=f"Data ends at {max_date}, likely post-listing or future"
                                    )
                        else:
                            # 如果 API 返回空，也认为是成功的（标记为已确认无数据）
                            if symbol in kline_dict:
                                success_count += 1
                                # 记录到空查询缓存
                                empty_query_service.record_empty_result(
                                    symbol, interval, start_dt, end_dt
                                )
                                # 确认缺失为 API_EMPTY
                                missing_data_tracker.confirm_missing_as_api_empty(
                                    symbol, interval, start_dt, end_dt,
                                    api_response="API returned empty DataFrame"
                                )
                            else:
                                failed_codes.append(symbol)

                except Exception as e:
                    logger.error(f"  批次处理失败: {type(e).__name__}: {e}")
                    failed_codes.extend(batch)

        # 整合显示单次同步结果
        if total_saved > 0 or api_call_count > 0:
            logger.info(
                f"同步完成: API 调用 {api_call_count} 次, 保存 {total_saved} 条记录, "
                f"成功 {success_count}/{len(symbols)} 只证券"
            )

        if failed_codes:
            logger.warning(f"同步失败的证券: {failed_codes}")

        return BatchSyncResult(
            success_count=success_count,
            synced_records=total_saved,
            failed_codes=failed_codes,
        )

    def _group_by_missing_ranges(
        self,
        completeness_results: dict,
        interval: str,
        full_start: str | None = None,
        full_end: str | None = None,
    ) -> dict[tuple[int, int], list[str]]:
        """按缺失区间对 symbol 进行分组.

        优化策略：使用用户请求的完整日期范围进行批量查询，
        减少 API 调用次数。数据库 UPSERT 处理重复数据（TimescaleDB 高效）。

        同时跳过已确认缺失的范围（API 返回空的，如停牌期间）。

        Args:
            completeness_results: 每个 symbol 的完整性检查结果 {symbol: CompletenessResult}
            interval: K 线周期名称
            full_start: 用户请求的完整开始日期（YYYYMMDD）
            full_end: 用户请求的完整结束日期（YYYYMMDD）

        Returns:
            dict: key 为 (begin_date, end_date), value 为 symbol 列表
        """
        from datetime import date

        range_groups: dict[tuple[int, int], list[str]] = {}
        confirmed_missing_symbols = []
        symbols_to_sync = []

        # 解析完整日期范围
        if not full_start or not full_end:
            logger.warning("未提供完整日期范围，无法使用宽松分组策略")
            return {}

        try:
            begin_int = int(full_start)
            end_int = int(full_end)
        except ValueError:
            # 处理日期字符串格式
            start_dt = date.fromisoformat(str(full_start))
            end_dt = date.fromisoformat(str(full_end))
            begin_int = int(start_dt.strftime("%Y%m%d"))
            end_int = int(end_dt.strftime("%Y%m%d"))

        for symbol, result in completeness_results.items():
            if result.is_complete:
                continue

            if not result.missing_ranges:
                continue

            # 记录缺失范围到追踪表
            for range_start, range_end in result.missing_ranges:
                missing_data_tracker.record_missing_range(
                    symbol=symbol,
                    interval=interval,
                    check_start=date.fromisoformat(str(full_start)) if full_start else range_start,
                    check_end=date.fromisoformat(str(full_end)) if full_end else range_end,
                    missing_start=range_start,
                    missing_end=range_end,
                )

            # 检查所有缺失范围是否都已确认
            all_confirmed = True
            for range_start, range_end in result.missing_ranges:
                if not missing_data_tracker.is_range_confirmed_missing(
                    symbol, interval, range_start, range_end
                ):
                    all_confirmed = False
                    break

            if all_confirmed:
                confirmed_missing_symbols.append(symbol)
                continue

            # 使用完整日期范围，不按精确缺失区间分组
            symbols_to_sync.append(symbol)

        if confirmed_missing_symbols:
            logger.info(
                f"跳过已确认缺失的 {len(confirmed_missing_symbols)} 只证券（如停牌期间）"
            )

        # 所有待同步证券使用同一个完整日期范围
        if symbols_to_sync:
            range_groups[(begin_int, end_int)] = symbols_to_sync

        return range_groups

    async def _group_by_missing_ranges_async(
        self,
        completeness_results: dict,
        interval: str,
        full_start: str | None = None,
        full_end: str | None = None,
    ) -> dict[tuple[int, int], list[str]]:
        """按缺失区间对 symbol 进行分组（异步版本）.

        优化策略：使用用户请求的完整日期范围进行批量查询，
        减少 API 调用次数。数据库 UPSERT 处理重复数据（TimescaleDB 高效）。

        同时跳过已确认缺失的范围（API 返回空的，如停牌期间）。
        """
        from datetime import date

        range_groups: dict[tuple[int, int], list[str]] = {}
        confirmed_missing_symbols = []
        symbols_to_sync = []

        # 解析完整日期范围
        if not full_start or not full_end:
            logger.warning("未提供完整日期范围，无法使用宽松分组策略")
            return {}

        try:
            begin_int = int(full_start)
            end_int = int(full_end)
        except ValueError:
            # 处理日期字符串格式
            start_dt = date.fromisoformat(str(full_start))
            end_dt = date.fromisoformat(str(full_end))
            begin_int = int(start_dt.strftime("%Y%m%d"))
            end_int = int(end_dt.strftime("%Y%m%d"))

        for symbol, result in completeness_results.items():
            if result.is_complete:
                continue

            if not result.missing_ranges:
                continue

            # 异步记录缺失范围到追踪表
            for range_start, range_end in result.missing_ranges:
                await missing_data_tracker.record_missing_range_async(
                    symbol=symbol,
                    interval=interval,
                    check_start=date.fromisoformat(str(full_start)) if full_start else range_start,
                    check_end=date.fromisoformat(str(full_end)) if full_end else range_end,
                    missing_start=range_start,
                    missing_end=range_end,
                )

            # 异步检查所有缺失范围是否都已确认
            all_confirmed = True
            for range_start, range_end in result.missing_ranges:
                if not await missing_data_tracker.is_range_confirmed_missing_async(
                    symbol, interval, range_start, range_end
                ):
                    all_confirmed = False
                    break

            if all_confirmed:
                confirmed_missing_symbols.append(symbol)
                continue

            # 使用完整日期范围，不按精确缺失区间分组
            symbols_to_sync.append(symbol)

        if confirmed_missing_symbols:
            logger.info(
                f"跳过已确认缺失的 {len(confirmed_missing_symbols)} 只证券（如停牌期间）"
            )

        # 所有待同步证券使用同一个完整日期范围
        if symbols_to_sync:
            range_groups[(begin_int, end_int)] = symbols_to_sync

        return range_groups

    def _batch_sync_by_symbol_count(
        self,
        symbols: List[str],
        interval: str,
        start_date: str,
        end_date: str,
        batch_size: int = 500,
    ) -> "BatchSyncResult":
        """按证券数量分批同步（回退方案）.

        Args:
            symbols: 证券代码列表
            interval: K线周期
            start_date: 开始日期 (YYYYMMDD 格式)
            end_date: 结束日期 (YYYYMMDD 格式)
            batch_size: 每批处理的证券数量

        Returns:
            BatchSyncResult: 批量同步结果
        """
        total_saved = 0
        success_count = 0
        failed_codes = []

        # 确保日期是整数格式 (YYYYMMDD)
        try:
            start_int = int(start_date) if start_date else None
            end_int = int(end_date) if end_date else None

            # 处理年份格式 (如 2025 -> 20250101)
            if start_int and len(str(start_int)) == 4:
                start_int = start_int * 10000 + 101
            if end_int and len(str(end_int)) == 4:
                end_int = end_int * 10000 + 1231

        except ValueError:
            from galaxy_db_sync.shared_kernel.utils.time_parser import parse_date_to_datetime
            start_dt = parse_date_to_datetime(start_date, interval)
            end_dt = parse_date_to_datetime(end_date, interval)
            start_int = int(start_dt.strftime('%Y%m%d')) if isinstance(start_dt, datetime) else int(start_dt)
            end_int = int(end_dt.strftime('%Y%m%d')) if isinstance(end_dt, datetime) else int(end_dt)

        # 按证券数量分批处理
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]

            try:
                # 批量 API 查询
                kline_dict = amazing_data_client.get_kline(
                    code_list=batch,
                    begin_date=start_int,
                    end_date=end_int,
                    interval=interval,
                )

                # 批量保存
                saved_count = self.kline_service.batch_save_kline_to_db(kline_dict, interval)
                total_saved += saved_count

                # 统计成功/失败
                for symbol in batch:
                    if (
                        symbol in kline_dict
                        and kline_dict[symbol] is not None
                        and not kline_dict[symbol].empty
                    ):
                        success_count += 1
                    else:
                        failed_codes.append(symbol)

            except Exception as e:
                logger.error(f"批次处理失败: {type(e).__name__}: {e}")
                failed_codes.extend(batch)

        return BatchSyncResult(
            success_count=success_count,
            synced_records=total_saved,
            failed_codes=failed_codes,
        )

    async def batch_sync_kline_data_async(
        self,
        symbols: List[str],
        interval: str,
        start_date: str,
        end_date: str,
        completeness_results: dict = None,
        batch_size: int = 500,
    ) -> "BatchSyncResult":
        """异步批量同步 K 线数据（按日期缺失区间分批）.

        Args:
            symbols: 证券代码列表
            interval: K线周期
            start_date: 开始日期 (YYYYMMDD 格式)
            end_date: 结束日期 (YYYYMMDD 格式)
            completeness_results: 完整性检查结果，用于按缺失区间分批
            batch_size: 每批处理的最大证券数量（在单个日期区间内）

        Returns:
            BatchSyncResult: 批量同步结果
        """
        # 如果没有提供完整性结果，或没有缺失区间，按原来的方式处理
        if not completeness_results:
            return await self._batch_sync_by_symbol_count_async(
                symbols, interval, start_date, end_date, batch_size
            )

        # 异步按日期缺失区间分组（使用统一的完整日期范围）
        range_groups = await self._group_by_missing_ranges_async(
            {s: completeness_results[s] for s in symbols if s in completeness_results},
            interval,
            full_start=start_date,
            full_end=end_date,
        )

        if not range_groups:
            logger.info("没有需要同步的日期区间")
            return BatchSyncResult(
                success_count=len(symbols),
                synced_records=0,
                failed_codes=[],
            )

        total_saved = 0
        success_count = 0
        failed_codes = []
        api_call_count = 0

        # 按日期区间分批处理
        for (begin_int, end_int), symbols_in_range in range_groups.items():
            logger.debug(
                f"同步区间 {begin_int} ~ {end_int}: {len(symbols_in_range)} 个证券"
            )

            # 解析日期区间
            start_dt = datetime.strptime(str(begin_int), "%Y%m%d").date()
            end_dt = datetime.strptime(str(end_int), "%Y%m%d").date()

            # 在单个日期区间内，再按 batch_size 分批处理证券
            for i in range(0, len(symbols_in_range), batch_size):
                batch = symbols_in_range[i : i + batch_size]

                try:
                    # 批量 API 查询 (SDK is sync, use asyncio.to_thread)
                    kline_dict = await asyncio.to_thread(
                        amazing_data_client.get_kline,
                        code_list=batch,
                        begin_date=begin_int,
                        end_date=end_int,
                        interval=interval,
                    )
                    api_call_count += 1
                except TypeError as e:
                    if "'NoneType' object cannot be interpreted as an integer" in str(e):
                        logger.warning(
                            f"批次 API 调用遇到已知 SDK 错误，跳过区间 {begin_int} ~ {end_int} 且不写入空结果缓存: {e}"
                        )
                        continue
                    raise

                try:
                    # 批量保存 (async)
                    saved_count = await self.kline_service.batch_save_kline_to_db(kline_dict, interval)
                    total_saved += saved_count

                    # 统计成功/失败
                    for symbol in batch:
                        if (
                            symbol in kline_dict
                            and kline_dict[symbol] is not None
                            and not kline_dict[symbol].empty
                        ):
                            success_count += 1
                            # 注意：不标记整个范围为已同步
                            # 因为 API 返回的数据可能只覆盖部分日期（如停牌期间缺失）
                            # 下次完整性检查会重新计算实际缺失
                        else:
                            # 如果 API 返回空，也认为是成功的（标记为已确认无数据）
                            if symbol in kline_dict:
                                success_count += 1
                                # 异步记录到空查询缓存
                                await empty_query_service.record_empty_result_async(
                                    symbol, interval, start_dt, end_dt
                                )
                                # 异步确认缺失为 API_EMPTY
                                await missing_data_tracker.confirm_missing_as_api_empty_async(
                                    symbol, interval, start_dt, end_dt,
                                    api_response="API returned empty DataFrame"
                                )
                            else:
                                failed_codes.append(symbol)

                except Exception as e:
                    logger.error(f"  批次处理失败: {type(e).__name__}: {e}")
                    failed_codes.extend(batch)

        # 整合显示单次同步结果
        if total_saved > 0 or api_call_count > 0:
            logger.info(
                f"同步完成: API 调用 {api_call_count} 次, 保存 {total_saved} 条记录, "
                f"成功 {success_count}/{len(symbols)} 只证券"
            )

        if failed_codes:
            logger.warning(f"同步失败的证券: {failed_codes}")

        return BatchSyncResult(
            success_count=success_count,
            synced_records=total_saved,
            failed_codes=failed_codes,
        )

    async def _batch_sync_by_symbol_count_async(
        self,
        symbols: List[str],
        interval: str,
        start_date: str,
        end_date: str,
        batch_size: int = 500,
    ) -> "BatchSyncResult":
        """异步版本：按证券数量分批同步.

        当没有完整性结果时使用此方法。
        """
        total_saved = 0
        success_count = 0
        failed_codes = []

        # 确保日期是整数格式 (YYYYMMDD)
        try:
            start_int = int(start_date) if start_date else None
            end_int = int(end_date) if end_date else None

            # 处理年份格式 (如 2025 -> 20250101)
            if start_int and len(str(start_int)) == 4:
                start_int = start_int * 10000 + 101
            if end_int and len(str(end_int)) == 4:
                end_int = end_int * 10000 + 1231

        except ValueError:
            from galaxy_db_sync.shared_kernel.utils.time_parser import parse_date_to_datetime
            start_dt = parse_date_to_datetime(start_date, interval)
            end_dt = parse_date_to_datetime(end_date, interval)
            start_int = int(start_dt.strftime('%Y%m%d')) if isinstance(start_dt, datetime) else int(start_dt)
            end_int = int(end_dt.strftime('%Y%m%d')) if isinstance(end_dt, datetime) else int(end_dt)

        # 按证券数量分批处理
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]

            try:
                # 批量 API 查询 (SDK is sync, use asyncio.to_thread)
                kline_dict = await asyncio.to_thread(
                    amazing_data_client.get_kline,
                    code_list=batch,
                    begin_date=start_int,
                    end_date=end_int,
                    interval=interval,
                )

                # 批量保存 (async)
                saved_count = await self.kline_service.batch_save_kline_to_db(kline_dict, interval)
                total_saved += saved_count

                # 统计成功/失败
                for symbol in batch:
                    if (
                        symbol in kline_dict
                        and kline_dict[symbol] is not None
                        and not kline_dict[symbol].empty
                    ):
                        success_count += 1
                    else:
                        failed_codes.append(symbol)

            except Exception as e:
                logger.error(f"批次处理失败: {type(e).__name__}: {e}")
                failed_codes.extend(batch)

        return BatchSyncResult(
            success_count=success_count,
            synced_records=total_saved,
            failed_codes=failed_codes,
        )


@dataclass
class BatchSyncResult:
    """批量同步结果."""

    success_count: int
    synced_records: int
    failed_codes: List[str]

    @property
    def failed_count(self) -> int:
        return len(self.failed_codes)


# 全局 K 线数据同步服务实例
kline_data_sync_service = KlineDataSyncService()
