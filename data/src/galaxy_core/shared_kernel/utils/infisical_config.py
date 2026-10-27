"""Infisical 配置模块.

使用 Infisical HTTP API 获取环境变量，支持 Universal Auth 认证方式。
"""

import os
from typing import Any

import requests


class InfisicalConfig:
    """Infisical 配置管理器.

    使用 Universal Auth (Client ID + Client Secret) 认证方式
    通过 HTTP API 从 Infisical 获取环境变量。
    """

    _access_token: str | None = None
    _initialized: bool = False
    _site_url: str = "https://app.infisical.com"

    @classmethod
    def initialize(
        cls,
        client_id: str | None = None,
        client_secret: str | None = None,
        site_url: str | None = None,
    ) -> bool:
        """初始化 Infisical 客户端并获取访问令牌.

        Args:
            client_id: Infisical Universal Auth Client ID
            client_secret: Infisical Universal Auth Client Secret
            site_url: Infisical 服务地址，默认 https://app.infisical.com

        Returns:
            是否初始化成功
        """
        if cls._initialized and cls._access_token:
            return True

        # 从环境变量获取配置
        client_id = client_id or os.getenv("INFISICAL_CLIENT_ID")
        client_secret = client_secret or os.getenv("INFISICAL_CLIENT_SECRET")
        site_url = site_url or os.getenv("INFISICAL_URL", "https://app.infisical.com")

        if not client_id or not client_secret:
            return False

        # site_url 此处至少为 INFISICAL_URL 的 getenv 值或 default，但类型仍是 str|None；
        # 再兜一次确保非 None（os.getenv 即便有 default 也返回 str|None）。
        resolved_url = site_url or "https://app.infisical.com"
        cls._site_url = resolved_url.rstrip("/")

        try:
            # 使用 Universal Auth 获取访问令牌
            response = requests.post(
                f"{cls._site_url}/api/v1/auth/universal-auth/login",
                json={
                    "clientId": client_id,
                    "clientSecret": client_secret,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            cls._access_token = data.get("accessToken")
            if cls._access_token:
                cls._initialized = True
                return True
            return False
        except Exception:
            return False

    @classmethod
    def get_secret(
        cls,
        secret_name: str,
        environment: str = "dev",
        project_id: str | None = None,
        default: str | None = None,
        secret_type: str = "shared",
        secret_path: str = "/",
    ) -> str | None:
        """从 Infisical 获取密钥.

        Args:
            secret_name: 密钥名称
            environment: 环境名称 (dev, staging, production)
            project_id: 项目 ID，默认从环境变量 INFISICAL_PROJECT_ID 获取
            default: 默认值
            secret_type: 密钥类型，shared (工作区共享，生产常用) 或 personal (个人)
            secret_path: 密钥路径，默认根路径 /

        Returns:
            密钥值，如果获取失败则返回默认值
        """
        if not cls._initialized:
            if not cls.initialize():
                return default

        project_id = project_id or os.getenv("INFISICAL_PROJECT_ID")
        if not project_id:
            return default

        try:
            response = requests.get(
                f"{cls._site_url}/api/v3/secrets/raw/{secret_name}",
                headers={
                    "Authorization": f"Bearer {cls._access_token}",
                },
                params={
                    "workspaceId": project_id,
                    "environment": environment,
                    "type": secret_type,
                    "secretPath": secret_path,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            secret = data.get("secret", {})
            return secret.get("secretValue") if secret else default
        except Exception:
            return default

    @classmethod
    def get_secrets(
        cls,
        environment: str = "dev",
        project_id: str | None = None,
        secret_type: str = "shared",
        secret_path: str = "/",
    ) -> dict[str, str]:
        """从 Infisical 获取所有密钥.

        Args:
            environment: 环境名称 (dev, staging, production)
            project_id: 项目 ID，默认从环境变量 INFISICAL_PROJECT_ID 获取
            secret_type: 密钥类型，shared (工作区共享，生产常用) 或 personal (个人)
            secret_path: 密钥路径，默认根路径 /

        Returns:
            密钥字典
        """
        if not cls._initialized:
            if not cls.initialize():
                return {}

        project_id = project_id or os.getenv("INFISICAL_PROJECT_ID")
        if not project_id:
            return {}

        try:
            response = requests.get(
                f"{cls._site_url}/api/v3/secrets/raw",
                headers={
                    "Authorization": f"Bearer {cls._access_token}",
                },
                params={
                    "workspaceId": project_id,
                    "environment": environment,
                    "type": secret_type,
                    "secretPath": secret_path,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            secrets = data.get("secrets", [])
            return {s["secretKey"]: s["secretValue"] for s in secrets}
        except Exception:
            return {}

    @classmethod
    def is_configured(cls) -> bool:
        """检查 Infisical 是否已配置.

        Returns:
            是否已配置
        """
        if cls._initialized:
            return True

        # 检查环境变量是否存在
        return bool(
            os.getenv("INFISICAL_CLIENT_ID")
            and os.getenv("INFISICAL_CLIENT_SECRET")
            and os.getenv("INFISICAL_PROJECT_ID")
        )

    @classmethod
    def reset(cls) -> None:
        """重置客户端（用于测试）."""
        cls._access_token = None
        cls._initialized = False


def get_env(
    key: str,
    default: str | None = None,
    use_infisical: bool = True,
    environment: str = "dev",
) -> str | None:
    """获取环境变量，优先从 Infisical 获取，其次从本地环境变量获取.

    获取顺序：
    1. Infisical (如果已配置且启用)
    2. 本地环境变量 (os.environ)
    3. 默认值

    Args:
        key: 环境变量名
        default: 默认值
        use_infisical: 是否尝试从 Infisical 获取
        environment: Infisical 环境名称

    Returns:
        环境变量值
    """
    # 1. 首先尝试从 Infisical 获取（优先级最高）
    if use_infisical and InfisicalConfig.is_configured():
        value = InfisicalConfig.get_secret(key, environment=environment)
        if value is not None:
            return value

    # 2. 从本地环境变量获取
    value = os.getenv(key)
    if value is not None:
        return value

    # 3. 返回默认值
    return default


def load_infisical_to_env(environment: str = "dev") -> dict[str, str]:
    """将 Infisical 的所有密钥加载到环境变量.

    Args:
        environment: 环境名称

    Returns:
        加载的密钥字典
    """
    if not InfisicalConfig.is_configured():
        return {}

    secrets = InfisicalConfig.get_secrets(environment=environment)
    for key, value in secrets.items():
        os.environ[key] = value

    return secrets
