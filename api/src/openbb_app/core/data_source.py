import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class DataSource(ABC):

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return data source provider name."""
        pass

    def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1d",
    ) -> list[dict[str, Any]]:
        """获取历史数据(子类实现:AmazingDataSource 直读 TimescaleDB)."""
        raise NotImplementedError

    def _normalize_symbol(self, symbol: str) -> str:
        """符号标准化钩子，子类可覆盖此方法"""
        return symbol

    def _convert_interval(self, interval: str) -> str:
        """转换时间间隔"""
        interval_map = {"1d": "1d", "1w": "1w", "1m": "1m"}
        return interval_map.get(interval, "1d")

    def _format_data(
        self,
        data: dict[Any, Any],
        interval: str,
    ) -> list[dict[str, Any]]:
        """格式化数据"""
        formatted_data: list[dict[str, Any]] = []
        # Data is in columnar format, convert to row-based format
        if not data or not any(isinstance(v, list) for v in data.values()):
            return formatted_data

        # Get the number of rows from the first list
        num_rows = len(next((v for v in data.values() if isinstance(v, list)), []))

        for i in range(num_rows):
            formatted_item = {
                "date": (
                    data.get("date", [None])[i]
                    if i < len(data.get("date", []))
                    else None
                ),
                "open": (
                    data.get("open", [None])[i]
                    if i < len(data.get("open", []))
                    else None
                ),
                "high": (
                    data.get("high", [None])[i]
                    if i < len(data.get("high", []))
                    else None
                ),
                "low": (
                    data.get("low", [None])[i] if i < len(data.get("low", [])) else None
                ),
                "close": (
                    data.get("close", [None])[i]
                    if i < len(data.get("close", []))
                    else None
                ),
                "volume": (
                    data.get("volume", [None])[i]
                    if i < len(data.get("volume", []))
                    else None
                ),
                "amount": (
                    data.get("amount", [None])[i]
                    if i < len(data.get("amount", []))
                    else None
                ),
                "interval": interval,
            }
            formatted_data.append(formatted_item)
        return formatted_data


class DataSourceManager:
    """数据源管理器(纯 AmazingData:本地 TimescaleDB 唯一源)."""

    def __init__(self):
        """初始化数据源管理器"""
        # 延迟导入避免循环依赖(core/__init__ -> amazingdata_source -> data_source)
        from openbb_app.core.amazingdata_source import AmazingDataSource

        self.data_sources = {
            "amazingdata": AmazingDataSource(),
        }
        self.priority_order = ["amazingdata"]

    def get_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1d",
    ) -> tuple[list[dict[str, Any]], str]:
        """获取数据(唯一源 amazingdata)"""
        for source_name in self.priority_order:
            try:
                data = self.data_sources[source_name].get_historical_data(
                    symbol, start_date, end_date, interval
                )
                if data:
                    return data, source_name
            except Exception as e:
                logger.warning(f"Failed to get data from {source_name}: {e}")
                continue

        raise Exception("Failed to fetch data from all sources")
