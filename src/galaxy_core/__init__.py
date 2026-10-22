"""Galaxy DB Bridge - 银河证券AmazingData数据库桥接层.

从银河证券AmazingData接口获取行情和财务数据，并持久化到PostgreSQL。
"""

__version__ = "0.1.0"
__author__ = "Laniakea Kamasylvia"
__email__ = "laniakea.kamasylvia@outlook.com"

# 从各模块导出核心组件
from .amazing_data.api.client import AmazingDataClient
from .shared_kernel.utils.config_loader import (
    ConfigLoader,
    get_config,
    get_section,
    get_project_root,
    get_pyproject_path,
)
from .database.core.async_connection import AsyncDatabaseManager as DatabaseManager
from .database.models import Base

__all__ = [
    "__version__",
    # API
    "AmazingDataClient",
    # Config
    "ConfigLoader",
    "get_config",
    "get_section",
    "get_project_root",
    "get_pyproject_path",
    # Database
    "DatabaseManager",
    # Models
    "Base",
]
