"""AmazingData API 层.

封装银河证券 AmazingData SDK 的连接和数据获取功能.
"""

from .client import AmazingDataClient
from .lazy_client import LazyAmazingDataClient

__all__ = [
    "AmazingDataClient",
    "LazyAmazingDataClient",
]
