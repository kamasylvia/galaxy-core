"""配置管理模块.

提供项目配置加载和管理功能，支持从 TOML 文件和环境变量读取配置。
"""

# 从 config.py 导出公共 API
from .config import (
    get_config,
    get_section,
    get_project_root,
    get_pyproject_path,
    reset_config_cache,
    load_config_dict,
)

# 从实现模块导出 ConfigLoader 类
from ._config_loader_impl import ConfigLoader

__all__ = [
    "ConfigLoader",
    "get_config",
    "get_section",
    "get_project_root",
    "get_pyproject_path",
    "reset_config_cache",
    "load_config_dict",
]
