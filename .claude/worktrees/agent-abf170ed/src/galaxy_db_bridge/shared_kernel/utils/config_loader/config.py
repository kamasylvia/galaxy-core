"""配置管理公共接口.

本模块提供配置加载和管理的公共API，内部实现委托给_config_loader_impl.py

Example:
    >>> from galaxy_db_bridge.shared_kernel.config import get_config
    >>> host = get_config("database", "host", "localhost")
    >>> root_path = get_project_root()
"""

from pathlib import Path
from typing import Any

# 从内部实现模块导入ConfigLoader
from ._config_loader_impl import ConfigLoader


# 模块级公共API函数
def get_config(section: str, key: str, default: Any = None) -> Any:
    """获取配置项的快捷函数.

    Args:
        section: 配置节名称
        key: 配置键名称
        default: 默认值

    Returns:
        配置值

    Example:
        >>> from galaxy_db_bridge.core.config import get_config
        >>> host = get_config("database", "host", "localhost")
    """
    return ConfigLoader.get(section, key, default)


def get_section(section: str) -> dict[str, Any]:
    """获取配置节的快捷函数.

    Args:
        section: 配置节名称

    Returns:
        配置节字典

    Example:
        >>> from galaxy_db_bridge.core.config import get_section
        >>> db_config = get_section("database")
    """
    return ConfigLoader.get_section(section)


def get_project_root() -> Path:
    """获取项目根目录路径的快捷函数.

    Returns:
        项目根目录的Path对象

    Example:
        >>> from galaxy_db_bridge.core.config import get_project_root
        >>> root_path = get_project_root()
        >>> data_path = root_path / "data" / "local_cache"
    """
    return ConfigLoader.get_project_root()


def get_pyproject_path() -> Path:
    """获取pyproject.toml文件路径的快捷函数.

    Returns:
        pyproject.toml文件的Path对象

    Example:
        >>> from galaxy_db_bridge.core.config import get_pyproject_path
        >>> pyproject_path = get_pyproject_path()
    """
    return ConfigLoader.get_pyproject_path()


def reset_config_cache() -> None:
    """重置配置缓存的快捷函数（用于测试）.

    Example:
        >>> from galaxy_db_bridge.core.config import reset_config_cache
        >>> reset_config_cache()
    """
    return ConfigLoader.reset()


def load_config_dict(config_path: str | Path | None = None) -> dict[str, Any]:
    """加载完整配置字典的函数.

    Args:
        config_path: TOML 配置文件路径，默认 ./config/settings.toml

    Returns:
        合并后的配置字典

    Example:
        >>> from galaxy_db_bridge.core.config import load_config_dict
        >>> config = load_config_dict()
    """
    return ConfigLoader.load(config_path)
