"""交易所指数数据同步任务.

管理 2 个交易所指数 API:
- index_constituent: 周度同步（慢变维度），挂 dimensions 链
- index_weight: 日度 T+1 同步（仅 5 个指数），挂 daily 链

每个数据类型独立管理 SyncStateManager 状态，单种失败不阻断其余。

Phase 03(03-04):index_weight 增量窗口改用 last_sync_date 表
(_resolve_incremental_range, scope_key=None 全局),消除固定 7 天反模式。
"""

import logging
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from galaxy_core.application.scheduler.jobs._incremental_mixin import (
    IncrementalSyncMixin,
)
from galaxy_core.application.scheduler.state_manager import SyncStateManager
from galaxy_core.database.services.last_sync_date_store import LastSyncDateStore
from galaxy_core.domain.ports.exchange_index_provider import ExchangeIndexProviderPort
from galaxy_core.domain.ports.exchange_index_store import ExchangeIndexStorePort
from galaxy_core.domain.value_objects import IndexConstituent, IndexWeight
from galaxy_core.shared_kernel.utils.config_loader import get_section

logger = logging.getLogger(__name__)

# SDK 硬限制：get_index_weight 仅支持 5 个指数
_DEFAULT_WEIGHT_CODES = ["000016.SH", "000300.SH", "000905.SH", "000906.SH", "000852.SH"]

# Phase 03:index_weight 增量 last_sync_date 维度(全局,5 指数共用窗口)
_INDEX_WEIGHT_SYNC_TYPE = "index_weight"


