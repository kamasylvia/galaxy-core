"""财务数据存储端口."""

from typing import Protocol, runtime_checkable

from galaxy_core.domain.value_objects import FinancialDataType, FinancialRecord


@runtime_checkable
class FinancialDataStorePort(Protocol):
    """财务数据存储接口 — 对接 PostgreSQL（async）.

    方法:
        save: UPSERT 财务记录，去重键 (symbol, reporting_period, statement_type)，
              保留 actual_ann_date 最新的记录
        get_last_sync_periods: 查询 symbol 已同步的最新 reporting_period（YYYYMMDD）
        set_last_sync_periods: 批量更新 last_sync_period
    """

    async def save(
        self,
        records: list[FinancialRecord],
        data_type: FinancialDataType,
    ) -> None: ...

    async def get_last_sync_periods(
        self,
        symbols: list[str],
        data_type: FinancialDataType,
    ) -> dict[str, str | None]: ...

    async def set_last_sync_periods(
        self,
        symbol_periods: dict[str, str],
        data_type: FinancialDataType,
    ) -> None: ...
