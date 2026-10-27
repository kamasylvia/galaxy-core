"""财务数据存储适配器 — 实现 FinancialDataStorePort.

将 FinancialRecord UPSERT 到对应的财务数据表，并通过扩展的
last_sync_date 表（data_type 列）管理每个 symbol 的最新同步报告期。
"""

import logging
from datetime import date

from sqlalchemy import String, and_, bindparam, func, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from galaxy_core.database.core.async_connection import AsyncDatabaseManager
from galaxy_core.database.models.financial_data import (
    BalanceSheet,
    CashFlow,
    Dividend,
    Income,
    ProfitExpress,
    ProfitNotice,
)
from galaxy_core.domain.value_objects import FinancialDataType, FinancialRecord
from galaxy_core.shared_kernel.exceptions import CacheError

logger = logging.getLogger(__name__)

# 财务数据类型 → ORM 模型映射
_DATA_TYPE_MODEL_MAP: dict[FinancialDataType, type] = {
    FinancialDataType.BALANCE_SHEET: BalanceSheet,
    FinancialDataType.CASH_FLOW: CashFlow,
    FinancialDataType.INCOME: Income,
    FinancialDataType.PROFIT_EXPRESS: ProfitExpress,
    FinancialDataType.PROFIT_NOTICE: ProfitNotice,
    FinancialDataType.DIVIDEND: Dividend,
}

# 三大报表的冲突键（symbol, reporting_period, statement_type）
_THREE_STATEMENT_CONFLICT = ["symbol", "reporting_period", "statement_type"]

# 快报的冲突键（symbol, reporting_period）
_EXPRESS_CONFLICT = ["symbol", "reporting_period"]

# 预告的冲突键（symbol, reporting_period, ann_date）
_NOTICE_CONFLICT = ["symbol", "reporting_period", "ann_date"]

# 分红配送的冲突键（symbol, reporting_period, ann_date）
_DIVIDEND_CONFLICT = ["symbol", "reporting_period", "ann_date"]


