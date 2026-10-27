"""配置加载器实现（内部使用）.

这个文件包含 ConfigLoader 类的具体实现，
外部用户应该使用 core 模块中的模块级函数接口。
"""

import os
from pathlib import Path
from typing import Any

import toml
from dotenv import load_dotenv

from galaxy_core.shared_kernel.utils.infisical_config import get_env

# 加载 .env 文件（含 INFISICAL_CLIENT_ID/SECRET/PROJECT_ID 三项 MI 凭证 +
# 业务凭证兜底）。SDK 优先从 Infisical 拉取，.env 兜底。
load_dotenv()


class ConfigLoader:
    """AmazingData API 配置加载器.

    优先从环境变量读取敏感信息，从 TOML 配置文件读取非敏感配置.
    支持从 Infisical 获取环境变量（通过 Machine Identity 认证，
    凭证 INFISICAL_CLIENT_ID/SECRET/PROJECT_ID 由 .env 提供）。
    这是一个单例模式的实现.
    """

    _config: dict[str, Any] | None = None

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> dict[str, Any]:
        """加载配置.

        Args:
            config_path: TOML 配置文件路径，默认根据 GALAXY_CONFIG_ENV 环境变量选择

        Returns:
            合并后的配置字典

        环境变量:
            GALAXY_CONFIG_ENV: 配置环境名称
                - "dev" → settings.dev.toml (开发环境)
                - "prod" → settings.prod.toml (生产环境)
                - 其他值 → settings.{value}.toml
                - 未设置 → settings.toml (默认生产环境)
        """
        if cls._config is not None:
            return cls._config

        # 加载 TOML 配置文件
        if config_path is None:
            project_root = cls.get_project_root()
            # 根据环境变量选择配置文件
            config_env = os.getenv("GALAXY_CONFIG_ENV", "")
            if config_env:
                config_filename = f"settings.{config_env}.toml"
            else:
                config_filename = "settings.toml"
            config_path = project_root / "config" / config_filename

        with open(config_path, "r", encoding="utf-8") as f:
            config = toml.load(f)

        # 环境变量覆盖敏感配置
        config = cls._apply_env_overrides(config)

        cls._config = config
        return config

    @classmethod
    def _apply_env_overrides(cls, config: dict[str, Any]) -> dict[str, Any]:
        """应用环境变量覆盖.

        环境变量优先级高于配置文件。支持从 Infisical 获取环境变量
        (见 load() 模块级 docstring)。DB_* 凭证由 async_connection.py 单独读取，
        此处不再处理 [database] 节（TOML 也无此节）。
        """
        # 获取 Infisical 环境配置
        infisical_env = os.getenv("INFISICAL_ENVIRONMENT", "dev")

        # AmazingData API 配置
        if "amazing_data" in config:
            ad_config = config["amazing_data"]
            ad_config["username"] = get_env("GALAXY_USERNAME", "", environment=infisical_env)
            ad_config["password"] = get_env("GALAXY_PASSWORD", "", environment=infisical_env)
            ad_config["host"] = get_env("GALAXY_HOST", "", environment=infisical_env)
            port_str = get_env("GALAXY_PORT", "", environment=infisical_env)
            ad_config["port"] = int(port_str) if port_str else 0
            ad_config["local_path"] = get_env(
                "GALAXY_CACHE_PATH",
                ad_config.get("local_path", "./data/local_cache/"),
                environment=infisical_env,
            )

        # 日志配置
        if "logging" in config:
            log_config = config["logging"]
            # 优先使用环境变量，其次使用配置文件中的默认值
            log_config["file_path"] = get_env(
                "LOG_FILE_PATH",
                log_config.get("file_path", "./data/logs/app.log"),
                environment=infisical_env,
            )

        return config

    @classmethod
    def get(cls, section: str, key: str, default: Any = None) -> Any:
        """获取配置项.

        支持点分 section 名（如 "sync.gap_merge"），按点号分割后逐层访问嵌套字典。
        如果任何层级不存在，返回 default。

        Args:
            section: 配置节名称（支持点分键名，如 "sync.gap_merge"）
            key: 配置键名称
            default: 默认值

        Returns:
            配置值
        """
        config = cls.load()
        # 支持点分 section 名，逐层访问嵌套字典
        parts = section.split(".")
        current: Any = config
        for part in parts:
            if not isinstance(current, dict):
                return default
            current = current.get(part)
            if current is None:
                return default
        if not isinstance(current, dict):
            return default
        return current.get(key, default)

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
        # 优先使用环境变量（用于测试或特殊环境）
        env_root = os.getenv("PROJECT_ROOT_PATH")
        if env_root:
            return Path(env_root)

        # 使用 __file__ 向上四级确定项目根目录：
        # __file__ 是 _config_loader_impl.py
        # parent 是 src/galaxy_core/shared_kernel/utils/config_loader/
        # parent.parent.parent.parent.parent 是 项目根目录
        import sys
        module = sys.modules[cls.__module__]
        return Path(module.__file__).parent.parent.parent.parent.parent.parent

    @classmethod
    def get_pyproject_path(cls) -> Path:
        """获取 pyproject.toml 文件的路径.

        Returns:
            pyproject.toml 文件的 Path 对象
        """
        return cls.get_project_root() / "pyproject.toml"
