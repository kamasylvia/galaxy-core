"""Reference data sync job for scheduler.

Integrates P0 data synchronization into AutoSyncScheduler:
- stock_basic: 每周检查新增/退市代码
- stock_status: 日频增量同步最新交易日（仅 A 股）
- backward_factor: 月度全量重新同步

Runs sequentially after K-line sync (API 不支持并发).
"""

import asyncio
import logging
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from galaxy_db_sync.amazing_data.api.client import amazing_data_client
from galaxy_db_sync.application.scheduler.retry_handler import sync_with_retry
from galaxy_db_sync.application.scheduler.state_manager import SyncStateManager
from galaxy_db_sync.database.core.async_connection import async_db_manager
from galaxy_db_sync.database.models import BackwardFactor, StockBasic, StockStatus
from galaxy_db_sync.database.services.trading_calendar import trading_calendar_service
from galaxy_db_sync.shared_kernel.utils.config_loader import get_section

logger = logging.getLogger(__name__)


class ReferenceDataSyncJob:
    """Reference data (P0) synchronization job.

    运行在 K-line sync 之后，共享 API 连接（API 不支持并发）。
    各表独立追踪同步状态，不按 security_type 拆分。
    """

    def __init__(self, state_manager: SyncStateManager) -> None:
        self._state_manager = state_manager
        self._config = get_section("scheduler")
        self._sync_config = get_section("sync")
        self._batch_size = self._sync_config.get("batch_size", 200)
        # SDK 文档要求 local_path 为绝对路径
        raw_cache = get_section("amazing_data").get("local_path", "./data/local_cache/")
        self._cache_dir = str(Path(raw_cache).resolve())

    # ========================================================================
    # 主入口
    # ========================================================================
    async def run(self, today: date) -> None:
        """Run reference data sync checks for today.

        根据各表频率决定是否执行同步：
        - stock_basic: 每周一次
        - stock_status: 每个交易日一次（仅 A 股）
        - backward_factor: 每月一次
        """
        logger.info("=" * 50)
        logger.info("ReferenceDataSyncJob 开始检查")
        logger.info("=" * 50)

        security_type = self._config.get("security_type", "EXTRA_ETF")

        # 1. stock_basic: 每周
        await self._maybe_sync_stock_basic(today, security_type)

        # 2. stock_status: 日频（仅股票类型）
        if self._is_stock_security_type(security_type):
            await self._maybe_sync_stock_status(today, security_type)
        else:
            logger.info("当前 security_type 为 ETF，跳过 stock_status 同步")

        # 3. backward_factor: 月度
        await self._maybe_sync_backward_factor(today, security_type)

        logger.info("=" * 50)
        logger.info("ReferenceDataSyncJob 检查完成")
        logger.info("=" * 50)

    # ========================================================================
    # stock_basic
    # ========================================================================
    async def _maybe_sync_stock_basic(self, today: date, security_type: str) -> None:
        """如有需要，同步证券基础信息（每周）."""
        week_id = f"{today.year}-W{today.isocalendar()[1]:02d}"
        sync_type = "refdata_stock_basic"

        if await self._state_manager.is_synced(sync_type, week_id):
            logger.info(f"stock_basic {week_id} 已同步，跳过")
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
        else:
            await self._state_manager.mark_failed(sync_type, week_id, "All retries exhausted")

    async def _sync_stock_basic(self, today: date, security_type: str, week_id: str) -> None:
        """同步证券基础信息（异步实现）."""
        logger.info(f"[stock_basic] 开始同步 {week_id}, security_type={security_type}")

        # 获取代码列表（get_stock_list 内部调用 get_code_info，index 为证券代码）
        stock_df = await amazing_data_client.get_stock_list_async(security_type)
        codes = stock_df.index.tolist()
        logger.info(f"当前 {security_type} 数量: {len(codes)}")

        all_records = []
        for i in range(0, len(codes), self._batch_size):
            batch = codes[i : i + self._batch_size]
            logger.info(
                f"  获取基础信息: {i + 1} - {min(i + self._batch_size, len(codes))}"
            )

            df = await asyncio.to_thread(
                amazing_data_client.get_stock_basic,
                batch,
            )
            if df is None or df.empty:
                continue

            for _, row in df.iterrows():
                code = row.get("MARKET_CODE") or row.get("code")
                if not code:
                    continue

                list_date = self._parse_date(row.get("LISTDATE"))

                record = {
                    "symbol": code,
                    "security_name": row.get("SECURITY_NAME"),
                    "comp_name": row.get("COMP_NAME"),
                    "pinyin": row.get("PINYIN"),
                    "list_date": list_date,
                    "delist_date": self._parse_date(row.get("DELISTDATE")),
                    "security_type": security_type,
                }
                all_records.append(record)

        logger.info(f"共获取 {len(all_records)} 条基础信息记录")
        if not all_records:
            return

        saved = await self._upsert_stock_basic(all_records)
        logger.info(f"保存/更新 stock_basic 记录: {saved}")

    # ========================================================================
    # stock_status
    # ========================================================================
    async def _maybe_sync_stock_status(self, today: date, security_type: str) -> None:
        """如有需要，同步历史证券状态（日频，仅交易日）."""
        date_id = today.strftime("%Y%m%d")
        sync_type = "refdata_stock_status"

        # 非交易日跳过
        trading_days = await trading_calendar_service.get_trading_days_async(today, today)
        if not trading_days:
            logger.info(f"{today} 非交易日，跳过 stock_status 同步")
            return

        if await self._state_manager.is_synced(sync_type, date_id):
            logger.info(f"stock_status {date_id} 已同步，跳过")
            return

        await self._state_manager.mark_running(sync_type, date_id)

        success = await sync_with_retry(
            self._sync_stock_status,
            f"stock_status {date_id}",
            today,
            security_type,
            date_id,
        )

        if success:
            await self._state_manager.mark_success(sync_type, date_id)
        else:
            await self._state_manager.mark_failed(sync_type, date_id, "All retries exhausted")

    async def _sync_stock_status(self, today: date, security_type: str, date_id: str) -> None:
        """同步历史证券状态（异步实现，日频）.

        注：API 的 begin_date/end_date 参数仅用于本地数据缓存方案，
        is_local=False 时无法按日期过滤服务端数据。日频同步即全量拉取后 UPSERT 去重。
        """
        logger.info(f"[stock_status] 开始同步 {date_id}, security_type={security_type}")

        # 获取代码列表
        stock_df = await amazing_data_client.get_stock_list_async(security_type)
        codes = stock_df.index.tolist()
        logger.info(f"代码数量: {len(codes)}")

        all_records = []
        total_batches = (len(codes) + self._batch_size - 1) // self._batch_size

        for i in range(0, len(codes), self._batch_size):
            batch = codes[i : i + self._batch_size]
            batch_num = i // self._batch_size + 1
            logger.info(
                f"  获取证券状态: batch {batch_num}/{total_batches} ({len(batch)} 只)"
            )

            try:
                result = await asyncio.to_thread(
                    amazing_data_client.get_history_stock_status,
                    code_list=batch,
                    local_path=self._cache_dir,
                    is_local=False,
                )
            except Exception as e:
                logger.error(f"    批次 {batch_num} 失败: {e}")
                raise  # 让 retry handler 处理

            if not isinstance(result, dict):
                logger.warning(f"    返回类型非 dict: {type(result)}")
                continue

            for code, df in result.items():
                if df is None or df.empty:
                    continue
                records = self._parse_stock_status_df(code, df)
                all_records.extend(records)

            if batch_num % 5 == 0:
                logger.info(f"  累计记录数: {len(all_records)}")

        logger.info(f"共获取 {len(all_records)} 条状态记录")
        if not all_records:
            return

        saved = await self._upsert_stock_status(all_records)
        logger.info(f"保存/更新 stock_status 记录: {saved}")

    # ========================================================================
    # backward_factor
    # ========================================================================
    async def _maybe_sync_backward_factor(self, today: date, security_type: str) -> None:
        """如有需要，同步后复权因子（月度全量）."""
        month_id = f"{today.year}-{today.month:02d}"
        sync_type = "refdata_backward_factor"

        if await self._state_manager.is_synced(sync_type, month_id):
            logger.info(f"backward_factor {month_id} 已同步，跳过")
            return

        await self._state_manager.mark_running(sync_type, month_id)

        success = await sync_with_retry(
            self._sync_backward_factor,
            f"backward_factor {month_id}",
            today,
            security_type,
            month_id,
        )

        if success:
            await self._state_manager.mark_success(sync_type, month_id)
        else:
            await self._state_manager.mark_failed(sync_type, month_id, "All retries exhausted")

    async def _sync_backward_factor(self, today: date, security_type: str, month_id: str) -> None:
        """同步后复权因子（异步实现，逐 batch UPSERT 控制内存）."""
        logger.info(f"[backward_factor] 开始同步 {month_id}, security_type={security_type}")

        # 获取代码列表
        stock_df = await amazing_data_client.get_stock_list_async(security_type)
        codes = stock_df.index.tolist()
        logger.info(f"代码数量: {len(codes)}")

        total_batches = (len(codes) + self._batch_size - 1) // self._batch_size
        total_saved = 0

        for i in range(0, len(codes), self._batch_size):
            batch = codes[i : i + self._batch_size]
            batch_num = i // self._batch_size + 1
            logger.info(
                f"  获取复权因子: batch {batch_num}/{total_batches} ({len(batch)} 只)"
            )

            try:
                df = await asyncio.to_thread(
                    amazing_data_client.get_backward_factor,
                    code_list=batch,
                    local_path=self._cache_dir,
                    is_local=False,
                )
            except Exception as e:
                logger.error(f"    批次 {batch_num} 失败: {e}")
                raise

            if df is None or df.empty:
                logger.warning(f"    批次 {batch_num} 返回空数据")
                continue

            records = self._parse_backward_factor_df(df)
            if records:
                saved = await self._upsert_backward_factor(records)
                total_saved += saved

            if batch_num % 5 == 0:
                logger.info(f"  累计保存记录数: {total_saved}")

        logger.info(f"保存/更新 backward_factor 记录: {total_saved}")

    # ========================================================================
    # UPSERT 操作
    # ========================================================================
    async def _upsert_stock_basic(self, records: list[dict]) -> int:
        """异步批量 UPSERT stock_basic 记录."""
        if not records:
            return 0

        batch_size = 3000
        total = 0
        async with async_db_manager.session() as session:
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]
                stmt = pg_insert(StockBasic).values(batch)
                upsert_stmt = stmt.on_conflict_do_update(
                    index_elements=["symbol"],
                    set_={
                        "security_name": stmt.excluded.security_name,
                        "comp_name": stmt.excluded.comp_name,
                        "pinyin": stmt.excluded.pinyin,
                        "list_date": stmt.excluded.list_date,
                        "delist_date": stmt.excluded.delist_date,
                        "security_type": stmt.excluded.security_type,
                        "updated_at": func.now(),
                    },
                )
                await session.execute(upsert_stmt)
                total += len(batch)
        return total

    async def _upsert_stock_status(self, records: list[dict]) -> int:
        """异步批量 UPSERT stock_status 记录."""
        if not records:
            return 0

        # 去重
        seen = {}
        for r in records:
            key = (r["symbol"], r["trade_date"])
            seen[key] = r
        deduped = list(seen.values())

        batch_size = 5000
        total = 0
        async with async_db_manager.session() as session:
            for i in range(0, len(deduped), batch_size):
                batch = deduped[i : i + batch_size]
                stmt = pg_insert(StockStatus).values(batch)
                upsert_stmt = stmt.on_conflict_do_update(
                    index_elements=["symbol", "trade_date"],
                    set_={
                        "preclose": stmt.excluded.preclose,
                        "high_limited": stmt.excluded.high_limited,
                        "low_limited": stmt.excluded.low_limited,
                        "is_st": stmt.excluded.is_st,
                        "is_susp": stmt.excluded.is_susp,
                        "is_xr": stmt.excluded.is_xr,
                        "is_wd": stmt.excluded.is_wd,
                        "updated_at": func.now(),
                    },
                )
                await session.execute(upsert_stmt)
                total += len(batch)
        return total

    async def _upsert_backward_factor(self, records: list[dict]) -> int:
        """异步批量 UPSERT backward_factor 记录."""
        if not records:
            return 0

        # 去重
        seen = {}
        for r in records:
            key = (r["symbol"], r["trade_date"])
            seen[key] = r
        deduped = list(seen.values())

        batch_size = 5000
        total = 0
        async with async_db_manager.session() as session:
            for i in range(0, len(deduped), batch_size):
                batch = deduped[i : i + batch_size]
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

    def _parse_stock_status_df(self, code: str, df: pd.DataFrame) -> list[dict]:
        """将 stock_status DataFrame 转换为记录列表."""
        records = []
        for _, row in df.iterrows():
            trade_date = self._parse_date(row.get("TRADE_DATE"))
            if trade_date is None:
                continue
            records.append(
                {
                    "symbol": code,
                    "trade_date": trade_date,
                    "preclose": self._to_float(row.get("PRECLOSE")),
                    "high_limited": self._to_float(row.get("HIGH_LIMITED")),
                    "low_limited": self._to_float(row.get("LOW_LIMITED")),
                    "is_st": self._to_bool(row.get("IS_ST_SEC")),
                    "is_susp": self._to_bool(row.get("IS_SUSP_SEC")),
                    "is_xr": self._to_bool(row.get("IS_XR_SEC")),
                    "is_wd": self._to_bool(row.get("IS_WD_SEC")),
                }
            )
        return records

    def _parse_backward_factor_df(self, df: pd.DataFrame) -> list[dict]:
        """将 backward_factor DataFrame 转换为记录列表.

        DataFrame 格式: index=日期, columns=股票代码
        """
        records = []
        df.index = pd.to_datetime(df.index)
        for trade_dt in df.index:
            trade_date = trade_dt.date()
            for col in df.columns:
                val = df.loc[trade_dt, col]
                if pd.isna(val):
                    continue
                records.append(
                    {
                        "symbol": col,
                        "trade_date": trade_date,
                        "factor": float(val),
                    }
                )
        return records

    # ========================================================================
    # 工具
    # ========================================================================
    @staticmethod
    def _is_stock_security_type(security_type: str) -> bool:
        """判断是否为股票类 security_type（非 ETF/指数/可转债）."""
        stock_types = {
            "EXTRA_STOCK_A",
            "EXTRA_STOCK_A_SH_SZ",
            "SH_A",
            "SZ_A",
            "BJ_A",
        }
        return security_type in stock_types
