"""行业指数数据存储适配器 — 实现 IndustryIndexStorePort.

将 IndustryBaseInfo / IndustryConstituent / IndustryWeight / IndustryDaily
值对象 UPSERT 到对应表。

注意: IndustryDaily 模型的 trade_date 为 Date 类型（hypertable 要求），
      值对象为 YYYYMMDD 字符串，UPSERT 时转换。
"""

import logging
from dataclasses import asdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from galaxy_core.database.core.async_connection import AsyncDatabaseManager
from galaxy_core.database.models import (
    IndustryBaseInfo,
    IndustryConstituent,
    IndustryDaily,
    IndustryWeight,
)
from galaxy_core.domain.value_objects import (
    IndustryBaseInfo as IndustryBaseInfoVO,
)
from galaxy_core.domain.value_objects import (
    IndustryConstituent as IndustryConstituentVO,
)
from galaxy_core.domain.value_objects import (
    IndustryDaily as IndustryDailyVO,
)
from galaxy_core.domain.value_objects import (
    IndustryWeight as IndustryWeightVO,
)
from galaxy_core.shared_kernel.exceptions import CacheError
from galaxy_core.shared_kernel.nocodb_schema import NOCODB_SYSTEM_COLUMNS
from galaxy_core.shared_kernel.utils.config_loader import get_config

logger = logging.getLogger(__name__)

_BASE_INFO_CONFLICT = ["index_code", "industry_code"]
_CONSTITUENT_CONFLICT = ["index_code", "con_code", "in_date"]
_WEIGHT_CONFLICT = ["index_code", "con_code", "trade_date"]
_DAILY_CONFLICT = ["index_code", "trade_date"]


def _yyyymmdd_to_date(value: str | None) -> date | None:
    """YYYYMMDD 字符串 → date(nocodb 形态 trade_date=date 列)."""
    if value is None:
        return None
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError, IndexError:
        return None


