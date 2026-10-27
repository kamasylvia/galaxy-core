"""K线查询结果封装模块."""

from dataclasses import dataclass
from typing import List, Dict, Optional

import pandas as pd

from .error import KlineError


@dataclass
class KlineSyncResult:
    """K线数据同步结果."""

    success_count: int  # 同步成功的代码数量
    synced_records: int  # 同步成功的数据条数
    failed_codes: List[str]  # 同步失败的代码列表
    message: str = ""  # 附加消息


@dataclass
class KlineItemResult:
    """单个证券K线查询结果."""

    code: str
    success: bool
    data: Optional[pd.DataFrame]
    error: Optional[KlineError] = None
    interval: Optional[str] = None  # 添加interval字段

    @classmethod
    def from_success(cls, code: str, data: pd.DataFrame, interval: str = None):
        """从成功结果创建实例."""
        return cls(code=code, success=True, data=data, interval=interval)

    @classmethod
    def from_error(cls, code: str, error: KlineError, interval: str = None):
        """从错误结果创建实例."""
        return cls(code=code, success=False, data=None, error=error, interval=interval)


@dataclass
class KlineQueryResult:
    """K线查询结果集合."""

    results: Dict[str, KlineItemResult]

    @property
    def success_count(self) -> int:
        """成功查询的数量."""
        return sum(1 for result in self.results.values() if result.success)

    @property
    def failed_count(self) -> int:
        """查询失败的数量."""
        return sum(1 for result in self.results.values() if not result.success)

    @property
    def all_success(self) -> bool:
        """是否全部成功."""
        return all(result.success for result in self.results.values())
