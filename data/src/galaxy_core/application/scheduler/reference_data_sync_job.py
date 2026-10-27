"""Reference data sync job for scheduler.

Integrates P0 data synchronization into AutoSyncScheduler:
- stock_basic: 每周检查新增/退市代码
- backward_factor: 月度全量重新同步

Runs sequentially after K-line sync (API 不支持并发).
"""

import logging
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from galaxy_core.application.scheduler.retry_handler import sync_with_retry
from galaxy_core.application.scheduler.state_manager import SyncStateManager
from galaxy_core.database.core.async_connection import AsyncDatabaseManager
from galaxy_core.database.models import BackwardFactor, StockBasic
from galaxy_core.domain.ports.calendar_store import CalendarStorePort
from galaxy_core.domain.ports.reference_provider import ReferenceProviderPort
from galaxy_core.shared_kernel.utils.chunking import resolve_kline_chunk_size
from galaxy_core.shared_kernel.utils.config_loader import get_section

logger = logging.getLogger(__name__)


class ReferenceDataSyncJob:
    """Reference data (P0) synchronization job.

    运行在 K-line sync 之后，共享 API 连接（API 不支持并发）。
    各表独立追踪同步状态，不按 security_type 拆分。
    """

    def __init__(
        self,
        state_manager: SyncStateManager,
        reference_provider: ReferenceProviderPort,
        db_manager: AsyncDatabaseManager,
        calendar_store: CalendarStorePort,
    ) -> None:
        self._state_manager = state_manager
        self._reference_provider = reference_provider
        self._db = db_manager
        self._calendar_store = calendar_store
        self._config = get_section("scheduler")
        self._sync_config = get_section("sync")
        # SDK 文档要求 local_path 为绝对路径
        raw_cache = get_section("amazing_data").get("local_path", "./data/local_cache/")
        self._cache_dir = str(Path(raw_cache).resolve())
        if raw_cache.endswith("/"):
            self._cache_dir += "/"

    # ========================================================================
    # 主入口
    # ========================================================================
    async def run(self, today: date) -> None:
        """Run reference data sync checks for today.

        向后兼容入口:内部顺序调 run_stock_basic + run_backward_factor(原 per-type
        交错语义等价,因两表无数据依赖)。

        各表频率：
        - stock_basic: 每周一次
        - backward_factor: 每月一次
        """
        await self.run_stock_basic(today)
        await self.run_backward_factor(today)

    async def run_stock_basic(self, today: date) -> None:
        """同步 stock_basic(周度,快)。遍历 security_types 调 _maybe_sync_stock_basic。

        2026-08-04 拆分:原 run() 内 per-type 交错 stock_basic↔backward_factor,
        backward_factor(月度全量 2h+)阻塞后续 fundflow → long_hu_bang 拖到凌晨
        SDK 不稳定时段全失败。拆出 stock_basic(快)让 scheduler chain 先跑它,
        backward_factor 移到 chain 末尾(scheduler.py)不阻塞 fundflow。
        """
        logger.info("=" * 50)
        logger.info("ReferenceDataSyncJob: stock_basic 检查开始")
        logger.info("=" * 50)

        security_types = self._config.get("security_types", ["EXTRA_ETF"])
        for st in security_types:
            await self._maybe_sync_stock_basic(today, st)

        logger.info("=" * 50)
        logger.info("ReferenceDataSyncJob: stock_basic 检查完成")
        logger.info("=" * 50)

    async def run_backward_factor(self, today: date) -> None:
        """同步 backward_factor(月度,慢,全量 ~2h+)。遍历 security_types 调
        _maybe_sync_backward_factor。

        2026-08-04 拆分:从 run() 拆出,scheduler chain 移到末尾(fundflow 之后、
        cleanup 之前)。backward_factor 月度门控(is_synced month_id),非月度日
        秒过;月初触发全量时即使 2h+ 也不阻塞已完成的 fundflow。

        SDK 限制:get_backward_factor 无日期参数,无法增量,全量不可避免。
        """
        logger.info("=" * 50)
        logger.info("ReferenceDataSyncJob: backward_factor 检查开始")
        logger.info("=" * 50)

        security_types = self._config.get("security_types", ["EXTRA_ETF"])
        for st in security_types:
            await self._maybe_sync_backward_factor(today, st)

        logger.info("=" * 50)
        logger.info("ReferenceDataSyncJob: backward_factor 检查完成")
        logger.info("=" * 50)

    # ========================================================================
    # stock_basic
    # ========================================================================
    async def _maybe_sync_stock_basic(self, today: date, security_type: str) -> None:
        """如有需要，同步证券基础信息（每周）.

        sync_type 按 security_type 拆分（2026-07-10 修 Bug 4）:
        原固定 "refdata_stock_basic" 导致空表首启时第 1 个 type success 后
        week_id 标 done,第 2/3 个 type 被跳过。改为 "refdata_stock_basic_{type}"
        各 type 独立门控。
        """
        week_id = f"{today.year}-W{today.isocalendar()[1]:02d}"
        sync_type = f"refdata_stock_basic_{security_type}"

        # 检查 stock_basic 表是否为空，为空时强制首次同步
        is_empty = await self._is_stock_basic_empty()
        if is_empty:
            logger.info("stock_basic 表为空，强制执行首次同步")
            # 忽略 week_id 去重，强制执行
        elif await self._state_manager.is_synced(sync_type, week_id):
            logger.info(f"stock_basic {security_type} {week_id} 已同步，跳过")
            return

        await self._state_manager.mark_running(sync_type, week_id)

        success = await sync_with_retry(
            self._sync_stock_basic,
            f"stock_basic {week_id}",
            today,
            security_type,
            week_id,
        )

        if success:
            await self._state_manager.mark_success(sync_type, week_id)
            # stock_basic 同步成功后，执行退市标记
            if self._is_etf_security_type(security_type):
                await self._maybe_mark_delisted_etfs(today, security_type)
        else:
            await self._state_manager.mark_failed(sync_type, week_id, "All retries exhausted")

    async def _sync_stock_basic(self, today: date, security_type: str, week_id: str) -> None:
        """同步证券基础信息（异步实现）."""
        logger.info(f"[stock_basic] 开始同步 {week_id}, security_type={security_type}")

        # 获取代码列表 via ReferenceProviderPort
        codes = await self._reference_provider.get_stock_list(security_type)
        logger.info(f"当前 {security_type} 数量: {len(codes)}")

        # 查询 stock_basic 表中已存在的 symbol
        try:
            from sqlalchemy import select

            async with self._db.session() as session:
                result = await session.execute(select(StockBasic.symbol))
                existing_symbols = {row[0] for row in result.all()}

            # 过滤出不存在的 symbol
            codes = [s for s in codes if s not in existing_symbols]
            if not codes:
                logger.info(f"stock_basic 表已包含所有 {security_type} 代码，无需同步")
                return
            logger.info(f"需要同步 {len(codes)} 个新代码")
        except Exception as e:
            logger.warning(f"查询 stock_basic 表失败: {e}，将同步所有代码")

        from galaxy_core.domain.symbol.type_inference import to_broad_security_type

        broad_type = to_broad_security_type(security_type)

        # SDK endpoint 分流：get_stock_basic 只支持股票代码，对 ETF/INDEX 返回空
        # （实测 shape=(0,10)，历史 4+ 次印证）。ETF/INDEX 必须走 get_code_info。
        # 见 AGENTS.md 2026-07-07 审计记录。
        if self._is_stock_basic_security_type(security_type):
            records = await self._fetch_stock_basic_records(codes, broad_type)
        else:
            records = await self._fetch_code_info_records(codes, broad_type, security_type)

        if not records:
            return

        saved = await self._upsert_stock_basic(records)
        logger.info(f"保存/更新 stock_basic 记录: {saved}")

    async def _fetch_stock_basic_records(
        self, codes: list[str], broad_type: str
    ) -> list[dict]:
        """通过 get_stock_basic_df 取数并解析（股票路径）.

        Args:
            codes: 待同步的代码列表（已过滤已存在的）
            broad_type: 宽口径 security_type，写入 stock_basic.security_type 列
        """
        df = await self._reference_provider.get_stock_basic_df(codes)
        if df is None or df.empty:
            logger.info("stock_basic 返回空数据")
            return []
        return self._parse_stock_basic_records(df, broad_type)

    async def _fetch_code_info_records(
        self, codes: list[str], broad_type: str, security_type: str
    ) -> list[dict]:
        """通过 get_code_info 取数并解析（ETF/INDEX 路径）.

        get_stock_basic 对 ETF/INDEX 代码永远返回空，必须用 get_code_info。
        get_code_info 返回全量 code_market index，本方法按 codes 过滤。

        Args:
            codes: 待同步的代码列表（已过滤已存在的）
            broad_type: 宽口径 security_type，写入 stock_basic.security_type 列
            security_type: 原始 security_type，传给 get_code_info
        """
        df = await self._reference_provider.get_code_info(security_type)
        if df is None or df.empty:
            logger.info(f"{security_type} get_code_info 返回空数据")
            return []
        return self._parse_records_from_code_info(df, broad_type, codes)

    # ========================================================================
    # backward_factor
    # ========================================================================
    async def _maybe_sync_backward_factor(self, today: date, security_type: str) -> None:
        """如有需要，同步后复权因子（月度全量）.

        sync_type 按 security_type 拆分（同 stock_basic Bug 4 修复理由）:
        "refdata_backward_factor_{type}" 各 type 独立门控。
        """
        month_id = f"{today.year}-{today.month:02d}"
        sync_type = f"refdata_backward_factor_{security_type}"

        if await self._state_manager.is_synced(sync_type, month_id):
            logger.info(f"backward_factor {security_type} {month_id} 已同步，跳过")
            return

        await self._state_manager.mark_running(sync_type, month_id)

        success = await sync_with_retry(
            self._sync_backward_factor,
            f"backward_factor {security_type} {month_id}",
            today,
            security_type,
            month_id,
        )

        if success:
            await self._state_manager.mark_success(sync_type, month_id)
        else:
            await self._state_manager.mark_failed(sync_type, month_id, "All retries exhausted")

    async def _sync_backward_factor(self, today: date, security_type: str, month_id: str) -> None:
        """同步后复权因子（异步实现，chunk 分批拉取 + 写入控制内存）.

        全量首启(13 年日度)整组传 API 会爆内存(2026-07-10 实测 ETF 1585 只
        RSS 7GB + pandas 解析卡死)。改用统一分批工具 resolve_daily_chunk_size()
        按内存预算(默认 158 万行/批)反推 chunk_size。

        每 chunk 独立:API 拉取 → 解析 → upsert(独立 session/事务即时 commit)，
        单 chunk 失败 log warning 继续(部分失败不阻断其它 chunk)。
        """
        logger.info(f"[backward_factor] 开始同步 {month_id}, security_type={security_type}")

        # 获取代码列表
        codes = await self._reference_provider.get_stock_list(security_type)
        logger.info(f"代码数量: {len(codes)}")
        if not codes:
            return

        # backward_factor 是全量历史数据(无窗口概念,每只 ~3159 行),用 kline 模型
        # 估算 chunk_size(13 年 day):158万/3159 ≈ 500。
        # 不用 resolve_daily_chunk_size —— 它有 daily_code_cap=100(industry_daily
        # 增量场景防 SDK 大批量卡死),backward_factor 是全量历史不受此 cap。
        chunk_size = resolve_kline_chunk_size("day", "20130101", today.strftime("%Y%m%d"))
        chunks = [codes[i : i + chunk_size] for i in range(0, len(codes), chunk_size)]
        logger.info(
            f"分 {len(chunks)} chunk (chunk_size={chunk_size}, {len(codes)} 只)"
        )

        total_saved = 0
        failed_chunks = 0
        for idx, chunk_codes in enumerate(chunks, 1):
            logger.info(
                f"[backward_factor] chunk {idx}/{len(chunks)} "
                f"({len(chunk_codes)} 只, {chunk_codes[0]}~{chunk_codes[-1]})"
            )
            try:
                df = await self._reference_provider.get_backward_factor_df(
                    chunk_codes, self._cache_dir
                )
            except Exception as e:
                logger.error(
                    f"[backward_factor] chunk {idx} API 失败: {type(e).__name__}: {e},跳过"
                )
                failed_chunks += 1
                continue

            if df is None or df.empty:
                logger.info(f"[backward_factor] chunk {idx} 返回空数据,跳过")
                continue

            records = self._parse_backward_factor_df(df)
            if records:
                saved = await self._upsert_backward_factor(records)
                total_saved += saved
                logger.info(
                    f"[backward_factor] chunk {idx}/{len(chunks)} 完成: "
                    f"{saved} 条 (累计 {total_saved})"
                )

        logger.info(
            f"[backward_factor] {security_type} 同步完成: "
            f"{total_saved} 条, {failed_chunks}/{len(chunks)} chunk 失败"
        )

    # ========================================================================
    # UPSERT 操作
    # ========================================================================
    async def _upsert_stock_basic(self, records: list[dict]) -> int:
        """异步批量 UPSERT stock_basic 记录."""
        if not records:
            return 0

        # asyncpg 参数上限 32767，每条 record 11 字段，batch_size 上限 ~2900。
        # 取 2000 留余量（2000 × 11 = 22000 < 32767）。
        batch_size = 2000
        total = 0
        async with self._db.session() as session:
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]
                stmt = pg_insert(StockBasic).values(batch)
                upsert_stmt = stmt.on_conflict_do_update(
                    index_elements=["symbol"],
                    set_={
                        "security_name": stmt.excluded.security_name,
                        "comp_name": stmt.excluded.comp_name,
                        "pinyin": stmt.excluded.pinyin,
                        "comp_name_eng": stmt.excluded.comp_name_eng,
                        "list_date": stmt.excluded.list_date,
                        "delist_date": stmt.excluded.delist_date,
                        "listplate_name": stmt.excluded.listplate_name,
                        "comp_sname_eng": stmt.excluded.comp_sname_eng,
                        "is_listed": stmt.excluded.is_listed,
                        "security_type": stmt.excluded.security_type,
                        "updated_at": func.now(),
                    },
                )
                await session.execute(upsert_stmt)
                total += len(batch)
        return total

    async def _upsert_backward_factor(self, records: list[dict]) -> int:
        """异步批量 UPSERT backward_factor 记录.

        每批独立 session/事务即时 commit（2026-07-10 修）:
        原单 session 包全量 → 158 万行单事务 WAL 堆积 + commit 慢。
        分 chunk 后每 chunk records ≈ 158 万,每 5000 条一批独立 commit。
        """
        if not records:
            return 0

        # 去重(同 chunk 内 symbol+date 唯一)
        seen = {}
        for r in records:
            key = (r["symbol"], r["trade_date"])
            seen[key] = r
        deduped = list(seen.values())

        batch_size = 5000
        total = 0
        for i in range(0, len(deduped), batch_size):
            batch = deduped[i : i + batch_size]
            async with self._db.session() as session:
                stmt = pg_insert(BackwardFactor).values(batch)
                upsert_stmt = stmt.on_conflict_do_update(
                    index_elements=["symbol", "trade_date"],
                    set_={
                        "factor": stmt.excluded.factor,
                        "updated_at": func.now(),
                    },
                )
                await session.execute(upsert_stmt)
                total += len(batch)
        return total

    # ========================================================================
    # 数据解析工具
    # ========================================================================
    @staticmethod
    def _parse_date(value) -> date | None:
        """解析日期值."""
        if value is None or pd.isna(value):
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, (int, float)):
            value = str(int(value))
        if isinstance(value, str):
            value = value.strip()
            if len(value) == 8:
                return date(int(value[:4]), int(value[4:6]), int(value[6:]))
            if len(value) == 10 and value[4] == "-":
                return date.fromisoformat(value)
        return None

    @classmethod
    def _parse_date_series(cls, series: pd.Series) -> pd.Series:
        """向量化解析日期值.

        尝试多种格式：YYYYMMDD（int/str）、YYYY-MM-DD、datetime。
        返回 date 对象 Series(nocodb 形态 list_date/delist_date 为 date 列)。
        """
        result = pd.Series([None] * len(series), index=series.index, dtype=object)

        is_null = series.isna()
        non_null = ~is_null

        if not non_null.any():
            return result

        # 转为字符串处理
        str_vals = series[non_null].astype(str).str.strip()

        # 尝试 YYYYMMDD 格式（8位数字）
        is_8digit = str_vals.str.len() == 8
        if is_8digit.any():
            parsed = pd.to_datetime(str_vals[is_8digit], format="%Y%m%d", errors="coerce")
            valid = parsed.notna()
            if valid.any():
                result.loc[str_vals[is_8digit][valid].index] = (
                    parsed[valid].dt.date
                )

        # 尝试 YYYY-MM-DD 格式（10位，第5位是-）
        still_none = result.isna() & non_null
        if still_none.any():
            str_remaining = str_vals[still_none]
            is_10dash = str_remaining.str.len() == 10
            if is_10dash.any():
                parsed = pd.to_datetime(
                    str_remaining[is_10dash], format="%Y-%m-%d", errors="coerce"
                )
                valid = parsed.notna()
                if valid.any():
                    result.loc[str_remaining[is_10dash][valid].index] = (
                        parsed[valid].dt.date
                    )

        # 尝试 int/float 转字符串后解析
        still_none = result.isna() & non_null
        if still_none.any():
            str_remaining = str_vals[still_none]
            # 已经是字符串，尝试自动推断
            parsed = pd.to_datetime(str_remaining, errors="coerce")
            valid = parsed.notna()
            if valid.any():
                result.loc[str_remaining[valid].index] = (
                    parsed[valid].dt.date
                )

        return result

    @staticmethod
    def _to_float(value) -> float | None:
        """安全转换为 float."""
        if value is None or pd.isna(value):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _to_bool(value) -> bool:
        """安全转换为 bool."""
        if value is None or pd.isna(value):
            return False
        try:
            return bool(int(value))
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _to_float_series(series: pd.Series) -> pd.Series:
        """向量化安全转换为 float."""
        return pd.to_numeric(series, errors="coerce")

    @staticmethod
    def _to_bool_series(series: pd.Series) -> pd.Series:
        """向量化安全转换为 bool."""
        return pd.to_numeric(series, errors="coerce").fillna(0).astype(int).astype(bool)

    @classmethod
    def _parse_stock_basic_records(cls, df: pd.DataFrame, security_type: str) -> list[dict]:
        """向量化提取 stock_basic 记录.

        Args:
            df: 包含 MARKET_CODE/code, SECURITY_NAME, LISTDATE 等列的 DataFrame
            security_type: 证券类型

        Returns:
            记录字典列表
        """
        # SDK 返回的 DataFrame 可能含重复 index 标签（实测 get_stock_basic 对股票
        # 返回的 DataFrame index 全为 0），后续 df[valid_mask] / result_df.loc[mask, ...]
        # 等 boolean mask 索引会触发 "cannot reindex on an axis with duplicate labels"。
        # reset_index(drop=True) 重建唯一 RangeIndex，code 已在 MARKET_CODE/code 列里，
        # 原 index 无业务语义。
        df = df.copy().reset_index(drop=True)

        # 提取 code 列
        if "MARKET_CODE" in df.columns:
            code_col = df["MARKET_CODE"]
        elif "code" in df.columns:
            code_col = df["code"]
        else:
            return []

        # 跳过 code 为 NaN 的行
        valid_mask = code_col.notna()
        df = df[valid_mask].copy()
        code_col = code_col[valid_mask]

        if df.empty:
            return []

        # 向量化日期解析
        listdate_col = (
            df["LISTDATE"] if "LISTDATE" in df.columns
            else pd.Series([None] * len(df), index=df.index)
        )
        delistdate_col = (
            df["DELISTDATE"] if "DELISTDATE" in df.columns
            else pd.Series([None] * len(df), index=df.index)
        )
        list_dates = cls._parse_date_series(listdate_col)
        delist_dates = cls._parse_date_series(delistdate_col)

        # IS_LISTED: 1=上市交易, 3=终止上市；adapter 转为 bool 或 None
        is_listed_raw = df.get("IS_LISTED", pd.Series(dtype=float))
        is_listed_num = pd.to_numeric(is_listed_raw, errors="coerce")
        is_listed = is_listed_num.apply(
            lambda x: True if x == 1 else False if x == 3 else None
        )

        # 向量化构建 records
        result_df = pd.DataFrame({
            "symbol": code_col.astype(str),
            "security_name": df.get("SECURITY_NAME", pd.Series(dtype=object)),
            "comp_name": df.get("COMP_NAME", pd.Series(dtype=object)),
            "pinyin": df.get("PINYIN", pd.Series(dtype=object)),
            "comp_name_eng": df.get("COMP_NAME_ENG", pd.Series(dtype=object)),
            "list_date": list_dates,
            "delist_date": delist_dates,
            "listplate_name": df.get("LISTPLATE_NAME", pd.Series(dtype=object)),
            "comp_sname_eng": df.get("COMP_SNAME_ENG", pd.Series(dtype=object)),
            "is_listed": is_listed,
            "security_type": security_type,
        })

        # 将 NaT/NaN 日期替换为 None
        for date_col in ["list_date", "delist_date"]:
            mask = result_df[date_col].apply(
                lambda x: x is pd.NaT or (isinstance(x, float) and pd.isna(x))
            )
            result_df.loc[mask, date_col] = None

        # 将 object 列的 NaN 替换为 None
        # 注意：当某列全为 NaN 时，pandas 推断为 float64 而非 object，
        # where(notna, None) 在 float 列上 None 会被转回 NaN，
        # to_dict 后传给 asyncpg 会报 'invalid input: nan (expected str)'。
        # 先 astype(object) 强制 object dtype，None 才能保留。
        for col in ["security_name", "comp_name", "pinyin", "comp_name_eng",
                    "listplate_name", "comp_sname_eng"]:
            result_df[col] = result_df[col].astype(object).where(
                result_df[col].notna(), other=None
            )

        # is_listed NaN -> None
        result_df["is_listed"] = result_df["is_listed"].where(
            result_df["is_listed"].notna(), other=None
        )

        return result_df.to_dict("records")

    @classmethod
    def _parse_records_from_code_info(
        cls, df: pd.DataFrame, security_type: str, codes: list[str]
    ) -> list[dict]:
        """从 get_code_info 返回的 DataFrame 提取 stock_basic 记录.

        get_code_info 用于 ETF/INDEX（get_stock_basic 不支持这些代码类型）。
        返回的 DataFrame 结构（实测）：
        - index.name = 'code_market'，index 值如 '159596.SZ'（唯一）
        - columns = ['symbol'(中文名), 'security_status', 'pre_close',
                     'high_limited', 'low_limited', 'price_tick', 'list_day'(上市日)]

        字段映射对齐 _parse_stock_basic_records 的 11 字段，get_code_info 不提供的
        字段（comp_name/pinyin/...）填 None，UPSERT 时这些列保持原值或写 NULL。

        Args:
            df: get_code_info 返回的原始 DataFrame（index=code_market）
            security_type: 宽口径 security_type，写入 stock_basic.security_type 列
            codes: 仅解析这些代码（过滤掉 df 中多余行）

        Returns:
            记录字典列表
        """
        if df.empty or not codes:
            return []

        # reset_index 把 code_market 从 index 转为列，列名 = index.name（'code_market'）
        df_reset = df.reset_index()
        code_col_name = df_reset.columns[0]  # 'code_market' 或 reset 后的首列

        # 过滤到目标 codes（get_code_info 返回全量，需按 codes 截取）
        codes_set = set(codes)
        df_reset = df_reset[df_reset[code_col_name].isin(codes_set)]
        if df_reset.empty:
            return []

        # symbol 列是中文名称（get_code_info 的 'symbol' 列语义与 get_stock_basic 不同）
        # list_day 是上市日期 YYYYMMDD 字符串
        list_dates = cls._parse_date_series(
            df_reset["list_day"] if "list_day" in df_reset.columns
            else pd.Series([None] * len(df_reset), index=df_reset.index)
        )

        result_df = pd.DataFrame({
            "symbol": df_reset[code_col_name].astype(str),
            "security_name": df_reset.get("symbol", pd.Series(dtype=object)),
            "comp_name": None,
            "pinyin": None,
            "comp_name_eng": None,
            "list_date": list_dates,
            "delist_date": None,
            "listplate_name": None,
            "comp_sname_eng": None,
            "is_listed": None,
            "security_type": security_type,
        })

        # NaT/NaN 日期 → None
        mask = result_df["list_date"].apply(
            lambda x: x is pd.NaT or (isinstance(x, float) and pd.isna(x))
        )
        result_df.loc[mask, "list_date"] = None

        # object 列 NaN → None
        for col in ["security_name"]:
            result_df[col] = result_df[col].where(result_df[col].notna(), other=None)

        return result_df.to_dict("records")

    @classmethod
    def _parse_backward_factor_records(cls, df: pd.DataFrame) -> list[dict]:
        """向量化提取 backward_factor 记录.

        使用 melt 模式替代 iterrows，DataFrame 格式: index=日期, columns=股票代码。

        Args:
            df: 宽格式 DataFrame（index=日期, columns=股票代码）

        Returns:
            记录字典列表
        """
        if df.empty:
            return []

        df_reset = df.reset_index()
        date_col = df_reset.columns[0]

        # melt: 宽格式 → 长格式
        df_melted = df_reset.melt(
            id_vars=[date_col],
            var_name="symbol",
            value_name="factor",
        )

        # 删除 NaN factor
        df_melted = df_melted.dropna(subset=["factor"])

        if df_melted.empty:
            return []

        # 解析日期 → date(nocodb 形态 trade_date=date 列;SDK 字面值是北京日期)
        df_melted[date_col] = pd.to_datetime(df_melted[date_col]).dt.date

        # 转为 records
        records = df_melted.rename(columns={date_col: "trade_date"}).to_dict("records")
        return records

    def _parse_backward_factor_df(self, df: pd.DataFrame) -> list[dict]:
        """将 backward_factor DataFrame 转换为记录列表（兼容包装）."""
        return self._parse_backward_factor_records(df)

    # ========================================================================
    # 工具
    # ========================================================================
    @staticmethod
    def _is_etf_security_type(security_type: str) -> bool:
        """判断是否为 ETF 类 security_type."""
        etf_types = {"EXTRA_ETF", "SH_ETF", "SZ_ETF"}
        return security_type in etf_types

    @staticmethod
    def _is_stock_basic_security_type(security_type: str) -> bool:
        """判断是否走 get_stock_basic endpoint（仅股票类）.

        get_stock_basic SDK endpoint 仅支持股票代码，对 ETF/INDEX 返回空。
        股票类走 get_stock_basic；ETF/INDEX 走 get_code_info。
        """
        return security_type in {"EXTRA_STOCK_A", "SH_STOCK_A", "SZ_STOCK_A"}

    async def _is_stock_basic_empty(self) -> bool:
        """检查 stock_basic 表是否为空."""
        try:
            from sqlalchemy import func, select

            async with self._db.session() as session:
                result = await session.execute(
                    select(func.count()).select_from(StockBasic).limit(1)
                )
                return result.scalar() == 0
        except Exception as e:
            logger.warning(f"检查 stock_basic 表失败: {e}")
            # 假设为空，强制同步
            return True

    # ========================================================================
    # 已退市ETF标记
    # ========================================================================
    async def _maybe_mark_delisted_etfs(self, today: date, security_type: str) -> None:
        """如有需要，标记已退市ETF（每周一次）.

        通过对比 get_hist_code_list 历史代码表与 get_code_info 当前代码表，
        找出已消失的ETF并在 stock_basic 表中标记 is_listed=3（终止上市）。
        """
        week_id = f"{today.year}-W{today.isocalendar()[1]:02d}"
        sync_type = "refdata_delisted_etf"

        if await self._state_manager.is_synced(sync_type, week_id):
            logger.info(f"已退市ETF标记 {week_id} 已完成，跳过")
            return

        await self._state_manager.mark_running(sync_type, week_id)

        success = await sync_with_retry(
            self._mark_delisted_etfs,
            f"delisted_etf {week_id}",
            today,
            security_type,
        )

        if success:
            await self._state_manager.mark_success(sync_type, week_id)
        else:
            await self._state_manager.mark_failed(sync_type, week_id, "All retries exhausted")

    async def _mark_delisted_etfs(self, today: date, security_type: str) -> None:
        """核心逻辑：对比历史/当前代码表，标记已退市ETF."""
        logger.info(f"[delisted_etf] 开始检查已退市ETF, security_type={security_type}")

        # 1. 获取历史所有ETF（从2006年第一个ETF上市起）
        start_date = 20060101
        end_date = int(today.strftime("%Y%m%d"))

        try:
            hist_codes = await self._reference_provider.get_hist_code_list(
                security_type, start_date, end_date, self._cache_dir
            )
        except Exception as e:
            logger.error(f"获取历史代码表失败: {e}")
            raise

        # 2. 获取当前ETF
        try:
            current_codes = await self._reference_provider.get_stock_list(security_type)
        except Exception as e:
            logger.error(f"获取当前代码表失败: {e}")
            raise

        # 3. 找出已消失的ETF
        disappeared = set(hist_codes) - set(current_codes)
        if not disappeared:
            logger.info("未发现已退市ETF")
            return

        logger.info(
            f"历史ETF {len(hist_codes)} 个，当前 {len(current_codes)} 个，"
            f"消失 {len(disappeared)} 个"
        )

        # 4. 查询 stock_basic 中仍未标记退市的 (is_listed != False)
        async with self._db.session() as session:
            stmt = select(StockBasic.symbol).where(
                StockBasic.security_type == security_type,
                or_(
                    StockBasic.is_listed.is_(None),
                    StockBasic.is_listed.is_(True),
                ),
                StockBasic.symbol.in_(list(disappeared)),
            )
            result = await session.execute(stmt)
            to_mark = list(result.scalars().all())

        if not to_mark:
            logger.info("无需标记（已退市ETF均已标记或不在表中）")
            return

        logger.info(f"需要标记 {len(to_mark)} 个已退市ETF")

        # 5. 更新 is_listed = False (终止上市)
        async with self._db.session() as session:
            stmt = (
                update(StockBasic)
                .where(StockBasic.symbol.in_(to_mark))
                .values(is_listed=False, updated_at=func.now())
            )
            await session.execute(stmt)

        logger.info(f"已标记 {len(to_mark)} 个ETF为退市状态")
