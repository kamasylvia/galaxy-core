"""资金流向同步任务 — akshare 1 + amazingdata 4 = 5 sync_type.

管理 5 个 sync_type(经 SyncStateManager 幂等门控,单种失败不阻断其余):

akshare 1(2026-06-19 范围修订:原 5 收敛为 1, 见 02-SCOPE-REVISION-REPORT.md):
- akshare_sector_fund_flow: 板块资金流(仅当日快照,日度累积建库)

amazingdata 4:
- long_hu_bang: 龙虎榜(单 code 循环)
- block_trading: 大宗交易(单 code 循环)
- margin_summary: 两融汇总(全市场汇总,无 code_list)
- margin_detail: 两融明细(单 code 循环 + dict[str, DataFrame] 处理)

单 code 循环严格串行(RESEARCH §A18/§C29 — API 不支持并发,全市场 5000 股 ~40min)。

架构(2026-06-26 重试修复 B2:编排/执行两层分离,对齐 kline/reference 模式):
- 编排层 _maybe_sync_*(today, *, force):is_synced 门控 + mark_running
  + sync_with_retry(执行层) + mark_success/mark_failed。单 sync 失败不阻断后续。
- 执行层 _sync_*(today, period_id):纯执行(取数/转换/save/last_sync 推进),
  失败 raise(异常传到 sync_with_retry 触发重试),不碰 state_manager。
"""

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from galaxy_core.application.scheduler.jobs._incremental_mixin import (
    IncrementalSyncMixin,
)
from galaxy_core.application.scheduler.retry_handler import sync_with_retry
from galaxy_core.application.scheduler.state_manager import SyncStateManager
from galaxy_core.database.services.adapters.akshare_store_adapter import (
    AkshareStoreAdapter,
)
from galaxy_core.database.services.adapters.fund_flow_store_adapter import (
    FundFlowStoreAdapter,
)
from galaxy_core.database.services.last_sync_date_store import LastSyncDateStore
from galaxy_core.domain.value_objects import (
    AkshareSectorFundFlow,
    BlockTrading,
    LongHuBang,
    MarginDetail,
    MarginSummary,
)
from galaxy_core.shared_kernel.exceptions.api import EmptyResponseError
from galaxy_core.shared_kernel.utils.chunking import (
    resolve_daily_chunk_size,
    resolve_fundflow_chunk_size,
)
from galaxy_core.shared_kernel.utils.config_loader import get_section
from galaxy_core.third_party.akshare.adapters.akshare_fund_flow_adapter import (
    AkshareFundFlowProviderAdapter,
)

logger = logging.getLogger(__name__)

# Phase 03 last_sync_date sync_type 常量(amazingdata 4 表 + akshare sector)
_SYNC_LONG_HU_BANG = "long_hu_bang"
_SYNC_BLOCK_TRADING = "block_trading"
_SYNC_MARGIN_SUMMARY = "margin_summary"
_SYNC_MARGIN_DETAIL = "margin_detail"
_SYNC_SECTOR_FUND_FLOW = "akshare_sector_fund_flow"

# 重试耗尽时的 error_message(对齐 reference/kline 模式)
_RETRIES_EXHAUSTED = "All retries exhausted"


