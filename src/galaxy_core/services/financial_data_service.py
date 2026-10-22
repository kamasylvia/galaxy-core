"""财务数据同步服务 — 按 reporting_period 增量推进.

从 FinancialDataStorePort 获取 last_sync_period，按 [next_period, end] 范围
查询 API，UPSERT 结果后更新 last_sync_period。
支持日常增量同步（按季度推进）和每月全量刷新（覆盖最近 3 年）。
"""

import logging
from datetime import date, timedelta
from itertools import groupby
from operator import itemgetter
from typing import Any, Callable

from tqdm import tqdm

from galaxy_core.domain.ports.financial_data_provider import FinancialDataProviderPort
from galaxy_core.domain.ports.financial_data_store import FinancialDataStorePort
from galaxy_core.domain.ports.reference_provider import ReferenceProviderPort
from galaxy_core.domain.value_objects import (
    FinancialDataType,
    FinancialRecord,
    FinancialSyncResult,
)

logger = logging.getLogger(__name__)

_VALID_QUARTER_ENDS = ("0331", "0630", "0930", "1231")


def _next_period(period: str) -> str:
    """返回下一季度末日期字符串. "20240331" -> "20240630", "20241231" -> "20250331"."""
    if len(period) != 8 or period[4:] not in _VALID_QUARTER_ENDS:
        raise ValueError(f"非法季度末日期 '{period}'，期望 MMDD 为 {'/'.join(_VALID_QUARTER_ENDS)}")
    year = int(period[:4])
    mmdd = period[4:]
    next_map = {"0331": "0630", "0630": "0930", "0930": "1231", "1231": "0331"}
    next_year = year + 1 if mmdd == "1231" else year
    return f"{next_year:04d}{next_map[mmdd]}"


def _prev_n_years(period: str, n: int) -> str:
    """返回 n 年前的同季度末. "20240331" (n=3) -> "20210331"."""
    if len(period) != 8:
        raise ValueError(f"非法日期格式 '{period}'，期望 YYYYMMDD")
    return f"{int(period[:4]) - n:04d}{period[4:]}"


def _last_reporting_period() -> str:
    """当前日期对应的上一个完整报告期."""
    today = date.today()
    year, month = today.year, today.month
    if month <= 3:
        return f"{year - 1:04d}1231"
    elif month <= 6:
        return f"{year:04d}0331"
    elif month <= 9:
        return f"{year:04d}0630"
    else:
        return f"{year:04d}0930"