class IndustryIndexStoreAdapter:
    """IndustryIndexStorePort 实现 — 行业指数数据 UPSERT."""

    def __init__(self, db_manager: AsyncDatabaseManager) -> None:
        self._db = db_manager

    async def save_industry_base_info(self, records: list[IndustryBaseInfoVO]) -> int:
        """UPSERT 行业指数基本信息. 冲突键: (index_code, industry_code)."""
        if not records:
            return 0
        data_list = [asdict(r) for r in records]
        data_list = [d for d in data_list if d.get("index_code") and d.get("industry_code")]
        return await self._upsert(IndustryBaseInfo, _BASE_INFO_CONFLICT, data_list)

    async def save_industry_constituent(self, records: list[IndustryConstituentVO]) -> int:
        """UPSERT 行业指数成分股. 冲突键: (index_code, con_code, in_date)."""
        if not records:
            return 0
        data_list = [asdict(r) for r in records]
        data_list = [d for d in data_list if d.get("in_date") is not None]
        return await self._upsert(IndustryConstituent, _CONSTITUENT_CONFLICT, data_list)

    async def save_industry_weight(self, records: list[IndustryWeightVO]) -> int:
        """UPSERT 行业指数日权重. 冲突键: (index_code, con_code, trade_date)."""
        if not records:
            return 0
        data_list = [asdict(r) for r in records]
        data_list = [d for d in data_list if d.get("trade_date") is not None]
        return await self._upsert(IndustryWeight, _WEIGHT_CONFLICT, data_list)

    async def save_industry_daily(self, records: list[IndustryDailyVO]) -> int:
        """UPSERT 行业指数日行情. 冲突键: (index_code, trade_date).

        值对象 trade_date 为 YYYYMMDD 字符串，模型为 Date，此处转换。
        """
        if not records:
            return 0
        data_list = [asdict(r) for r in records]
        converted = []
        for d in data_list:
            td = _yyyymmdd_to_date(d.get("trade_date"))
            if td is None:
                continue
            d["trade_date"] = td
            converted.append(d)
        return await self._upsert(IndustryDaily, _DAILY_CONFLICT, converted)

    async def get_industry_daily_last_date(self, index_code: str) -> str | None:
        """获取行业指数日行情的最后交易日（增量同步起点）."""
        try:
            async with self._db.session() as session:
                stmt = select(func.max(IndustryDaily.trade_date)).where(
                    IndustryDaily.index_code == index_code
                )
                result = await session.execute(stmt)
                last = result.scalar()
                if last is None:
                    return None
                # Date → YYYYMMDD 字符串
                return last.strftime("%Y%m%d") if hasattr(last, "strftime") else str(last)
        except SQLAlchemyError as e:
            logger.warning(f"查询 industry_daily 最后日期失败: {e}")
            return None

    async def get_industry_daily_max_last_date(self) -> str | None:
        """获取所有行业指数日行情的全局最后交易日(批量,非 per-code)。

        用于 _resolve_daily_range 统一窗口计算(2026-07-28 修复):
        原方案只查 codes[0] 的 last_date,若 codes[0] 恰好是最久未同步的 code,
        所有 codes 共用一个过宽的 window。改用全局 MAX(trade_date) 让 window
        基于最新已同步日,避免无谓的大窗口查询。

        Returns:
            YYYYMMDD 字符串,无数据返 None。
        """
        try:
            async with self._db.session() as session:
                stmt = select(func.max(IndustryDaily.trade_date))
                result = await session.execute(stmt)
                last = result.scalar()
                if last is None:
                    return None
                return last.strftime("%Y%m%d") if hasattr(last, "strftime") else str(last)
        except SQLAlchemyError as e:
            logger.warning(f"查询 industry_daily 全局最后日期失败: {e}")
            return None

    async def is_industry_base_info_empty(self) -> bool:
        """检查 industry_base_info 表是否为空（首次强制同步判断）."""
        try:
            async with self._db.session() as session:
                result = await session.execute(
                    select(func.count()).select_from(IndustryBaseInfo).limit(1)
                )
                return result.scalar() == 0
        except SQLAlchemyError as e:
            logger.warning(f"检查 industry_base_info 表失败: {e}")
            return True

    async def _upsert(self, model, conflict_cols: list[str], data_list: list[dict]) -> int:
        """通用批处理 UPSERT（镜像 FinancialDataStoreAdapter.save 模式）."""
        if not data_list:
            return 0

        # nocodb 形态:date 列(str YYYYMMDD/YYYY-MM-DD/datetime)统一强转,
        # 覆盖 weight 的 trade_date 与 constituent 的 in_date/out_date 等
        from galaxy_core.shared_kernel.nocodb_schema import coerce_nocodb_columns

        data_list = coerce_nocodb_columns(model, data_list)

        # 批内按冲突键去重（保留最后出现）
        seen: dict[tuple, dict] = {}
        for row in data_list:
            key = tuple(row.get(c) for c in conflict_cols)
            seen[key] = row
        data_list = list(seen.values())

        batch_size = get_config("sync.batch", "db_upsert", 100)
        if not isinstance(batch_size, int):
            batch_size = 100

        try:
            async with self._db.session() as session:
                for i in range(0, len(data_list), batch_size):
                    batch = data_list[i : i + batch_size]
                    stmt = pg_insert(model).values(batch)
                    update_dict = {
                        col.name: stmt.excluded[col.name]
                        for col in model.__table__.columns
                        if col.name not in conflict_cols and col.name not in NOCODB_SYSTEM_COLUMNS
                    }
                    # nocodb 审计:冲突更新分支刷新 updated_at(出站增量 watermark 用;
                    # INSERT 分支由 DB DEFAULT now() 填充)
                    update_dict["updated_at"] = func.now()
                    upsert_stmt = stmt.on_conflict_do_update(
                        index_elements=conflict_cols,
                        set_=update_dict,
                    )
                    await session.execute(upsert_stmt)
        except SQLAlchemyError as e:
            raise CacheError(
                message=f"保存行业指数数据失败: {e}",
                operation="save_industry_index_data",
                key=f"{model.__tablename__}:{len(data_list)}条",
            ) from e

        logger.debug(f"保存 {len(data_list)} 条 {model.__tablename__} 记录")
        return len(data_list)
