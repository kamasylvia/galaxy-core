"""K 线数据同步服务 — last_sync_date 纯追加模式.

从 KlineStorePort 获取 last_sync_date，按 [last+1, end] 范围查询 API，
UPSERT 结果后更新 last_sync_date 为实际 MAX(trade_time)。
无交易日历比对、无缺失日期计算、无空缓存处理。
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from itertools import groupby
from operator import itemgetter

from tqdm import tqdm

from galaxy_core.domain.date_range.parser import expand_date_to_full
from galaxy_core.domain.ports.calendar_store import CalendarStorePort
from galaxy_core.domain.ports.kline_provider import KlineProviderPort
from galaxy_core.domain.ports.kline_store import KlineStorePort
from galaxy_core.domain.ports.reference_provider import ReferenceProviderPort
from galaxy_core.domain.value_objects import Interval
from galaxy_core.shared_kernel.exceptions.api import EmptyResponseError
from galaxy_core.shared_kernel.utils.chunking import resolve_kline_chunk_size

logger = logging.getLogger(__name__)

# AM 返空检测:目标日期(end)覆盖率低于此阈值 → raise EmptyResponseError。
# 2026-08-14 补强:原 `total_synced==0` 漏了「部分空」(少量历史补数据混入
# 逃过 0 条检查,2026-08-13 案例 180 条旧股退市前数据)。改为检查入库 symbol
# 中 max_date >= end_date 的比例,覆盖率 < 10% 即判 AM 返空(给停牌等留容差)。
_EMPTY_RESPONSE_COVERAGE_THRESHOLD = 0.1


@dataclass
class SyncResult:
    """同步结果."""

    total_symbols: int = 0
    success_count: int = 0
    synced_records: int = 0
    failed_codes: list[str] = field(default_factory=list)


class KlineDataService:
    """K 线数据同步服务 — last_sync_date 纯追加模式.

    流程：
    1. 解析默认日期
    2. 从 store 获取 last_sync_date
    3. 为每个 symbol 构建 [last+1, end] 查询范围
    4. 按相同查询范围分组 symbols，批量调用 API
    5. UPSERT 数据，更新 last_sync_date 为 MAX(trade_time)
    6. 空 API 响应不推进 last_sync_date（D-02）
    """

    def __init__(
        self,
        kline_provider: KlineProviderPort,
        kline_store: KlineStorePort,
        reference_provider: ReferenceProviderPort,
        calendar_store: CalendarStorePort,
    ) -> None:
        self._provider = kline_provider
        self._store = kline_store
        self._reference = reference_provider
        self._calendar_store = calendar_store

    async def sync(
        self,
        symbols: list[str],
        interval: Interval,
        start: str | None = None,
        end: str | None = None,
    ) -> SyncResult:
        """同步 K 线数据.

        Args:
            symbols: 证券代码列表
            interval: K 线周期
            start: 开始日期 (YYYYMMDD)，None 则按配置推导
            end: 结束日期 (YYYYMMDD)，None 则为 T-1

        Returns:
            SyncResult: 同步结果
        """
        # 1. 推导默认日期
        if start is None:
            start = self._resolve_default_start(symbols)
        if end is None:
            end = (date.today() - timedelta(days=1)).strftime("%Y%m%d")

        start = expand_date_to_full(start, interval.value, is_end=False)
        end = expand_date_to_full(end, interval.value, is_end=True)

        assert start is not None and end is not None

        logger.info(f"同步 {len(symbols)} 只证券，{interval.value}，{start} ~ {end}")

        # 2. 获取 last_sync_date
        last_sync_dates = await self._store.get_last_sync_dates(symbols, interval)

        # 3. 构建同步范围并按相同查询范围分组
        start_dt = datetime.strptime(start[:8], "%Y%m%d").date()
        groups = self._build_and_group_ranges(symbols, last_sync_dates, start_dt, end)

        symbols_needing_sync = sum(len(s) for _, _, s in groups)
        if symbols_needing_sync == 0:
            logger.info("所有证券数据已最新")
            return SyncResult(
                total_symbols=len(symbols),
                success_count=len(symbols),
            )

        logger.info(f"需同步 {symbols_needing_sync} 只证券")

        # 4. 按分组查询 API 并保存
        total_synced = 0
        failed_codes: list[str] = []
        symbol_max_dates: dict[str, date] = {}

        progress = tqdm(
            total=symbols_needing_sync,
            desc=f"同步 {interval.value} K线",
            unit="只",
            ncols=80,
        )
        for query_start, query_end, group_symbols in groups:
            # 组内分 chunk(内存预算模型):按窗口天数 + 周期估算 每 symbol 行数,
            # 反推 chunk_size 使每批行数 ≤ 内存预算(api_batch_rows)。
            # 全量 day(3159行/只)→ ~500 只/批(分批防 OOM);
            # 增量 day(1行/只)→ ~158 万只/批(等于不分批,避免浪费 API 调用)。
            # 失败粒度为单 chunk,沿用原 try/except/continue 模式。
            chunk_size = resolve_kline_chunk_size(interval.value, query_start, query_end)
            for i in range(0, len(group_symbols), chunk_size):
                chunk_symbols = group_symbols[i : i + chunk_size]
                try:
                    bars = await self._provider.get_kline(
                        symbols=chunk_symbols,
                        interval=interval,
                        start=query_start,
                        end=query_end,
                    )
                except Exception as e:
                    # 提级 debug→warning(2026-07-29 观测盲区):chunk 失败应可见,
                    # 否则 8034 只全失败但日志只显示最终"同步完成"无人知晓
                    logger.warning(
                        f"API 查询失败 ({len(chunk_symbols)} 只, {query_start}~{query_end}): {e}"
                    )
                    failed_codes.extend(chunk_symbols)
                    progress.update(len(chunk_symbols))
                    continue

                if bars:
                    await self._store.save_kline(bars, interval)
                    total_synced += len(bars)

                    # 计算每个 symbol 的 max trade_date
                    for symbol, max_dt in self._compute_symbol_max_dates(bars).items():
                        symbol_max_dates[symbol] = max_dt

                    # 覆盖度校验(2026-08-06 观测):SDK 对混合市场 code_list
                    # 静默丢 codes,返回 bars 只覆盖少数 symbol 却无异常 → 上层
                    # 把整 chunk 记成功。日线增量窗口几乎每只有数据,覆盖率
                    # 异常低(<10%)说明 SDK 丢 codes,必须可见。
                    covered = len({bar.symbol for bar in bars})
                    if covered < len(chunk_symbols) * 0.1:
                        logger.warning(
                            f"chunk 覆盖度异常: 返回 {len(bars)} 条只覆盖 "
                            f"{covered}/{len(chunk_symbols)} 只,窗口 "
                            f"{query_start}~{query_end} — SDK 可能静默丢 codes"
                        )

                    logger.debug(
                        f"批次 {query_start}~{query_end}，"
                        f"{len(chunk_symbols)} 只证券，{len(bars)} 条记录"
                    )
                # else: 空 API 响应不推进 last_sync_date (D-02)
                progress.update(len(chunk_symbols))

        progress.close()

        # 5. 更新 last_sync_date
        if symbol_max_dates:
            await self._store.set_last_sync_dates(symbol_max_dates, interval)

        success_count = len(symbols) - len(failed_codes)
        # 提级(2026-07-29 观测盲区):全失败/部分失败应可见,否则 retry_handler
        # 把"无异常"当成功即使 0 条入库(8/1 kline 8034 全失败却标 success)
        if success_count == 0 and len(symbols) > 0:
            logger.error(
                f"同步完成: {success_count}/{len(symbols)} 只成功, "
                f"{total_synced} 条记录, {len(failed_codes)} 只失败 — 全部失败!"
            )
        else:
            logger.info(
                f"同步完成: {success_count}/{len(symbols)} 只成功, "
                f"{total_synced} 条记录, {len(failed_codes)} 只失败"
            )
        if failed_codes:
            # 失败 symbol 列表提级 debug→warning(有失败就应可见)
            logger.warning(f"失败 {len(failed_codes)} 只: {failed_codes[:10]}")

        # AM 返空检测(2026-08-11 根治 + 2026-08-14 覆盖率补强 + 2026-08-18
        # 周期限定):仅 DAY 周期用「目标日期覆盖率」判据 — end_date=昨日交易日,
        # 数据应推进到 end_date,覆盖率 < 10% → raise(捕获全空 + 部分空:
        # 少量历史补数据混入,2026-08-13 案例 180 条旧股退市前数据)。
        # 长周期(week/month/season/year)周期线 trade_time 是周期首交易日
        # (周一/月初),end_date 是周期末日,`max_date >= end_date` 永不成立
        # 会误判(2026-08-15 kline_week W33:拉到 15442 条周线却判 0% 覆盖,
        # 重试 7 次浪费 7.5h)→ 长周期只查全空 + 窗口含交易日。
        # 仅在 symbols_needing_sync>0 时检测(避免「无 symbol 需同步」误判)。
        if symbols_needing_sync > 0:
            end_date = datetime.strptime(end[:8], "%Y%m%d").date()
            coverage_checked = False

            if interval == Interval.DAY:
                end_trading_days = await self._calendar_store.get_trading_days(
                    end_date, end_date
                )
                if end_trading_days:
                    # end 是交易日:检查目标日期覆盖率
                    symbols_at_end = sum(
                        1 for d in symbol_max_dates.values() if d >= end_date
                    )
                    coverage = symbols_at_end / symbols_needing_sync
                    if coverage < _EMPTY_RESPONSE_COVERAGE_THRESHOLD:
                        raise EmptyResponseError(
                            f"目标日期 {end} 是交易日但覆盖率仅 "
                            f"{coverage:.1%}"
                            f"({symbols_at_end}/{symbols_needing_sync}), "
                            f"total_synced={total_synced}, "
                            f"失败 {len(failed_codes)} 只 — AM 时段性返空或"
                            f"全 API 异常,需重试",
                            endpoint="get_kline",
                        )
                    logger.info(
                        f"目标日期 {end} 覆盖率 {coverage:.1%}"
                        f"({symbols_at_end}/{symbols_needing_sync})"
                    )
                    coverage_checked = True

            if not coverage_checked and total_synced == 0:
                # DAY+end 非交易日 / 长周期 + 全空:检查窗口是否含交易日
                # (节假日场景不误判)
                query_start_date = datetime.strptime(start[:8], "%Y%m%d").date()
                trading_days = await self._calendar_store.get_trading_days(
                    query_start_date, end_date
                )
                if trading_days:
                    raise EmptyResponseError(
                        f"同步窗口 {start}~{end} 含 {len(trading_days)} 个交易日"
                        f"但 0 条入库(需同步 {symbols_needing_sync} 只, "
                        f"失败 {len(failed_codes)} 只) — AM 时段性返空或全 API "
                        f"异常,需重试",
                        endpoint="get_kline",
                    )
                logger.info(
                    f"同步窗口 {start}~{end} 无交易日,0 条入库为正常(节假日)"
                )

        return SyncResult(
            total_symbols=len(symbols),
            success_count=success_count,
            synced_records=total_synced,
            failed_codes=failed_codes,
        )

    def _resolve_default_start(self, symbols: list[str]) -> str:
        """从配置读取默认开始日期."""
        from galaxy_core.shared_kernel.utils.config_loader import get_section

        section = get_section("kline")
        default = section.get("default_start_date", "20130101")
        if isinstance(default, str) and len(default) == 8 and default.isdigit():
            return default
        return "20130101"

    def _build_and_group_ranges(
        self,
        symbols: list[str],
        last_sync_dates: dict[str, date | None],
        start_dt: date,
        end_str: str,
    ) -> list[tuple[str, str, list[str]]]:
        """构建同步范围并按相同 (query_start, query_end) 分组.

        新 symbol（无 last_sync_date 记录）从 start-1 开始查询 (D-03)。
        已有记录的 symbol 从 last_sync_date+1 开始。
        query_start > query_end 时跳过。
        """
        ranges: list[tuple[str, str, str]] = []  # (query_start, query_end, symbol)

        for symbol in symbols:
            last = last_sync_dates.get(symbol)
            if last is None:
                # 新 symbol：从 start-1 开始 (D-03)
                last = start_dt - timedelta(days=1)
            query_start = (last + timedelta(days=1)).strftime("%Y%m%d")
            if query_start <= end_str:
                ranges.append((query_start, end_str, symbol))

        if not ranges:
            return []

        # 按 (query_start, query_end) 分组
        ranges.sort(key=lambda x: (x[0], x[1]))
        grouped: list[tuple[str, str, list[str]]] = []
        for (qs, qe), group in groupby(ranges, key=itemgetter(0, 1)):
            group_symbols = [r[2] for r in group]
            grouped.append((qs, qe, group_symbols))

        return grouped

    @staticmethod
    def _compute_symbol_max_dates(bars: list) -> dict[str, date]:
        """从返回的 KlineBar 列表中计算每个 symbol 的最大 trade_date."""
        from galaxy_core.shared_kernel.utils.constants import CST

        result: dict[str, date] = {}
        for bar in bars:
            trade_dt = bar.trade_time
            # aware datetime → 北京时区后取 date(避免 UTC 日界线偏移)
            bar_date = (
                trade_dt.astimezone(CST).date()
                if isinstance(trade_dt, datetime)
                else trade_dt
            )
            existing = result.get(bar.symbol)
            if existing is None or bar_date > existing:
                result[bar.symbol] = bar_date
        return result