class FinancialDataService:
    """财务数据同步服务.

    流程：获取 A 股 → 过滤退市 → 推导日期范围 → 按 period 分组 →
    调 provider → 存 store → 更新 last_sync_period。
    """

    def __init__(
        self,
        provider: FinancialDataProviderPort,
        store: FinancialDataStorePort,
        reference_provider: ReferenceProviderPort,
        db_manager: Any = None,
    ) -> None:
        self._provider = provider
        self._store = store
        self._reference = reference_provider
        self._db_manager = db_manager

    async def sync(
        self,
        data_type: FinancialDataType,
        symbols: list[str] | None = None,
        start: str | None = None,
        end: str | None = None,
        full_refresh: bool = False,
    ) -> FinancialSyncResult:
        """同步财务数据.

        Args:
            data_type: 财务数据类型
            symbols: 证券代码列表，None 则自动获取全部 A 股
            start: 开始报告期 (YYYYMMDD)，None 则按增量/全量推导
            end: 结束报告期 (YYYYMMDD)，None 则为上一个完整报告期
            full_refresh: True 覆盖最近 3 年，False 增量推进
        """
        # 1. 获取 symbol 列表
        if symbols is None:
            from datetime import date as _date, timedelta
            from pathlib import Path
            from galaxy_core.shared_kernel.utils.config_loader import get_section
            from galaxy_core.shared_kernel.utils.universe import (
                resolve_universe_with_fallback,
            )

            cache_raw = get_section("amazing_data").get("local_path", "./data/local_cache/")
            local_path = str(Path(cache_raw).resolve())
            if cache_raw.endswith("/"):
                local_path += "/"
            yesterday = _date.today() - timedelta(days=1)
            symbols = await resolve_universe_with_fallback(
                reference_provider=self._reference,
                db_manager=self._db_manager,
                security_type="EXTRA_STOCK_A",
                end_date=yesterday,
                local_path=local_path,
            )

        # 2. 过滤退市
        active_symbols = await self._filter_active(symbols)
        if not active_symbols:
            logger.info("无活跃证券需要同步")
            return FinancialSyncResult()

        # 3. 推导 end（默认 T-1，与 K 线同步一致）
        if end is None:
            end = (date.today() - timedelta(days=1)).strftime("%Y%m%d")

        # 4. 构建 period 分组
        if start is not None:
            groups: list[tuple[str, str, list[str]]] = [(start, end, active_symbols)]
        elif full_refresh:
            groups = [(_prev_n_years(end, 3), end, active_symbols)]
        else:
            groups = await self._build_period_groups(active_symbols, data_type, end)

        symbols_needing_sync = sum(len(s) for _, _, s in groups)
        if symbols_needing_sync == 0:
            logger.info(f"所有证券 {data_type.value} 数据已最新")
            return FinancialSyncResult(total_symbols=len(active_symbols), success_count=len(active_symbols))

        logger.info(f"同步 {data_type.value}，{symbols_needing_sync}/{len(active_symbols)} 只证券需要更新")

        # 5. 按组查询 API 并保存
        provider_method = self._get_provider_method(data_type)
        total_synced = 0
        failed_codes: list[str] = []
        symbol_max_periods: dict[str, str] = {}

        progress = tqdm(total=symbols_needing_sync, desc=f"同步 {data_type.value}", unit="只", ncols=80)
        for query_start, query_end, group_symbols in groups:
            try:
                records = await provider_method(symbols=group_symbols, begin_date=query_start, end_date=query_end)
            except Exception as e:
                logger.debug(f"API 查询失败 ({len(group_symbols)} 只, {query_start}~{query_end}): {e}")
                failed_codes.extend(group_symbols)
                progress.update(len(group_symbols))
                continue

            if records:
                await self._store.save(records, data_type)
                total_synced += len(records)
                for sym, max_p in self._compute_symbol_max_periods(records).items():
                    symbol_max_periods[sym] = max_p
                logger.debug(f"同步 {len(group_symbols)} 只，{len(records)} 条记录，{query_start}~{query_end}")
            progress.update(len(group_symbols))

        progress.close()

        # 6. 更新 last_sync_period
        if symbol_max_periods:
            await self._store.set_last_sync_periods(symbol_max_periods, data_type)

        success_count = len(active_symbols) - len(failed_codes)
        logger.info(f"同步完成: {success_count}/{len(active_symbols)} 只成功, {total_synced} 条记录")
        if failed_codes:
            logger.debug(f"失败 {len(failed_codes)} 只: {failed_codes[:10]}")

        return FinancialSyncResult(
            total_symbols=len(active_symbols),
            success_count=success_count,
            synced_records=total_synced,
            failed_codes=failed_codes,
        )

    async def _filter_active(self, symbols: list[str]) -> list[str]:
        """过滤退市 symbol（无上市日期信息的排除）."""
        if not symbols:
            return []
        listing_dates = await self._reference.get_listing_dates(symbols, "EXTRA_STOCK_A_SH_SZ")
        return [sym for sym in symbols if listing_dates.get(sym) is not None]

    async def _build_period_groups(
        self, symbols: list[str], data_type: FinancialDataType, end_period: str,
    ) -> list[tuple[str, str, list[str]]]:
        """按 last_sync_period 构建增量同步分组.

        有记录的 symbol 从 _next_period(last) 开始，
        无记录的首次同步从 _prev_n_years(end, 3) 开始。
        """
        last_periods = await self._store.get_last_sync_periods(symbols, data_type)
        default_start = _prev_n_years(end_period, 3)

        ranges: list[tuple[str, str, str]] = []
        for symbol in symbols:
            last = last_periods.get(symbol)
            if last is not None:
                if data_type == FinancialDataType.DIVIDEND:
                    # dividend 的 period 是分红公告日(非季度末),直接 +1 天
                    from datetime import datetime as _dt, timedelta as _td
                    d = _dt.strptime(str(last), "%Y%m%d") + _td(days=1)
                    start = d.strftime("%Y%m%d")
                else:
                    start = _next_period(last)
            else:
                start = default_start
            if start <= end_period:
                ranges.append((start, end_period, symbol))

        if not ranges:
            return []

        ranges.sort(key=lambda x: (x[0], x[1]))
        grouped: list[tuple[str, str, list[str]]] = []
        for (qs, qe), group in groupby(ranges, key=itemgetter(0, 1)):
            grouped.append((qs, qe, [r[2] for r in group]))
        return grouped

    def _get_provider_method(self, data_type: FinancialDataType) -> Callable:
        """根据 data_type 返回对应的 provider async 方法."""
        method_map: dict[FinancialDataType, Callable] = {
            FinancialDataType.BALANCE_SHEET: self._provider.get_balance_sheet,
            FinancialDataType.CASH_FLOW: self._provider.get_cash_flow,
            FinancialDataType.INCOME: self._provider.get_income_statement,
            FinancialDataType.PROFIT_EXPRESS: self._provider.get_profit_express,
            FinancialDataType.PROFIT_NOTICE: self._provider.get_profit_notice,
            FinancialDataType.DIVIDEND: self._provider.get_dividend,
        }
        method = method_map.get(data_type)
        if method is None:
            raise ValueError(f"不支持的数据类型: {data_type}")
        return method

    @staticmethod
    def _compute_symbol_max_periods(records: list[FinancialRecord]) -> dict[str, str]:
        """计算每个 symbol 的最大 reporting_period."""
        result: dict[str, str] = {}
        for rec in records:
            existing = result.get(rec.symbol)
            if existing is None or rec.reporting_period > existing:
                result[rec.symbol] = rec.reporting_period
        return result