class ExchangeIndexSyncJob(IncrementalSyncMixin):
    """交易所指数数据同步任务（成分股周度 + 权重日度）."""

    def __init__(
        self,
        state_manager: SyncStateManager,
        provider: ExchangeIndexProviderPort,
        store: ExchangeIndexStorePort,
        last_sync_store: LastSyncDateStore,
    ) -> None:
        self._state = state_manager
        self._provider = provider
        self._store = store
        self._last_sync_store = last_sync_store  # Phase 03 增量用
        self._config = get_section("index")
        self._scheduler_config = get_section("scheduler")
        raw_cache = get_section("amazing_data").get("local_path", "./data/local_cache/")
        self._cache_dir = str(Path(raw_cache).resolve())
        if raw_cache.endswith("/"):
            self._cache_dir += "/"

    # ------------------------------------------------------------------
    # 日度入口（行情/权重，紧跟 K线 day 之后）
    # ------------------------------------------------------------------
    async def run_daily(self, today: date) -> None:
        """日度同步：交易所指数日权重.

        仅交易日执行（由 scheduler 的 T+1 门控保证调用时机）。
        sync_type=exchange_index_weight, period_id=YYYYMMDD.
        """
        period_id = today.strftime("%Y%m%d")
        sync_type = "exchange_index_weight"

        # 暂停开关：AmazingData API 自 2026-05-14 起停供，SDK download_index_weight
        # 对空 DataFrame 后处理有 bug（sort_values('TRADE_DATE') KeyError），每日 ERROR。
        # 等 SDK 修复后置 disable_index_weight=false 即恢复自动同步（从 last_sync_date 续拉）。
        if self._config.get("disable_index_weight", False):
            logger.info(
                f"{sync_type} 已暂停（disable_index_weight=true），跳过自动同步"
            )
            return

        if await self._state.is_synced(sync_type, period_id):
            logger.info(f"{sync_type} {period_id} 已同步，跳过")
            return

        await self._state.mark_running(sync_type, period_id)
        try:
            saved = await self._sync_index_weight(today)
            await self._state.mark_success(sync_type, period_id, records_synced=saved)
            logger.info(f"{sync_type} 同步完成: {saved} 条权重记录")
        except Exception as e:
            await self._state.mark_failed(sync_type, period_id, str(e))
            logger.error(f"{sync_type} 同步失败: {e}")

    async def run_daily_force(self, today: date) -> None:
        """强制日度同步：绕过 is_synced 门控，但仍走状态标记.

        Per Phase 01 (manual CLI --force)：手动补数 / 回补历史交易日用。
        跑完仍写 success，避免下次 scheduler 重复跑。
        """
        period_id = today.strftime("%Y%m%d")
        sync_type = "exchange_index_weight"

        await self._state.mark_running(sync_type, period_id)
        try:
            saved = await self._sync_index_weight(today)
            await self._state.mark_success(sync_type, period_id, records_synced=saved)
            logger.info(f"{sync_type} 强制同步完成: {saved} 条权重记录")
        except Exception as e:
            await self._state.mark_failed(sync_type, period_id, str(e))
            logger.error(f"{sync_type} 强制同步失败: {e}")

    async def _sync_index_weight(self, today: date) -> int:
        """同步交易所指数日权重（SDK 仅支持 5 个指数）.

        Phase 03(03-04):增量窗口走 last_sync_date 表(scope_key=None 全局),
        空表首次从 DEFAULT_FIRST_SYNC_DATE=20130101 拉全历史。
        """
        codes = self._config.get("index_weight_codes", _DEFAULT_WEIGHT_CODES)
        # Phase 03 增量:替换原固定 7 天窗口
        begin_date, end_date = await self._resolve_incremental_range(
            _INDEX_WEIGHT_SYNC_TYPE, scope_key=None, today=today
        )

        data = await self._provider.get_index_weight(
            codes, self._cache_dir,
            is_local=False, begin_date=begin_date, end_date=end_date,
        )
        if not data:
            logger.info("交易所指数日权重返回空数据")
            return 0

        records: list[IndexWeight] = []
        for _index_code, df in data.items():
            if df is None or df.empty:
                continue
            records.extend(self._df_to_weight_records(df))

        saved = await self._store.save_index_weight(records)

        # Phase 03 D-08:有记录才推进 last_sync_date(空响应不推进)。
        # records trade_date 是 str YYYYMMDD,parse 为 date 后取 MAX。
        if records:
            max_str = max(
                (r.trade_date for r in records if r.trade_date),
                default=None,
            )
            if max_str:
                try:
                    max_date = date(
                        int(max_str[:4]), int(max_str[4:6]), int(max_str[6:8])
                    )
                    await self._last_sync_store.set_last_sync_date(
                        _INDEX_WEIGHT_SYNC_TYPE, None, max_date
                    )
                except (ValueError, IndexError):
                    logger.warning("index_weight trade_date 解析失败:%s", max_str)

        return saved

    # ------------------------------------------------------------------
    # 维度入口（成分股，周度，挂 refdata 之后）
    # ------------------------------------------------------------------
    async def run_dimensions(self, today: date) -> None:
        """周度同步：交易所指数成分股（慢变维度）.

        sync_type=exchange_index_constituent, period_id=YYYY-Www.
        """
        week_id = f"{today.year}-W{today.isocalendar()[1]:02d}"
        sync_type = "exchange_index_constituent"

        # 空表首次强制同步（镜像 ReferenceDataSyncJob 模式）
        is_empty = await self._store.is_index_constituent_empty()
        if is_empty:
            logger.info("index_constituent 表为空，强制首次同步")
        elif await self._state.is_synced(sync_type, week_id):
            logger.info(f"{sync_type} {week_id} 已同步，跳过")
            return

        await self._state.mark_running(sync_type, week_id)
        try:
            saved = await self._sync_index_constituent()
            await self._state.mark_success(sync_type, week_id, records_synced=saved)
            logger.info(f"{sync_type} 同步完成: {saved} 条成分股记录")
        except Exception as e:
            await self._state.mark_failed(sync_type, week_id, str(e))
            logger.error(f"{sync_type} 同步失败: {e}")

    async def run_dimensions_force(self, today: date) -> None:
        """强制维度同步：绕过 is_synced，保留表空强制首次同步分支.

        Per Phase 01 (manual CLI --force)。表空时仍走首次同步路径（不能因 force
        跳过空表初始化）。
        """
        week_id = f"{today.year}-W{today.isocalendar()[1]:02d}"
        sync_type = "exchange_index_constituent"

        is_empty = await self._store.is_index_constituent_empty()
        if is_empty:
            logger.info("index_constituent 表为空，强制首次同步")

        await self._state.mark_running(sync_type, week_id)
        try:
            saved = await self._sync_index_constituent()
            await self._state.mark_success(sync_type, week_id, records_synced=saved)
            logger.info(f"{sync_type} 强制同步完成: {saved} 条成分股记录")
        except Exception as e:
            await self._state.mark_failed(sync_type, week_id, str(e))
            logger.error(f"{sync_type} 强制同步失败: {e}")

    async def _sync_index_constituent(self) -> int:
        """同步交易所指数成分股（全量约 600 只指数）."""
        security_type = self._config.get("index_security_type", "EXTRA_INDEX_A")
        codes = await self._provider.get_index_code_list(security_type)
        if not codes:
            logger.warning(f"未获取到 {security_type} 指数代码列表")
            return 0

        logger.info(f"开始同步 {len(codes)} 个交易所指数成分股")
        data = await self._provider.get_index_constituent(
            codes, self._cache_dir, is_local=False,
        )
        if not data:
            logger.info("交易所指数成分股返回空数据")
            return 0

        records: list[IndexConstituent] = []
        empty_codes: list[str] = []
        for index_code, df in data.items():
            if df is None or df.empty:
                empty_codes.append(index_code)
                continue
            records.extend(self._df_to_constituent_records(df))

        if empty_codes:
            logger.debug(f"{len(empty_codes)} 个指数不支持/无成分股数据")

        return await self._store.save_index_constituent(records)

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

    @classmethod
    def _df_to_constituent_records(cls, df: pd.DataFrame) -> list[IndexConstituent]:
        """DataFrame → IndexConstituent 值对象列表."""
        df_reset = df.reset_index() if "INDEX_CODE" not in df.columns else df
        records: list[IndexConstituent] = []
        for _, row in df_reset.iterrows():
            in_date = cls._safe_str(row.get("INDATE"))
            records.append(IndexConstituent(
                index_code=cls._safe_str(row.get("INDEX_CODE")) or "",
                con_code=cls._safe_str(row.get("CON_CODE")) or "",
                in_date=in_date,
                out_date=cls._safe_str(row.get("OUTDATE")),
                index_name=cls._safe_str(row.get("INDEX_NAME")),
            ))
        return records

    @classmethod
    def _df_to_weight_records(cls, df: pd.DataFrame) -> list[IndexWeight]:
        """DataFrame → IndexWeight 值对象列表."""
        df_reset = df.reset_index() if "INDEX_CODE" not in df.columns else df
        records: list[IndexWeight] = []
        for _, row in df_reset.iterrows():
            trade_date = cls._safe_str(row.get("TRADE_DATE"))
            if trade_date is None:
                continue
            records.append(IndexWeight(
                index_code=cls._safe_str(row.get("INDEX_CODE")) or "",
                con_code=cls._safe_str(row.get("CON_CODE")) or "",
                trade_date=trade_date,
                total_share=cls._safe_float(row.get("TOTAL_SHARE")),
                free_share_ratio=cls._safe_float(row.get("FREE_SHARE_RATIO")),
                calc_share=cls._safe_float(row.get("CALC_SHARE")),
                weight_factor=cls._safe_float(row.get("WEIGHT_FACTOR")),
                weight=cls._safe_float(row.get("WEIGHT")),
                close=cls._safe_float(row.get("CLOSE")),
            ))
        return records
