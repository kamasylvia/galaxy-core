"""行业指数数据存储端口."""

from typing import Protocol, runtime_checkable

from galaxy_core.domain.value_objects import (
    IndustryBaseInfo,
    IndustryConstituent,
    IndustryDaily,
    IndustryWeight,
)


@runtime_checkable
class IndustryIndexStorePort(Protocol):
    """行业指数数据存储接口（async，AsyncSession 集中在 adapter）."""

    async def save_industry_base_info(self, records: list[IndustryBaseInfo]) -> int:
        """UPSERT 行业指数基本信息.

        冲突键: (index_code, industry_code)

        Returns:
            实际写入的记录数
        """
        ...

    async def save_industry_constituent(self, records: list[IndustryConstituent]) -> int:
        """UPSERT 行业指数成分股.

        冲突键: (index_code, con_code, in_date)

        Returns:
            实际写入的记录数
        """
        ...

    async def save_industry_weight(self, records: list[IndustryWeight]) -> int:
        """UPSERT 行业指数日权重.

        冲突键: (index_code, con_code, trade_date)

        Returns:
            实际写入的记录数
        """
        ...

    async def save_industry_daily(self, records: list[IndustryDaily]) -> int:
        """UPSERT 行业指数日行情.

        冲突键: (index_code, trade_date)

        Returns:
            实际写入的记录数
        """
        ...

    async def get_industry_daily_last_date(self, index_code: str) -> str | None:
        """获取行业指数日行情的最后交易日（用于增量同步起点）.

        Args:
            index_code: 行业指数代码

        Returns:
            最后交易日期 YYYYMMDD，无数据则 None
        """
        ...

    async def is_industry_base_info_empty(self) -> bool:
        """检查 industry_base_info 表是否为空（用于首次强制全量同步判断）."""
        ...
