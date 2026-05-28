"""AmazingData API 层.

封装银河证券 AmazingData SDK 的连接和数据获取功能.
"""

from .client import AmazingDataClient, amazing_data_client

__all__ = [
    "AmazingDataClient",
    "amazing_data_client",
]
