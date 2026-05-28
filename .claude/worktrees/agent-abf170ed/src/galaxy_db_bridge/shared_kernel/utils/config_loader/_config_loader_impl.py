"""配置加载器实现（内部使用）.

这个文件包含 ConfigLoader 类的具体实现，
外部用户应该使用 core 模块中的模块级函数接口。
"""

import os
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

import toml

# 加载 .env 文件
load_dotenv()


class ConfigLoader:
    """AmazingData API 配置加载器.

    优先从环境变量读取敏感信息，从 TOML 配置文件读取非敏感配置.
    这是一个单例模式的实现.
    """

    _config: dict[str, Any] | None = None

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> dict[str, Any]:
        """加载配置.

        Args:
            config_path: TOML 配置文件路径，默认 ./config/settings.toml

        Returns:
            合并后的配置字典
        """
        if cls._config is not None:
            return cls._config

        # 加载 TOML 配置文件
        if config_path is None:
            project_root = cls.get_project_root()
            config_path = project_root / "config" / "settings.toml"

        with open(config_path, "r", encoding="utf-8") as f:
            config = toml.load(f)

        # 环境变量覆盖敏感配置
        config = cls._apply_env_overrides(config)

        cls._config = config
        return config

    @classmethod
    def _apply_env_overrides(cls, config: dict[str, Any]) -> dict[str, Any]:
        """应用环境变量覆盖.

        环境变量优先级高于配置文件。
        """
        # AmazingData API 配置
        if "amazing_data" in config:
            ad_config = config["amazing_data"]
            ad_config["username"] = os.getenv("GALAXY_USERNAME", "")
            ad_config["password"] = os.getenv("GALAXY_PASSWORD", "")
            ad_config["host"] = os.getenv("GALAXY_HOST", "")
            ad_config["port"] = int(os.getenv("GALAXY_PORT", ""))
            ad_config["local_path"] = os.getenv(
                "GALAXY_CACHE_PATH", ad_config.get("local_path", "./data/")
            )

        # 数据库配置
        if "database" in config:
            db_config = config["database"]
            db_config["host"] = os.getenv("DB_HOST", "localhost")
            db_config["port"] = int(os.getenv("DB_PORT", "5432"))
            db_config["name"] = os.getenv("DB_NAME", "quant_db")
            db_config["user"] = os.getenv("DB_USER", "quant_user")
            db_config["password"] = os.getenv("DB_PASSWORD", "")

        # 日志配置
        if "logging" in config:
            log_config = config["logging"]
            # 优先使用环境变量，其次使用配置文件中的默认值
            log_config["file_path"] = os.getenv(
                "LOG_FILE_PATH", log_config.get("file_path", "./data/logs/app.log")
            )

        return config

    @classmethod
    def get(cls, section: str, key: str, default: Any = None) -> Any:
        """获取配置项.

        Args:
            section: 配置节名称
            key: 配置键名称
            default: 默认值

        Returns:
            配置值
        """
        config = cls.load()
        return config.get(section, {}).get(key, default)

    @classmethod
    def get_section(cls, section: str) -> dict[str, Any]:
        """获取配置节.

        Args:
            section: 配置节名称

        Returns:
            配置节字典
        """
        config = cls.load()
        return config.get(section, {})

    @classmethod
    def reset(cls) -> None:
        """重置配置缓存（用于测试）."""
        cls._config = None

    @classmethod
    def get_project_root(cls) -> Path:
        """获取项目根目录路径.

        Returns:
            项目根目录的 Path 对象
        """
        # 获取当前文件所在目录，然后向上四级：
        # __file__ 是 _config_loader_impl.py
        # parent 是 src/galaxy_db_bridge/core/
        # parent.parent 是 src/galaxy_db_bridge/
        # parent.parent.parent 是 src/
        # parent.parent.parent.parent 是 项目根目录
        return Path(os.getenv("PROJECT_ROOT_PATH", ""))

    @classmethod
    def get_pyproject_path(cls) -> Path:
        """获取 pyproject.toml 文件的路径.

        Returns:
            pyproject.toml 文件的 Path 对象
        """
        return cls.get_project_root() / "pyproject.toml"