class FinancialDataStoreAdapter:
    """FinancialDataStorePort 实现 — 财务数据 UPSERT + last_sync_period 管理."""

    def __init__(self, db_manager: AsyncDatabaseManager) -> None:
        self._db = db_manager

    async def save(
        self,
        records: list[FinancialRecord],
        data_type: FinancialDataType,
    ) -> None:
        """UPSERT 财务记录到对应表.

        根据 data_type 选择目标模型。records 为空时直接返回。
        FinancialRecord.fields dict 中的所有字段展开为列名（snake_case），
        元数据字段（symbol, reporting_period 等）优先级高于 fields。

        去重键:
        - 三大报表: (symbol, reporting_period, statement_type)
        - 快报: (symbol, reporting_period)
        - 预告: (symbol, reporting_period, ann_date)
        - 分红配送: (symbol, reporting_period, ann_date)

        Args:
            records: FinancialRecord 列表
            data_type: 财务数据类型
        """
        if not records:
            return

        model = _DATA_TYPE_MODEL_MAP.get(data_type)
        if model is None:
            raise ValueError(f"未知的财务数据类型: {data_type}")

        # 确定冲突键
        if data_type == FinancialDataType.PROFIT_NOTICE:
            conflict_cols = _NOTICE_CONFLICT
        elif data_type == FinancialDataType.DIVIDEND:
            conflict_cols = _DIVIDEND_CONFLICT
        elif data_type == FinancialDataType.PROFIT_EXPRESS:
            conflict_cols = _EXPRESS_CONFLICT
        else:
            conflict_cols = _THREE_STATEMENT_CONFLICT

        # FinancialRecord → list[dict]
        data_list = self._records_to_dicts(records, model)

        # nocodb 形态:reporting_period/ann_date 等为 date 列,str 日期强转
        from galaxy_core.shared_kernel.nocodb_schema import (
            NOCODB_SYSTEM_COLUMNS,
            coerce_nocodb_columns,
        )

        data_list = coerce_nocodb_columns(model, data_list)

        if not data_list:
            return

        # 去重：同一 batch 内按冲突键去重（保留最后出现）
        seen: dict[tuple, dict] = {}
        for row in data_list:
            key = tuple(row.get(c) for c in conflict_cols)
            seen[key] = row
        data_list = list(seen.values())

        # 分批处理
        from galaxy_core.shared_kernel.utils.config_loader import get_config

        batch_size = get_config("sync.batch", "db_upsert", 100)
        if not isinstance(batch_size, int):
            batch_size = 100

        try:
            async with self._db.session() as session:
                for i in range(0, len(data_list), batch_size):
                    batch = data_list[i : i + batch_size]
                    stmt = pg_insert(model).values(batch)

                    # 更新策略：简单覆盖所有非 PK 列
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
                message=f"保存财务数据失败: {e}",
                operation="save_financial_data",
                key=f"{data_type.value}:{len(records)}条",
            ) from e

        logger.debug(f"保存 {len(data_list)} 条财务数据，data_type={data_type.value}")

    async def get_last_sync_periods(
        self,
        symbols: list[str],
        data_type: FinancialDataType,
    ) -> dict[str, str | None]:
        """查询 symbol 已同步的最新 reporting_period.

        从扩展的 last_sync_date 表查询，data_type 列匹配，interval 列为 NULL。
        last_sync_date 存储为 date 对象，返回时转为 YYYYMMDD 字符串。

        Args:
            symbols: 证券代码列表
            data_type: 财务数据类型

        Returns:
            dict[symbol, reporting_period_str]，未查到的 symbol 不包含在返回中
        """
        if not symbols:
            return {}

        from galaxy_core.database.models.last_sync_date import LastSyncDate

        found: dict[str, str] = {}
        try:
            async with self._db.session() as session:
                stmt = select(LastSyncDate).where(
                    and_(
                        LastSyncDate.data_type == data_type.value,
                        LastSyncDate.symbol
                        == func.any(bindparam("symbols", value=symbols, type_=ARRAY(String))),
                    )
                )
                result = await session.execute(stmt)
                rows = result.scalars().all()
                for row in rows:
                    # date → YYYYMMDD 字符串
                    found[row.symbol] = row.last_sync_date.strftime("%Y%m%d")
        except SQLAlchemyError as e:
            raise CacheError(
                message=f"查询最后同步报告期失败: {e}",
                operation="get_last_sync_periods",
                key=f"{len(symbols)} symbols:{data_type.value}",
            ) from e

        return found

    async def set_last_sync_periods(
        self,
        symbol_periods: dict[str, str],
        data_type: FinancialDataType,
    ) -> None:
        """批量 upsert 最后同步报告期.

        将 YYYYMMDD 字符串转为 date 对象存入 last_sync_date 列。
        data_type 列有值，interval 列为 NULL。

        Args:
            symbol_periods: {symbol: reporting_period_str} 映射
            data_type: 财务数据类型
        """
        if not symbol_periods:
            return

        from galaxy_core.database.models.last_sync_date import LastSyncDate

        records = []
        for s, period_str in symbol_periods.items():
            # YYYYMMDD 字符串 → date 对象
            period_date = date(
                int(period_str[:4]),
                int(period_str[4:6]),
                int(period_str[6:8]),
            )
            records.append(
                {
                    "symbol": s,
                    "data_type": data_type.value,
                    "interval": None,
                    "last_sync_date": period_date,
                }
            )

        try:
            async with self._db.session() as session:
                stmt = pg_insert(LastSyncDate).values(records)
                upsert_stmt = stmt.on_conflict_do_update(
                    index_elements=["symbol", "data_type"],
                    set_={
                        "last_sync_date": stmt.excluded.last_sync_date,
                        "updated_at": func.now(),
                    },
                )
                await session.execute(upsert_stmt)
        except SQLAlchemyError as e:
            raise CacheError(
                message=f"更新最后同步报告期失败: {e}",
                operation="set_last_sync_periods",
                key=f"{len(symbol_periods)} symbols:{data_type.value}",
            ) from e

        logger.debug(
            f"更新 {len(symbol_periods)} 个 symbol 的 last_sync_period, data_type={data_type.value}"
        )

    def _records_to_dicts(
        self,
        records: list[FinancialRecord],
        model: type,
    ) -> list[dict]:
        """将 FinancialRecord 列表转为 dict 列表.

        元数据字段（symbol, reporting_period, statement_type, actual_ann_date 等）
        优先级高于 fields dict，防止 fields 中包含同名键时覆盖。
        仅包含模型中实际存在的列名。
        """
        # 获取模型所有列名
        model_columns = {col.name for col in model.__table__.columns}
        # 不需要手动写入的列（由 DB 自动管理）
        auto_columns = {"created_at", "updated_at"}

        result: list[dict] = []
        for rec in records:
            row: dict = {}

            # 先展开 fields dict 中的所有字段
            for key, value in rec.fields.items():
                if key in model_columns and key not in auto_columns:
                    row[key] = value

            # 元数据字段覆盖（优先级高于 fields）
            if "symbol" in model_columns:
                row["symbol"] = rec.symbol
            if "reporting_period" in model_columns:
                row["reporting_period"] = rec.reporting_period
            if "ann_date" in model_columns:
                row["ann_date"] = rec.ann_date
            if "actual_ann_date" in model_columns:
                row["actual_ann_date"] = rec.actual_ann_date
            if "statement_type" in model_columns:
                row["statement_type"] = rec.statement_type

            result.append(row)

        return result
