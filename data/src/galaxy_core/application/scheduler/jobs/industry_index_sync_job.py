"""行业指数数据同步任务.

管理 4 个行业指数 API:
- industry_base_info: 月度同步（纯目录数据），挂 dimensions 链
- industry_constituent: 周度同步（慢变维度），挂 dimensions 链
- industry_weight: 日度 T+1 同步，挂 daily 链
- industry_daily: 日度 T+1 同步（行业指数唯一行情源），挂 daily 链

每个数据类型独立管理 SyncStateManager 状态，单种失败不阻断其余。

Phase 03(03-04):industry_weight 增量窗口改用 last_sync_date 表
(_resolve_incremental_range, scope_key=None 全局),消除固定 7 天反模式。
industry_daily 仍走 per-code _resolve_daily_range(已正确,不改)。

架构(2026-07-17 编排/执行两层分离,对齐 fundflow/kline 模式):
- 编排层 _maybe_sync_*(today, *, force):is_synced 门控 + mark_running
  + sync_with_retry(执行层) + mark_success/mark_failed。单 sync 失败不阻断后续。
- 执行层 _sync_*(today, period_id) -> int:纯执行(取数/转换/save/last_sync 推进),
  返回 saved count(仅日志价值,编排层不透传到 mark_success —— sync_with_retry
  返 bool 吞掉返回值,与 fundflow AGENTS.md 2026-06-26 既定模式一致,
  records_synced 降级为 0)。失败 raise(异常传到 sync_with_retry 触发重试),
  不碰 state_manager。

2026-07-17 修复:旧版 industry_daily 等 4 方法静默 false-success
(chunk API 异常 except 吞 + 全失败仍 mark_success(0) + 不接 sync_with_retry),
industry_daily 连续多日 0 条无人告警。改为编排/执行两层分离 + 接 retry。
"""

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from galaxy_core.application.scheduler.jobs._incremental_mixin import (
    IncrementalSyncMixin,
)
from galaxy_core.application.scheduler.retry_handler import sync_with_retry
from galaxy_core.application.scheduler.state_manager import SyncStateManager
from galaxy_core.database.services.last_sync_date_store import LastSyncDateStore
from galaxy_core.domain.ports.industry_index_provider import IndustryIndexProviderPort
from galaxy_core.domain.ports.industry_index_store import IndustryIndexStorePort
from galaxy_core.domain.value_objects import (
    IndustryBaseInfo,
    IndustryConstituent,
    IndustryDaily,
    IndustryWeight,
)
from galaxy_core.shared_kernel.exceptions.api import EmptyResponseError
from galaxy_core.shared_kernel.utils.chunking import (
    resolve_daily_chunk_size,
    resolve_weight_chunk_size,
)
from galaxy_core.shared_kernel.utils.config_loader import get_section

logger = logging.getLogger(__name__)

# Phase 03:industry_weight 增量维度(全局,所有行业指数共用窗口)
_INDUSTRY_WEIGHT_SYNC_TYPE = "industry_weight"

# 重试耗尽时的 error_message(对齐 fundflow/kline 模式)
_RETRIES_EXHAUSTED = "All retries exhausted"

# AM SDK get_industry_daily 批量安全上限(2026-08-27 探针矩阵实测):
# >20 codes 或 >25 自然日窗口的请求会静默挂死(SDK 线程无响应且不可取消)。
INDUSTRY_DAILY_CODE_CAP = 20

# industry_daily 覆盖率熔断阈值(2026-09-11):实际入库行数 < 预期(窗口内
# 截至昨日的交易日数 × 行业代码数)× 此值 → raise 触发重试/晚间补拉。
# 0.8 留容差(个别指数长期无行情);涓流发布(如 38/414)会命中熔断。
INDUSTRY_DAILY_COVERAGE_THRESHOLD = 0.8
INDUSTRY_DAILY_WINDOW_DAYS = 25


