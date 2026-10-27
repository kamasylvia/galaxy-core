"""交易所指数数据存储端口."""

from typing import Protocol, runtime_checkable

from galaxy_core.domain.value_objects import IndexConstituent, IndexWeight


@runtime_checkable
class ExchangeIndexStorePort(Protocol):
    """交易所指数数据存储接口（async，AsyncSession 集中在 adapter）."""

    async def save_index_constituent(self, records: list[IndexConstituent]) -> int:
        """UPSERT 交易所指数成分股记录.

        冲突键: (index_code, con_code, in_date)

        Returns:
            实际写入的记录数
        """
        ...

    async def save_index_weight(self, records: list[IndexWeight]) -> int:
        """UPSERT 交易所指数日权重记录.

        冲突键: (index_code, con_code, trade_date)

        Returns:
            实际写入的记录数
        """
        ...

    async def is_index_constituent_empty(self) -> bool:
        """检查 index_constituent 表是否为空（用于首次强制全量同步判断）."""
        ...