class FundFlowSyncJob(IncrementalSyncMixin):
    """资金流向同步任务 — akshare + amazingdata 双 provider/store.

    构造注入 state_manager + 2 provider + 2 store + last_sync_store(Phase 03 增量)
    + reference_provider(per-symbol 表的 universe 来源)。

    架构(2026-06-26 B2):编排/执行两层分离。
    - run_daily/run_daily_force → _maybe_sync_*(编排,含 sync_with_retry)
    - _sync_*(执行,失败 raise)

    Phase 03(03-05):amazingdata 4 表增量走 last_sync_date 表
    (per-symbol scope_key=market_code;margin_summary 全局 None)。
    akshare sector_fund_flow 当日快照特殊处理(D-22:last != today 才拉)。
    """

    def __init__(
        self,
        state_manager: SyncStateManager,
        akshare_provider: AkshareFundFlowProviderAdapter,
        amazing_provider: Any,
        akshare_store: AkshareStoreAdapter,
        amazing_store: FundFlowStoreAdapter,
        last_sync_store: LastSyncDateStore,
        reference_provider: Any = None,
        db_manager: Any = None,
        calendar_store: Any = None,
    ) -> None:
        self._state = state_manager
        self._akshare_provider = akshare_provider
        self._amazing_provider = amazing_provider
        self._akshare_store = akshare_store
        self._amazing_store = amazing_store
        self._db_manager = db_manager
        self._last_sync_store = last_sync_store  # Phase 03 增量用
        # 交易日历(margin_detail 空结果熔断用,2026-09-09):判「昨日是否交易日」
        self._calendar_store = calendar_store
        # universe 来源:reference_provider.get_stock_list(security_type)
        # 取全沪深 A 股,供 long_hu_bang/block_trading/margin_detail 单 code 循环。
        # DI 注入(2026-06-25 修复:原漏注导致 per-symbol 三表永远 0 条)。
        self._reference_provider = reference_provider
        self._security_type = get_section("fundflow").get(
            "security_type", "EXTRA_STOCK_A_SH_SZ"
        )
        raw_cache = get_section("amazing_data").get("local_path", "./data/local_cache/")
        self._cache_dir = str(Path(raw_cache).resolve())
        if raw_cache.endswith("/"):
            self._cache_dir += "/"

    # ------------------------------------------------------------------
    # 日度入口(编排层分派)
    # ------------------------------------------------------------------
    async def run_daily(self, today: date, target: str = "all") -> None:
        """日度同步:按 target 分派 5 个 _maybe_sync_<X>(编排层).

        target choices(范围修订后): all / sector / longhu / block / margin。
        target='margin' 跑 summary + detail(2 个);其余单跑对应 _sync。
        单 sync 失败(重试耗尽)不阻断后续 sync(编排层隔离)。
        """
        if target in ("all", "sector"):
            await self._maybe_sync_sector(today)
        if target in ("all", "longhu"):
            await self._maybe_sync_long_hu_bang(today)
        if target in ("all", "block"):
            await self._maybe_sync_block_trading(today)
        if target in ("all", "margin"):
            await self._maybe_sync_margin_summary(today)
            await self._maybe_sync_margin_detail(today)

    async def run_daily_force(self, today: date, target: str = "all") -> None:
        """强制日度同步:绕过 is_synced,各 _maybe_sync_<X> 传 force=True.

        Per Phase 01 (CLI --force)。仍走状态机标记,避免 scheduler 重复跑。
        target choices(范围修订后): all / sector / longhu / block / margin。
        """
        if target in ("all", "sector"):
            await self._maybe_sync_sector(today, force=True)
        if target in ("all", "longhu"):
            await self._maybe_sync_long_hu_bang(today, force=True)
        if target in ("all", "block"):
            await self._maybe_sync_block_trading(today, force=True)
        if target in ("all", "margin"):
            await self._maybe_sync_margin_summary(today, force=True)
            await self._maybe_sync_margin_detail(today, force=True)

    # ------------------------------------------------------------------
    # 编排层 _maybe_sync_<X>(门控 + mark + sync_with_retry)
    # ------------------------------------------------------------------
    async def _maybe_sync_sector(
        self, today: date, *, force: bool = False
    ) -> None:
        """编排层:板块资金流(akshare). is_synced 门控 + 重试."""
        period_id = today.strftime("%Y%m%d")
        sync_type = _SYNC_SECTOR_FUND_FLOW
        if not force and await self._state.is_synced(sync_type, period_id):
            logger.info(f"{sync_type} {period_id} 已同步,跳过")
            return
        await self._state.mark_running(sync_type, period_id)
        success = await sync_with_retry(
            self._sync_sector_fund_flow, f"{sync_type} {period_id}", today, period_id
        )
        if success:
            await self._state.mark_success(sync_type, period_id)
        else:
            await self._state.mark_failed(sync_type, period_id, _RETRIES_EXHAUSTED)

    async def _maybe_sync_long_hu_bang(
        self, today: date, *, force: bool = False
    ) -> None:
        """编排层:龙虎榜. is_synced 门控 + 重试."""
        period_id = today.strftime("%Y%m%d")
        sync_type = _SYNC_LONG_HU_BANG
        if not force and await self._state.is_synced(sync_type, period_id):
            logger.info(f"{sync_type} {period_id} 已同步,跳过")
            return
        await self._state.mark_running(sync_type, period_id)
        success = await sync_with_retry(
            self._sync_long_hu_bang, f"{sync_type} {period_id}", today, period_id
        )
        if success:
            await self._state.mark_success(sync_type, period_id)
        else:
            await self._state.mark_failed(sync_type, period_id, _RETRIES_EXHAUSTED)

    async def _maybe_sync_block_trading(
        self, today: date, *, force: bool = False
    ) -> None:
        """编排层:大宗交易. is_synced 门控 + 重试."""
        period_id = today.strftime("%Y%m%d")
        sync_type = _SYNC_BLOCK_TRADING
        if not force and await self._state.is_synced(sync_type, period_id):
            logger.info(f"{sync_type} {period_id} 已同步,跳过")
            return
        await self._state.mark_running(sync_type, period_id)
        success = await sync_with_retry(
            self._sync_block_trading, f"{sync_type} {period_id}", today, period_id
        )
        if success:
            await self._state.mark_success(sync_type, period_id)
        else:
            await self._state.mark_failed(sync_type, period_id, _RETRIES_EXHAUSTED)

    async def _maybe_sync_margin_summary(
        self, today: date, *, force: bool = False
    ) -> None:
        """编排层:两融汇总(全局). is_synced 门控 + 重试."""
        period_id = today.strftime("%Y%m%d")
        sync_type = _SYNC_MARGIN_SUMMARY
        if not force and await self._state.is_synced(sync_type, period_id):
            logger.info(f"{sync_type} {period_id} 已同步,跳过")
            return
        await self._state.mark_running(sync_type, period_id)
        success = await sync_with_retry(
            self._sync_margin_summary, f"{sync_type} {period_id}", today, period_id
        )
        if success:
            await self._state.mark_success(sync_type, period_id)
        else:
            await self._state.mark_failed(sync_type, period_id, _RETRIES_EXHAUSTED)

    async def _maybe_sync_margin_detail(
        self, today: date, *, force: bool = False
    ) -> None:
        """编排层:两融明细(per-symbol). is_synced 门控 + 重试."""
        period_id = today.strftime("%Y%m%d")
        sync_type = _SYNC_MARGIN_DETAIL
        if not force and await self._state.is_synced(sync_type, period_id):
            logger.info(f"{sync_type} {period_id} 已同步,跳过")
            return
        await self._state.mark_running(sync_type, period_id)
        success = await sync_with_retry(
            self._sync_margin_detail, f"{sync_type} {period_id}", today, period_id
        )
        if success:
            await self._state.mark_success(sync_type, period_id)
        else:
            await self._state.mark_failed(sync_type, period_id, _RETRIES_EXHAUSTED)

    # ------------------------------------------------------------------
    # 执行层 _sync_<X>(纯执行,失败 raise,不碰 state_manager)
    # ------------------------------------------------------------------
    async def _sync_sector_fund_flow(self, today: date, period_id: str) -> None:
        """执行层:板块资金流(仅当日快照). RESEARCH §A10 — scheduler 日度累积建库.

        Phase 03 D-22 特殊处理:akshare stock_sector_fund_flow_rank 仅返当日快照,
        无历史日期参数。每次拉当日,用 sync_state 幂等防重复;成功后
        set_last_sync_date(today)(用于检测 scheduler 宕机缺口,但 API 无法回补历史)。
        失败 raise(传到 sync_with_retry 触发重试)。
        """
        sync_type = _SYNC_SECTOR_FUND_FLOW
        df = await self._akshare_provider.get_sector_fund_flow()
        if df is None or df.empty:
            logger.info(f"{sync_type} 返回空数据")
            return
        records = self._df_to_sector_records(df, period_id)
        saved = await self._akshare_store.save_sector_fund_flow(records)
        # Phase 03 D-22:有记录才推进 last_sync_date(空响应不推进)
        if records:
            await self._last_sync_store.set_last_sync_date(
                _SYNC_SECTOR_FUND_FLOW, None, today
            )
        logger.info(f"{sync_type} 同步完成: {saved} 条板块资金流记录")

    async def _sync_long_hu_bang(self, today: date, period_id: str) -> None:
        """执行层:龙虎榜. 同窗口批量 + 分 chunk(500/批).

        Phase 03(03-05):per-symbol 增量,scope_key=market_code。
        每 code 独立 last_sync_date,空表首启从 DEFAULT_FIRST_SYNC_DATE 拉全历史。
        空表首启场景所有 code 窗口相同,自动批量化(5204只一次被 API 拒,故分 chunk);
        正常增量各 code 窗口分散,自然退化为单只。详见 AGENTS.md 2026-07-04。
        失败 raise(传到 sync_with_retry 触发重试)。
        """
        sync_type = _SYNC_LONG_HU_BANG
        universe = await self._get_amazing_universe()
        records = await self._fetch_per_symbol_batched(
            sync_type, universe, today, "get_long_hu_bang", is_dict_return=False
        )
        saved = await self._amazing_store.save_long_hu_bang(records)
        await self._advance_last_sync_dates(
            sync_type, records, date_attr="trade_date"
        )
        logger.info(f"{sync_type} 同步完成: {saved} 条龙虎榜记录")

    async def _sync_block_trading(self, today: date, period_id: str) -> None:
        """执行层:大宗交易. 同窗口批量 + 分 chunk. Phase 03 per-symbol 增量.

        详见 _sync_long_hu_bang docstring 的批量策略。
        失败 raise(传到 sync_with_retry 触发重试)。
        """
        sync_type = _SYNC_BLOCK_TRADING
        universe = await self._get_amazing_universe()
        records = await self._fetch_per_symbol_batched(
            sync_type, universe, today, "get_block_trading", is_dict_return=False
        )
        saved = await self._amazing_store.save_block_trading(records)
        await self._advance_last_sync_dates(
            sync_type, records, date_attr="trade_date"
        )
        logger.info(f"{sync_type} 同步完成: {saved} 条大宗交易记录")

    async def _sync_margin_summary(self, today: date, period_id: str) -> None:
        """执行层:两融汇总(全市场,无 code_list). 单次 get_margin_summary.

        Phase 03(03-05):全局增量,scope_key=None。
        失败 raise(传到 sync_with_retry 触发重试)。
        """
        sync_type = _SYNC_MARGIN_SUMMARY
        begin, end = await self._resolve_incremental_range(
            sync_type, scope_key=None, today=today
        )
        df = await self._amazing_provider.get_margin_summary(
            local_path=self._cache_dir,
            is_local=False,
            begin_date=begin,
            end_date=end,
        )
        if df is None or df.empty:
            logger.info(f"{sync_type} 返回空数据")
            return
        records = self._df_to_margin_summary_records(df)
        saved = await self._amazing_store.save_margin_summary(records)
        # Phase 03 D-08:全局表单条 last_sync_date(scope_key=None)
        await self._advance_last_sync_date_global(
            sync_type, records, date_attr="trade_date"
        )
        logger.info(f"{sync_type} 同步完成: {saved} 条两融汇总记录")

    async def _sync_margin_detail(self, today: date, period_id: str) -> None:
        """执行层:两融明细. 同窗口批量 + 分 chunk + dict[str, DataFrame] 处理.

        Phase 03(03-05):per-symbol 增量,scope_key=market_code。
        详见 _sync_long_hu_bang docstring 的批量策略。
        失败 raise(传到 sync_with_retry 触发重试)。

        空结果熔断(2026-09-09):AM 端 margin_detail T+1 数据发布时刻不稳定
        (实证 9/2 14:41 可查、9/9 15:27 仍空),12:00 链常拉空;且窗口仅
        当日有效(T+1 之后拉不到,2026-09-08 定因)。0 条若标成功 = 当日
        永久错过。故昨日是交易日且拉空 → raise 进重试;昨日非交易日无新
        数据属正常,0 条直接成功。
        """
        sync_type = _SYNC_MARGIN_DETAIL
        universe = await self._get_amazing_universe()
        records = await self._fetch_per_symbol_batched(
            sync_type, universe, today, "get_margin_detail", is_dict_return=True
        )
        if not records:
            yesterday = today - timedelta(days=1)
            trading_days = (
                await self._calendar_store.get_trading_days(yesterday, yesterday)
                if self._calendar_store is not None
                else [yesterday]
            )
            if trading_days:
                raise EmptyResponseError(
                    f"两融明细 0 条且 {yesterday} 是交易日 — AM 端 T+1 数据"
                    f"未发布或接口返空,窗口仅当日有效,需重试(period={period_id})",
                    endpoint="get_margin_detail",
                )
            logger.info(f"{sync_type} {yesterday} 非交易日,0 条属正常")
        saved = await self._amazing_store.save_margin_detail(records)
        await self._advance_last_sync_dates(
            sync_type, records, date_attr="trade_date"
        )
        logger.info(f"{sync_type} 同步完成: {saved} 条两融明细记录")

    # ------------------------------------------------------------------
    # 私有辅助
    # ------------------------------------------------------------------
    async def _fetch_per_symbol_batched(
        self,
        sync_type: str,
        universe: list[str],
        today: date,
        api_method_name: str,
        is_dict_return: bool = False,
    ) -> list:
        """批量拉取 per-symbol 数据(同窗口合并 + 分 chunk)。

        背景:三表(long_hu_bang/block_trading/margin_detail)原为单只循环,
        空表首启时所有 code 窗口相同(begin=DEFAULT_FIRST_SYNC_DATE, end=today),
        可批量。但整组 5204 只一次传 API 会被拒(AGENTS.md 2026-07-04 实测),
        故分 chunk。chunk_size 走统一分批工具 resolve_daily_chunk_size()
        (默认 api_chunk_size=500,可配置)。

        策略:
        1. 预查所有 code 的 (begin, end) 窗口
        2. 按 (begin, end) 分组 —— 同窗口合并
        3. 每组内分 chunk 批量调 API
        4. 正常增量(各 code 窗口分散)自然退化为小组,兼容旧行为

        返回 records list(调用方负责 save + advance_last_sync_date)。
        """
        # 1. 预查窗口并分组
        # 优化:先判断是否空表首启。空表时所有 code 窗口相同(begin=默认,end=today),
        # 跳过 5500 次逐个 DB 查询(省 ~10min)。
        from galaxy_core.shared_kernel.utils.constants import DEFAULT_FIRST_SYNC_DATE

        # CRITICAL:不能用 get_last_sync_date(sync_type, None) 判空——per-symbol 表
        # (long_hu_bang/block_trading/margin_detail)的 scope_key 是 code,scope=None
        # 恒返回 None,会被误判为空表首启 → begin=20130101 的 13 年全窗口 → API 处理
        # 海量数据挂起。改为查 universe 首个 code 的 per-code 记录:空表首启时它也
        # 为 None,非空表时为日期。(2026-07-14 修复,导致 fundflow 补数无限卡死)
        probe = universe[0] if universe else None
        is_empty = (
            probe is None
            or await self._last_sync_store.get_last_sync_date(sync_type, probe) is None
        )
        window_groups: dict[tuple[int, int], list[str]] = {}
        if is_empty:
            # 空表首启:所有 code 统一默认窗口(跳过逐个查询)
            begin = DEFAULT_FIRST_SYNC_DATE
            end = int(today.strftime("%Y%m%d"))
            window_groups[(begin, end)] = list(universe)
        else:
            # 非空表:批量查 last_sync_date + 月桶对齐(2026-08-01 优化)
            # 原 5200 次逐个 _resolve_incremental_range → 几千个精确窗口组,
            # 每组单独调 SDK → 调用爆炸 + 碎片化窗口 SDK 慢(8/1 long_hu_bang
            # 5172 个 code 分散 2013~2026 各月,几千组 × SDK 调用耗时 5h+)。
            # 改为:单 SQL 批量查 + begin 对齐到月初(同一月的 code 合并)。
            # 多查几天数据无副作用(UPSERT 幂等),组数从几千降到 ~42 个月桶。
            last_dates = await self._last_sync_store.get_last_sync_dates_batch(
                sync_type, list(universe)
            )
            for code in universe:
                last = last_dates.get(code)
                if last is not None:
                    # 月桶对齐:begin 对齐到 last 所在月的下一个月初
                    # (last 在 2026-07 → begin=20260801,覆盖 8 月至今)
                    begin_year = last.year + (last.month // 12)
                    begin_month = (last.month % 12) + 1
                    begin = begin_year * 10000 + begin_month * 100 + 1
                else:
                    # 无记录的 code 用默认全窗口(与空表首启一致)
                    begin = DEFAULT_FIRST_SYNC_DATE
                end = int(today.strftime("%Y%m%d"))
                key = (begin, end)
                window_groups.setdefault(key, []).append(code)
            logger.info(
                f"{sync_type} 窗口分组: {len(universe)} 只 → "
                f"{len(window_groups)} 组(月桶对齐)"
            )

        api_method = getattr(self._amazing_provider, api_method_name)
        records: list = []

        # 2. 每组内分 chunk 批量(整窗口传,不分段)
        # 分段曾用于规避 SDK 大窗口 sleep,但根因(universe 获取)已修(get_hist_code_list),
        # 分段反而加剧 SDK 累积限流(45 次调用 vs 1 次)。整窗口 + chunk=100 更稳定。
        for (begin, end), codes in window_groups.items():
            chunk_size = resolve_fundflow_chunk_size()

            if len(codes) <= 1:
                batch_iter = [[c] for c in codes]
            else:
                batch_iter = [
                    codes[i : i + chunk_size]
                    for i in range(0, len(codes), chunk_size)
                ]

            for batch_codes in batch_iter:
                try:
                    data = await api_method(
                        code_list=batch_codes,
                        local_path=self._cache_dir,
                        is_local=False,
                        begin_date=begin,
                        end_date=end,
                    )
                except Exception as e:
                    logger.warning(
                        f"{sync_type} 批量 {batch_codes[0]}~{batch_codes[-1]} "
                        f"({len(batch_codes)}只, {begin}~{end}) 失败: "
                        f"{type(e).__name__}: {e},跳过"
                    )
                    continue

                if is_dict_return:
                    # margin_detail: dict[str, DataFrame]
                    if not data:
                        continue
                    for code_key, df in data.items():
                        if df is None or df.empty:
                            continue
                        records.extend(
                            self._df_to_margin_detail_records(df, code_key)
                        )
                else:
                    # long_hu_bang/block_trading: DataFrame
                    if data is None or data.empty:
                        continue
                    conv = {
                        "long_hu_bang": self._df_to_long_hu_bang_records,
                        "block_trading": self._df_to_block_trading_records,
                    }.get(sync_type)
                    if conv is None:
                        continue
                    records.extend(conv(data))

        return records

    async def _get_amazing_universe(self) -> list[str]:
        """AmazingData universe: 返回 list[code] (如 600000.SH).

        走 resolve_universe_with_fallback:
        - SDK 区间 [T-30, T-1] union 多日 pkl(降低单日联网失败影响)
        - SDK 返空时 fallback 从 stock_basic 表读 codes
        (见 AGENTS.md 2026-07-28 Bug 2)
        """
        if self._reference_provider is None:
            return []

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
        result = await resolve_universe_with_fallback(
            reference_provider=self._reference_provider,
            db_manager=self._db_manager,
            security_type=self._security_type,
            end_date=yesterday,
            local_path=local_path,
        )
        return list(result) if result else []

    @staticmethod
    def _split_window_into_segments(
        begin: int, end: int, max_months: int = 3
    ) -> list[tuple[int, int]]:
        """将大窗口拆成 ≤max_months 个月的小段。

        SDK 对 fundflow 三表的大窗口(>3 月)请求触发内部 sleep 循环(hrtimer_nanosleep),
        导致进程假死。拆成小段后 SDK 正常(实测 3 月 100 只 = 2.2s)。

        Args:
            begin: 起始 YYYYMMDD int
            end: 结束 YYYYMMDD int
            max_months: 每段最大月数(默认 3)

        Returns:
            [(seg_begin, seg_end), ...] 的 YYYYMMDD int 列表
        """
        from datetime import date as dt, timedelta

        try:
            b = dt(begin // 10000, (begin // 100) % 100, begin % 100)
            e = dt(end // 10000, (end // 100) % 100, end % 100)
        except ValueError:
            return [(begin, end)]

        segments: list[tuple[int, int]] = []
        cur = b
        while cur < e:
            # 加 max_months 个月
            month = cur.month + max_months
            year = cur.year + (month - 1) // 12
            month = (month - 1) % 12 + 1
            next_cur = dt(year, month, 1)
            if next_cur > e:
                next_cur = e + timedelta(days=1)
            seg_end = min(next_cur - timedelta(days=1), e)
            seg_begin_int = int(cur.strftime("%Y%m%d"))
            seg_end_int = int(seg_end.strftime("%Y%m%d"))
            segments.append((seg_begin_int, seg_end_int))
            cur = next_cur

        return segments if segments else [(begin, end)]

    # ------------------------------------------------------------------
    # Phase 03:last_sync_date 推进辅助
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_yyyymmdd(value: str) -> date | None:
        """YYYYMMDD 或 YYYY-MM-DD str → date(失败返 None).

        AmazingData API trade_date 字段有两种格式:
        - 8 char YYYYMMDD(部分接口)
        - 10 char YYYY-MM-DD(long_hu_bang/block_trading/margin_* 等)
        """
        if not value:
            return None
        # YYYY-MM-DD
        if len(value) == 10 and value[4] == "-" and value[7] == "-":
            try:
                return date(int(value[:4]), int(value[5:7]), int(value[8:10]))
            except (ValueError, IndexError):
                return None
        # YYYYMMDD
        if len(value) == 8:
            try:
                return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
            except (ValueError, IndexError):
                return None
        return None

    async def _advance_last_sync_dates(
        self,
        sync_type: str,
        records: list,
        date_attr: str = "trade_date",
        scope_attr: str = "market_code",
    ) -> None:
        """per-symbol 表推进 last_sync_date:按 scope_attr 分组,每组取 MAX date。

        D-08:records 空 → 不调 set(空响应不推进)。
        records trade_date 是 str YYYYMMDD,parse 为 date。
        """
        if not records:
            return
        # 按 scope_key 分组 → MAX date
        per_scope: dict[str, date] = {}
        for r in records:
            scope = getattr(r, scope_attr, None)
            td_str = getattr(r, date_attr, None)
            if scope is None or td_str is None:
                continue
            td = self._parse_yyyymmdd(td_str)
            if td is None:
                continue
            if scope not in per_scope or td > per_scope[scope]:
                per_scope[scope] = td
        for scope, max_date in per_scope.items():
            await self._last_sync_store.set_last_sync_date(sync_type, scope, max_date)

    async def _advance_last_sync_date_global(
        self,
        sync_type: str,
        records: list,
        date_attr: str = "trade_date",
    ) -> None:
        """全局表(margin_summary)推进 last_sync_date:单条 scope_key=None。

        D-08:records 空 → 不调 set。
        """
        if not records:
            return
        max_str = max(
            (getattr(r, date_attr, None) for r in records),
            key=lambda x: x or "",
            default=None,
        )
        max_date = self._parse_yyyymmdd(max_str) if max_str else None
        if max_date is not None:
            await self._last_sync_store.set_last_sync_date(sync_type, None, max_date)

    # ------------------------------------------------------------------
    # DataFrame → 值对象转换
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_str(value: Any) -> str | None:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        result = str(value)
        if result.lower() in ("nan", "none", "nat", ""):
            return None
        return result

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        try:
            result = float(value)
            return None if pd.isna(result) else result
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @classmethod
    def _df_to_sector_records(
        cls, df: pd.DataFrame, trade_date: str
    ) -> list[AkshareSectorFundFlow]:
        """板块资金流 df → VO. akshare 中文列映射.

        akshare stock_sector_fund_flow_rank 列(中文):名称/今日涨跌幅/主力净流入净额/
        主力净流入净占比/超大单净流入净额/超大单净流入净占比/大单.../中单.../小单.../今日主力净流入最大股
        """
        records: list[AkshareSectorFundFlow] = []
        for _, row in df.iterrows():
            sector_name = cls._safe_str(row.get("名称"))
            if sector_name is None:
                continue
            sector_type = cls._safe_str(row.get("板块类型")) or "行业"
            records.append(AkshareSectorFundFlow(
                trade_date=trade_date,
                sector_type=sector_type,
                sector_name=sector_name,
                main_net_amount=cls._safe_float(row.get("主力净流入-净额")),
                main_net_pct=cls._safe_float(row.get("主力净流入-净占比")),
                super_large_net_amount=cls._safe_float(row.get("超大单类目-净额")),
                super_large_net_pct=cls._safe_float(row.get("超大单类目-净占比")),
                large_net_amount=cls._safe_float(row.get("大单类目-净额")),
                large_net_pct=cls._safe_float(row.get("大单类目-净占比")),
                medium_net_amount=cls._safe_float(row.get("中单类目-净额")),
                medium_net_pct=cls._safe_float(row.get("中单类目-净占比")),
                small_net_amount=cls._safe_float(row.get("小单类目-净额")),
                small_net_pct=cls._safe_float(row.get("小单类目-净占比")),
                top_stock=cls._safe_str(row.get("今日主力净流入最大股")),
            ))
        return records

    @classmethod
    def _df_to_long_hu_bang_records(cls, df: pd.DataFrame) -> list[LongHuBang]:
        """龙虎榜 df → VO. AmazingData 大写列 → snake_case."""
        df_reset = df.reset_index() if "MARKET_CODE" not in df.columns else df
        records: list[LongHuBang] = []
        for _, row in df_reset.iterrows():
            market_code = cls._safe_str(row.get("MARKET_CODE"))
            trade_date = cls._safe_str(row.get("TRADE_DATE"))
            trader_name = cls._safe_str(row.get("TRADER_NAME"))
            flow_mark = cls._safe_int(row.get("FLOW_MARK"))
            if not market_code or trade_date is None or not trader_name or flow_mark is None:
                continue
            records.append(LongHuBang(
                market_code=market_code,
                trade_date=trade_date,
                security_name=cls._safe_str(row.get("SECURITY_NAME")),
                reason_type=cls._safe_str(row.get("REASON_TYPE")),
                reason_type_name=cls._safe_str(row.get("REASON_TYPE_NAME")),
                change_range=cls._safe_float(row.get("CHANGE_RANGE")),
                trader_name=trader_name,
                flow_mark=flow_mark,
                buy_amount=cls._safe_float(row.get("BUY_AMOUNT")),
                sell_amount=cls._safe_float(row.get("SELL_AMOUNT")),
                total_amount=cls._safe_float(row.get("TOTAL_AMOUNT")),
                total_volume=cls._safe_float(row.get("TOTAL_VOLUME")),
            ))
        return records

    @classmethod
    def _df_to_block_trading_records(cls, df: pd.DataFrame) -> list[BlockTrading]:
        """大宗交易 df → VO. b_ 前缀沿用 API 原始字段名 snake_case 化."""
        df_reset = df.reset_index() if "MARKET_CODE" not in df.columns else df
        records: list[BlockTrading] = []
        for _, row in df_reset.iterrows():
            market_code = cls._safe_str(row.get("MARKET_CODE"))
            trade_date = cls._safe_str(row.get("TRADE_DATE"))
            buyer = cls._safe_str(row.get("B_BUYER_NAME"))
            seller = cls._safe_str(row.get("B_SELLER_NAME"))
            if not market_code or trade_date is None or not buyer or not seller:
                continue
            records.append(BlockTrading(
                market_code=market_code,
                trade_date=trade_date,
                b_share_price=cls._safe_float(row.get("B_SHARE_PRICE")),
                b_share_volume=cls._safe_float(row.get("B_SHARE_VOLUME")),
                b_frequency=cls._safe_int(row.get("B_FREQUENCY")),
                block_avg_volume=cls._safe_float(row.get("BLOCK_AVG_VOLUME")),
                b_share_amount=cls._safe_float(row.get("B_SHARE_AMOUNT")),
                b_buyer_name=buyer,
                b_seller_name=seller,
            ))
        return records

    @classmethod
    def _df_to_margin_summary_records(cls, df: pd.DataFrame) -> list[MarginSummary]:
        """两融汇总 df → VO. 全市场每日 1 行汇总,大写列."""
        df_reset = df.reset_index() if "TRADE_DATE" not in df.columns else df
        records: list[MarginSummary] = []
        for _, row in df_reset.iterrows():
            trade_date = cls._safe_str(row.get("TRADE_DATE"))
            if trade_date is None:
                continue
            records.append(MarginSummary(
                trade_date=trade_date,
                sum_borrow_money_balance=cls._safe_float(
                    row.get("SUM_BORROW_MONEY_BALANCE")
                ),
                sum_purch_with_borrow_money=cls._safe_float(
                    row.get("SUM_PURCH_WITH_BORROW_MONEY")
                ),
                sum_repayment_of_borrow_money=cls._safe_float(
                    row.get("SUM_REPAYMENT_OF_BORROW_MONEY")
                ),
                sum_sec_lending_balance=cls._safe_float(
                    row.get("SUM_SEC_LENDING_BALANCE")
                ),
                sum_sales_of_borrowed_sec=cls._safe_float(
                    row.get("SUM_SALES_OF_BORROWED_SEC")
                ),
                sum_margin_trade_balance=cls._safe_float(
                    row.get("SUM_MARGIN_TRADE_BALANCE")
                ),
            ))
        return records

    @classmethod
    def _df_to_margin_detail_records(
        cls, df: pd.DataFrame, market_code: str
    ) -> list[MarginDetail]:
        """两融明细 df → VO. dict value 行结构,大写列 → snake."""
        df_reset = df.reset_index() if "TRADE_DATE" not in df.columns else df
        records: list[MarginDetail] = []
        for _, row in df_reset.iterrows():
            trade_date = cls._safe_str(row.get("TRADE_DATE"))
            if trade_date is None:
                continue
            # market_code 优先取 df 列,fallback 传入的 code
            mc = cls._safe_str(row.get("MARKET_CODE")) or market_code
            records.append(MarginDetail(
                market_code=mc,
                trade_date=trade_date,
                security_name=cls._safe_str(row.get("SECURITY_NAME")),
                borrow_money_balance=cls._safe_float(row.get("BORROW_MONEY_BALANCE")),
                purch_with_borrow_money=cls._safe_float(
                    row.get("PURCH_WITH_BORROW_MONEY")
                ),
                repayment_of_borrow_money=cls._safe_float(
                    row.get("REPAYMENT_OF_BORROW_MONEY")
                ),
                sec_lending_balance=cls._safe_float(row.get("SEC_LENDING_BALANCE")),
                sales_of_borrowed_sec=cls._safe_float(row.get("SALES_OF_BORROWED_SEC")),
                repayment_of_borrow_sec=cls._safe_float(
                    row.get("REPAYMENT_OF_BORROW_SEC")
                ),
                sec_lending_balance_vol=cls._safe_float(
                    row.get("SEC_LENDING_BALANCE_VOL")
                ),
                margin_trade_balance=cls._safe_float(row.get("MARGIN_TRADE_BALANCE")),
            ))
        return records
