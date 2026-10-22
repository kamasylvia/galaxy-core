"""交易所指数数据存储适配器 — 实现 ExchangeIndexStorePort.

将 IndexConstituent / IndexWeight 值对象 UPSERT 到对应表。
镜像 FinancialDataStoreAdapter 的批处理 + on_conflict_do_update 模式。
"""

import logging
from dataclasses import asdict

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from galaxy_core.database.core.async_connection import AsyncDatabaseManager
from galaxy_core.database.models import IndexConstituent, IndexWeight
from galaxy_core.domain.value_objects import IndexConstituent as IndexConstituentVO
from galaxy_core.domain.value_objects import IndexWeight as IndexWeightVO
from galaxy_core.shared_kernel.exceptions import CacheError
from galaxy_core.shared_kernel.utils.config_loader import get_config

logger = logging.getLogger(__name__)

_CONSTITUENT_CONFLICT = ["index_code", "con_code", "in_date"]
_WEIGHT_CONFLICT = ["index_code", "con_code", "trade_date"]


class ExchangeIndexStoreAdapter:
    """ExchangeIndexStorePort 实现 — 交易所指数数据 UPSERT."""

    def __init__(self, db_manager: AsyncDatabaseManager) -> None:
        self._db = db_manager

    async def save_index_constituent(self, records: list[IndexConstituentVO]) -> int:
        """UPSERT 交易所指数成分股记录.

        冲突键: (index_code, con_code, in_date)
        """
        if not records:
            return 0

        data_list = [asdict(r) for r in records]
        # in_date 主键列不允许 None，过滤掉无 in_date 的记录
        data_list = [d for d in data_list if d.get("in_date") is not None]
        if not data_list:
            return 0

        return await self._upsert(IndexConstituent, _CONSTITUENT_CONFLICT, data_list)

    async def save_index_weight(self, records: list[IndexWeightVO]) -> int:
        """UPSERT 交易所指数日权重记录.

        冲突键: (index_code, con_code, trade_date)
        """
        if not records:
            return 0

        data_list = [asdict(r) for r in records]
        data_list = [d for d in data_list if d.get("trade_date") is not None]
        if not data_list:
            return 0

        return await self._upsert(IndexWeight, _WEIGHT_CONFLICT, data_list)

    async def is_index_constituent_empty(self) -> bool:
        """检查 index_constituent 表是否为空（首次强制同步判断）."""
        try:
            async with self._db.session() as session:
                result = await session.execute(
                    select(func.count()).select_from(IndexConstituent).limit(1)
                )
                return result.scalar() == 0
        except SQLAlchemyError as e:
            logger.warning(f"检查 index_constituent 表失败: {e}")
            return True

    async def _upsert(self, model, conflict_cols: list[str], data_list: list[dict]) -> int:
        """通用批处理 UPSERT（镜像 FinancialDataStoreAdapter.save 模式）."""
        from galaxy_core.shared_kernel.nocodb_schema import (
            NOCODB_SYSTEM_COLUMNS,
            coerce_nocodb_columns,
        )

        # nocodb 形态:in_date/out_date/trade_date 为 date 列,str 日期强转
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
                message=f"保存交易所指数数据失败: {e}",
                operation="save_exchange_index_data",
                key=f"{model.__tablename__}:{len(data_list)}条",
            ) from e

        logger.debug(f"保存 {len(data_list)} 条 {model.__tablename__} 记录")
        return len(data_list)