def _split_window(begin: int, end: int) -> list[tuple[int, int]]:
    """[begin, end] YYYYMMDD 闭区间按自然日切段,每段 ≤ WINDOW_DAYS 天(升序)."""
    from datetime import date as _date

    def _to_date(v: int) -> _date:
        return _date(v // 10000, v // 100 % 100, v % 100)

    def _to_int(d: _date) -> int:
        return d.year * 10000 + d.month * 100 + d.day

    d0, d1 = _to_date(begin), _to_date(end)
    segs: list[tuple[int, int]] = []
    cur = d0
    while cur <= d1:
        seg_end = min(cur + timedelta(days=INDUSTRY_DAILY_WINDOW_DAYS - 1), d1)
        segs.append((_to_int(cur), _to_int(seg_end)))
        cur = seg_end + timedelta(days=1)
    return segs or [(begin, end)]


class IndustryIndexSyncJob(IncrementalSyncMixin):
    """行业指数数据同步任务（基本信息/成分股维度 + 权重/日行情日度）."""

    def __init__(
        self,
        state_manager: SyncStateManager,
        provider: IndustryIndexProviderPort,
        store: IndustryIndexStorePort,
        last_sync_store: LastSyncDateStore,
        calendar_store: Any = None,
    ) -> None:
        self._state = state_manager
        self._provider = provider
        self._store = store
        self._last_sync_store = last_sync_store  # Phase 03 增量用
        # 交易日历(industry_daily 空结果熔断用,2026-09-11):判「昨日是否交易日」
        self._calendar_store = calendar_store
        self._config = get_section("index")
        raw_cache = get_section("amazing_data").get("local_path", "./data/local_cache/")
        self._cache_dir = str(Path(raw_cache).resolve())
        if raw_cache.endswith("/"):
            self._cache_dir += "/"

    # ------------------------------------------------------------------
    # 日度入口（行情/权重，紧跟 K线 day 之后）
    # ------------------------------------------------------------------
    async def run_daily(self, today: date) -> None:
        """日度同步：行业指数日行情 + 行业指数日权重.

        sync_type 分别为 industry_daily / industry_weight, period_id=YYYYMMDD.
        两者独立管理状态，互不阻断。
        """
        await self._maybe_sync_industry_daily(today)
        await self._maybe_sync_industry_weight(today)

    async def run_daily_force(self, today: date) -> None:
        """强制日度同步：绕过 is_synced，两个 sync_type 都强制.

        Per Phase 01 (manual CLI --force)。仍走状态标记，避免 scheduler 重复跑。
        """
        await self._maybe_sync_industry_daily(today, force=True)
        await self._maybe_sync_industry_weight(today, force=True)

    # ------------------------------------------------------------------
    # 编排层 _maybe_sync_*（门控 + mark + sync_with_retry）
    # ------------------------------------------------------------------
    async def _maybe_sync_industry_daily(
        self, today: date, *, force: bool = False
    ) -> None:
        """编排层:行业指数日行情. is_synced 门控 + 重试."""
        period_id = today.strftime("%Y%m%d")
        sync_type = "industry_daily"
        if not force and await self._state.is_synced(sync_type, period_id):
            logger.info(f"{sync_type} {period_id} 已同步,跳过")
            return
        await self._state.mark_running(sync_type, period_id)
        success = await sync_with_retry(
            self._sync_industry_daily, f"{sync_type} {period_id}", today, period_id
        )
        # records_synced 由执行层 logger 体现(对齐 fundflow 模式,mark_success 不带 count)
        if success:
            await self._state.mark_success(sync_type, period_id)
        else:
            await self._state.mark_failed(sync_type, period_id, _RETRIES_EXHAUSTED)

    async def _maybe_sync_industry_weight(
        self, today: date, *, force: bool = False
    ) -> None:
        """编排层:行业指数日权重. is_synced 门控 + 重试."""
        period_id = today.strftime("%Y%m%d")
        sync_type = "industry_weight"
        if not force and await self._state.is_synced(sync_type, period_id):
            logger.info(f"{sync_type} {period_id} 已同步,跳过")
            return
        await self._state.mark_running(sync_type, period_id)
        success = await sync_with_retry(
            self._sync_industry_weight, f"{sync_type} {period_id}", today, period_id
        )
        if success:
            await self._state.mark_success(sync_type, period_id)
        else:
            await self._state.mark_failed(sync_type, period_id, _RETRIES_EXHAUSTED)

    # ------------------------------------------------------------------
    # 执行层 _sync_*（纯执行,失败 raise,返回 saved count）
    # ------------------------------------------------------------------
    async def _sync_industry_daily(self, today: date, period_id: str) -> int:
        """执行层:行业指数日行情. 分 chunk 调 API.

        单 chunk 失败 try/except 容错(warning 级,不阻断其余 chunk),
        但**全 chunk 失败** raise RuntimeError 触发 sync_with_retry 重试。
        codes 空 raise(provider 故障,不能静默 mark_success(0))。
        API 返空 df(真无数据)仍 return 0(非故障,正常交易日可能无新数据)。

        Returns:
            saved count(入库行数)。
        """
        codes = await self._provider.get_industry_index_codes(self._cache_dir)
        if not codes:
            raise RuntimeError(
                "未获取到行业指数代码列表(provider 故障或 base_info 缓存缺失)"
            )

        # 增量:从最后同步日期的次日到今天
        begin_date, end_date = await self._resolve_daily_range(codes[0], today)
        # 2026-08-27 修复:AM SDK get_industry_daily 对「大批 codes 或大响应体」
        # 静默挂死(不报错不返回,asyncio.wait_for 因 to_thread 线程不可取消也救不了),
        # 生产 chunk=100×48 天窗即此形态 → 每次同步 6 chunk 全空返 → 7/9 起断档。
        # 探针矩阵(2026-08-27):≤20 codes × ≤25 自然日稳定秒回(J1:20c×25d=432 行
        # 1.7s);100 codes 或 ~500+ 行请求一律挂死。绕过方案 = 双维限幅:
        # 每批 ≤INDUSTRY_DAILY_CODE_CAP 只、窗口按 INDUSTRY_DAILY_WINDOW_DAYS 自然日切段。
        chunk_size = min(
            resolve_daily_chunk_size(str(begin_date), str(end_date)),
            INDUSTRY_DAILY_CODE_CAP,
        )
        logger.info(
            f"industry_daily 开始: {len(codes)} 只, chunk_size={chunk_size}, "
            f"window={begin_date}~{end_date}"
        )
        records: list[IndustryDaily] = []
        failed_chunks = 0
        total_chunks = 0
        for seg_begin, seg_end in _split_window(begin_date, end_date):
            for i in range(0, len(codes), chunk_size):
                chunk = codes[i : i + chunk_size]
                total_chunks += 1
                try:
                    data = await self._provider.get_industry_daily(
                        chunk, self._cache_dir,
                        is_local=False, begin_date=seg_begin, end_date=seg_end,
                    )
                except Exception as e:
                    failed_chunks += 1
                    logger.warning(
                        f"industry_daily chunk 失败 ({len(chunk)} 只, "
                        f"{seg_begin}~{seg_end}): {e}"
                    )
                    continue
                for _index_code, df in data.items():
                    if df is None or df.empty:
                        continue
                    records.extend(self._df_to_daily_records(df, _index_code))

        if total_chunks > 0 and failed_chunks == total_chunks:
            raise RuntimeError(
                f"industry_daily 全部 {total_chunks} 个 chunk 失败,触发重试"
            )

        saved = await self._store.save_industry_daily(records)
        # 空结果/低覆盖率熔断(2026-09-11,margin_detail 同款):AM 端 T+1
        # 发布时刻不稳且涓流(9/9 实证 0→38→94/414 跨小时分批放行),0 条或
        # 显著低于预期标成功 = false-success 阻断当日后续补救(窗口当晚有效)。
        # 预期行数 = 窗口内(截至昨日)交易日数 × 行业代码数;昨日非交易日
        # (周末/节假日)无新数据属正常,不熔断。
        yesterday = today - timedelta(days=1)
        # begin_date 是 int(YYYYMMDD,_resolve_daily_range 返回),日历列已是
        # date(nocodb 形态)——必须转 date,否则 asyncpg 报 date >= integer
        begin_dt = date(begin_date // 10000, begin_date // 100 % 100, begin_date % 100)
        trading_days = (
            await self._calendar_store.get_trading_days(begin_dt, yesterday)
            if self._calendar_store is not None
            else [yesterday]
        )
        expected = len(codes) * len(trading_days)
        if saved < expected * INDUSTRY_DAILY_COVERAGE_THRESHOLD:
            if trading_days:
                raise EmptyResponseError(
                    f"industry_daily 仅 {saved} 行,低于预期 "
                    f"{expected}({len(trading_days)} 交易日 × {len(codes)} 只)的 "
                    f"{INDUSTRY_DAILY_COVERAGE_THRESHOLD:.0%} — AM 端 T+1 数据"
                    f"未发布完或接口返空,需重试(period={period_id})",
                    endpoint="get_industry_daily",
                )
            logger.info(
                f"industry_daily 昨日 {yesterday} 非交易日,{saved} 条属正常"
            )
        if saved == 0:
            logger.warning(
                f"industry_daily 同步完成: 0 条日行情记录 "
                f"(codes={len(codes)}, chunk_size={chunk_size}, "
                f"window={begin_date}~{end_date}, failed_chunks={failed_chunks}/{total_chunks})"
            )
        else:
            logger.info(f"industry_daily 同步完成: {saved} 条日行情记录")
        return saved

    async def _sync_industry_weight(self, today: date, period_id: str) -> int:
        """执行层:行业指数日权重. 分批下载.

        分批下载(每批 BATCH_SIZE 个代码),避免全量加载导致 OOM。
        全量 511 代码 × 3400 天 × 成分股 ≈ 26GB 内存,分批可控制在 ~1GB。

        Returns:
            saved count(入库行数)。
        """
        codes = await self._provider.get_industry_index_codes(self._cache_dir)
        if not codes:
            raise RuntimeError(
                "未获取到行业指数代码列表(provider 故障或 base_info 缓存缺失)"
            )

        # Phase 03 增量(03-04):替换原固定 7 天窗口,走 last_sync_date 表
        begin_date, end_date = await self._resolve_incremental_range(
            _INDUSTRY_WEIGHT_SYNC_TYPE, scope_key=None, today=today
        )

        # 分批下载(成分股二维展开类,密度远高于日度行情,用独立小基准 weight_chunk_size)
        # 全量 511 代码 × 3400 天 × 成分股 ≈ 26GB,分批 20 个 ≈ ~1GB
        batch_size = resolve_weight_chunk_size()
        total_saved = 0
        all_trade_dates: list[str] = []

        for i in range(0, len(codes), batch_size):
            batch = codes[i : i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(codes) + batch_size - 1) // batch_size
            logger.info(
                f"industry_weight 批次 {batch_num}/{total_batches}: "
                f"{len(batch)} 个代码 ({batch[0]}~{batch[-1]})"
            )

            data = await self._provider.get_industry_weight(
                batch, self._cache_dir,
                is_local=False, begin_date=begin_date, end_date=end_date,
            )

            records: list[IndustryWeight] = []
            for _index_code, df in data.items():
                if df is None or df.empty:
                    continue
                records.extend(self._df_to_weight_records(df, _index_code))

            if records:
                saved = await self._store.save_industry_weight(records)
                total_saved += saved
                # 收集 trade_date 用于更新 last_sync_date
                all_trade_dates.extend(r.trade_date for r in records if r.trade_date)

            # 显式释放当前批次数据
            del data
            del records

        # Phase 03 D-08:有记录才推进 last_sync_date(空响应不推进)。
        if all_trade_dates:
            max_str = max(all_trade_dates)
            try:
                max_date = date(
                    int(max_str[:4]), int(max_str[4:6]), int(max_str[6:8])
                )
                await self._last_sync_store.set_last_sync_date(
                    _INDUSTRY_WEIGHT_SYNC_TYPE, None, max_date
                )
            except (ValueError, IndexError):
                logger.warning("industry_weight trade_date 解析失败:%s", max_str)

        logger.info(f"industry_weight 同步完成: {total_saved} 条权重记录")
        return total_saved

    async def _resolve_daily_range(self, index_code: str, today: date) -> tuple[int, int]:
        """解析增量同步的 [begin_date, end_date] 区间.

        从 store 查全局最后同步日(2026-07-28 修复:原只查 codes[0] 的 last_date,
        若 codes[0] 是最久未同步 code 会导致 window 过宽),无则回退 7 天。
        """
        end_date = int(today.strftime("%Y%m%d"))
        last = await self._store.get_industry_daily_max_last_date()
        if last:
            try:
                last_d = date(int(last[:4]), int(last[4:6]), int(last[6:8]))
                begin_date = int((last_d + timedelta(days=1)).strftime("%Y%m%d"))
                return begin_date, end_date
            except (ValueError, IndexError):
                pass
        return int((today - timedelta(days=7)).strftime("%Y%m%d")), end_date

    # ------------------------------------------------------------------
    # 维度入口（基本信息月度 + 成分股周度，挂 refdata 之后）
    # ------------------------------------------------------------------
    async def run_dimensions(self, today: date) -> None:
        """维度同步：行业指数基本信息（月度）+ 成分股（周度）."""
        await self._maybe_sync_industry_base_info(today)
        await self._maybe_sync_industry_constituent(today)

    async def run_dimensions_force(self, today: date) -> None:
        """强制维度同步：绕过 is_synced，两个 sync_type 都强制.

        Per Phase 01 (manual CLI --force)。base_info 仍保留表空强制首次同步分支。
        """
        await self._maybe_sync_industry_base_info(today, force=True)
        await self._maybe_sync_industry_constituent(today, force=True)

    async def _maybe_sync_industry_base_info(
        self, today: date, *, force: bool = False
    ) -> None:
        """编排层:行业指数基本信息(月度). is_synced 门控 + 空表强制 + 重试.

        空表(is_industry_base_info_empty=True)时绕过 is_synced 门控,
        确保首次同步不被跳过(与原设计一致)。
        """
        month_id = f"{today.year}-{today.month:02d}"
        sync_type = "industry_base_info"

        # 空表首次强制同步(force 路径同样保留,确保空表初始化不被跳过)
        is_empty = await self._store.is_industry_base_info_empty()
        if is_empty:
            logger.info("industry_base_info 表为空,强制首次同步")
        elif not force and await self._state.is_synced(sync_type, month_id):
            logger.info(f"{sync_type} {month_id} 已同步,跳过")
            return

        await self._state.mark_running(sync_type, month_id)
        success = await sync_with_retry(
            self._sync_industry_base_info, f"{sync_type} {month_id}", today, month_id
        )
        if success:
            await self._state.mark_success(sync_type, month_id)
        else:
            await self._state.mark_failed(sync_type, month_id, _RETRIES_EXHAUSTED)

    async def _maybe_sync_industry_constituent(
        self, today: date, *, force: bool = False
    ) -> None:
        """编排层:行业指数成分股(周度). is_synced 门控 + 重试."""
        week_id = f"{today.year}-W{today.isocalendar()[1]:02d}"
        sync_type = "industry_constituent"
        if not force and await self._state.is_synced(sync_type, week_id):
            logger.info(f"{sync_type} {week_id} 已同步,跳过")
            return
        await self._state.mark_running(sync_type, week_id)
        success = await sync_with_retry(
            self._sync_industry_constituent, f"{sync_type} {week_id}", today, week_id
        )
        if success:
            await self._state.mark_success(sync_type, week_id)
        else:
            await self._state.mark_failed(sync_type, week_id, _RETRIES_EXHAUSTED)

    async def _sync_industry_base_info(self, today: date, period_id: str) -> int:
        """执行层:行业指数基本信息. 整组拉取(纯目录数据,无 code_list,不分批).

        Returns:
            saved count(入库行数)。
        """
        df = await self._provider.get_industry_base_info(
            self._cache_dir, is_local=False,
        )
        if df is None or df.empty:
            logger.info("行业指数基本信息返回空数据")
            return 0
        records = self._df_to_base_info_records(df)
        saved = await self._store.save_industry_base_info(records)
        logger.info(f"industry_base_info 同步完成: {saved} 条基本信息记录")
        return saved

    async def _sync_industry_constituent(self, today: date, period_id: str) -> int:
        """执行层:行业指数成分股. 整组拉取(成分股维度,不分批).

        Returns:
            saved count(入库行数)。
        """
        codes = await self._provider.get_industry_index_codes(self._cache_dir)
        if not codes:
            raise RuntimeError(
                "未获取到行业指数代码列表(provider 故障或 base_info 缓存缺失)"
            )

        data = await self._provider.get_industry_constituent(
            codes, self._cache_dir, is_local=False,
        )
        records: list[IndustryConstituent] = []
        for _index_code, df in data.items():
            if df is None or df.empty:
                continue
            records.extend(self._df_to_constituent_records(df, _index_code))

        saved = await self._store.save_industry_constituent(records)
        logger.info(f"industry_constituent 同步完成: {saved} 条成分股记录")
        return saved

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

    @classmethod
    def _normalize_trade_date(cls, value: Any) -> str | None:
        """任意形态的交易日 → YYYYMMDD 字符串.

        SDK 返回格式会漂移(2026-09-17 实证):TRADE_DATE 曾是索引/普通列,
        dtype 曾是 int 字符串/Timestamp/datetime。统一在此归一,store 层
        _yyyymmdd_to_date 只认 YYYYMMDD 前缀。
        """
        if isinstance(value, pd.Timestamp):
            return value.strftime("%Y%m%d")
        if isinstance(value, datetime):
            return value.strftime("%Y%m%d")
        if isinstance(value, date):
            return value.strftime("%Y%m%d")
        s = cls._safe_str(value)
        if s is None:
            return None
        if s.isdigit() and len(s) == 8:
            return s
        # "2026-10-27" / "2026-10-27 00:00:00"
        if "-" in s:
            head = s[:10].replace("-", "")
            return head if head.isdigit() and len(head) == 8 else None
        return None

    @classmethod
    def _reset_for_record(cls, df: pd.DataFrame) -> pd.DataFrame:
        """把索引中的字段落成列(按缺失字段判定,不再依赖旧格式假设).

        2026-09-17 SDK 格式变更:industry_daily 的 df 变为
        「TRADE_DATE 为索引名 + INDEX_CODE/TOTAL_CAP 为普通列」,旧守卫
        `reset_index() if "INDEX_CODE" not in df.columns` 在新格式下跳过
        reset → row.get("TRADE_DATE") 恒 None → 100% 行静默丢弃,行业日行情
        断供一个月。改按「记录需要的字段是否在列」判定:TRADE_DATE 不在列
        (无论它是不是索引名)都 reset_index()。旧格式(纯 OHLC 列 + 日期索引)
        行为不变。
        """
        if "TRADE_DATE" not in df.columns:
            return df.reset_index()
        return df

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
    def _df_to_base_info_records(cls, df: pd.DataFrame) -> list[IndustryBaseInfo]:
        records: list[IndustryBaseInfo] = []
        for _, row in df.iterrows():
            index_code = cls._safe_str(row.get("INDEX_CODE"))
            industry_code = cls._safe_str(row.get("INDUSTRY_CODE"))
            if not index_code or not industry_code:
                continue
            records.append(IndustryBaseInfo(
                index_code=index_code,
                industry_code=industry_code,
                level_type=cls._safe_int(row.get("LEVEL_TYPE")),
                level1_name=cls._safe_str(row.get("LEVEL1_NAME")),
                level2_name=cls._safe_str(row.get("LEVEL2_NAME")),
                level3_name=cls._safe_str(row.get("LEVEL3_NAME")),
                is_pub=cls._safe_int(row.get("IS_PUB")),
                change_reason=cls._safe_str(row.get("CHANGE_REASON")),
            ))
        return records

    @classmethod
    def _df_to_constituent_records(
        cls, df: pd.DataFrame, index_code_fallback: str | None = None
    ) -> list[IndustryConstituent]:
        df_reset = cls._reset_for_record(df)
        records: list[IndustryConstituent] = []
        for _, row in df_reset.iterrows():
            records.append(IndustryConstituent(
                index_code=cls._safe_str(row.get("INDEX_CODE"))
                or index_code_fallback
                or "",
                con_code=cls._safe_str(row.get("CON_CODE")) or "",
                in_date=cls._safe_str(row.get("INDATE")),
                out_date=cls._safe_str(row.get("OUTDATE")),
                index_name=cls._safe_str(row.get("INDEX_NAME")),
            ))
        return records

    @classmethod
    def _df_to_weight_records(
        cls, df: pd.DataFrame, index_code_fallback: str | None = None
    ) -> list[IndustryWeight]:
        df_reset = cls._reset_for_record(df)
        records: list[IndustryWeight] = []
        for _, row in df_reset.iterrows():
            trade_date = cls._normalize_trade_date(row.get("TRADE_DATE"))
            if trade_date is None:
                continue
            records.append(IndustryWeight(
                index_code=cls._safe_str(row.get("INDEX_CODE"))
                or index_code_fallback
                or "",
                con_code=cls._safe_str(row.get("CON_CODE")) or "",
                trade_date=trade_date,
                weight=cls._safe_float(row.get("WEIGHT")),
            ))
        return records

    @classmethod
    def _df_to_daily_records(
        cls, df: pd.DataFrame, index_code_fallback: str | None = None
    ) -> list[IndustryDaily]:
        df_reset = cls._reset_for_record(df)
        records: list[IndustryDaily] = []
        for _, row in df_reset.iterrows():
            index_code = (
                cls._safe_str(row.get("INDEX_CODE")) or index_code_fallback
            )
            trade_date = cls._normalize_trade_date(row.get("TRADE_DATE"))
            if not index_code or trade_date is None:
                continue
            records.append(IndustryDaily(
                index_code=index_code,
                trade_date=trade_date,
                open=cls._safe_float(row.get("OPEN")),
                high=cls._safe_float(row.get("HIGH")),
                low=cls._safe_float(row.get("LOW")),
                close=cls._safe_float(row.get("CLOSE")),
                pre_close=cls._safe_float(row.get("PRE_CLOSE")),
                volume=cls._safe_float(row.get("VOLUME")),
                amount=cls._safe_float(row.get("AMOUNT")),
                pb=cls._safe_float(row.get("PB")),
                pe=cls._safe_float(row.get("PE")),
                total_cap=cls._safe_float(row.get("TOTAL_CAP")),
                a_float_cap=cls._safe_float(row.get("A_FLOAT_CAP")),
            ))
        return records
