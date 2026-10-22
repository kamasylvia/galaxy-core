"""InfisicalConfig / get_env 单元测试.

测试 get_env 优先级链:
  1. Infisical (is_configured + get_secret 返值)
  2. os.environ
  3. default

测试 InfisicalConfig 类状态隔离 (reset / is_configured / initialize)。
所有用例 autouse fixture 调 reset() 保证类级 _access_token/_initialized 不串。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from galaxy_core.shared_kernel.utils.infisical_config import (
    InfisicalConfig,
    get_env,
    load_infisical_to_env,
)


@pytest.fixture(autouse=True)
def _reset_infisical_state() -> None:
    """每个用例前后清空 InfisicalConfig 类状态,避免类属性跨用例泄漏."""
    InfisicalConfig.reset()
    yield
    InfisicalConfig.reset()


# 所需的三个 MI 环境变量
MI_ENV = {
    "INFISICAL_CLIENT_ID": "test-client-id",
    "INFISICAL_CLIENT_SECRET": "test-client-secret",
    "INFISICAL_PROJECT_ID": "test-project-id",
}


class TestGetEnvPriorityChain:
    """get_env 三级优先级链."""

    def test_get_env_prefers_infisical_when_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """is_configured True + get_secret 返值 → 返回 infisical 值,不读 os.getenv."""
        for k, v in MI_ENV.items():
            monkeypatch.setenv(k, v)
        # 故意让 os.environ 也有同 key,验证 infisical 优先
        monkeypatch.setenv("MY_KEY", "from-os-env")

        with (
            patch.object(InfisicalConfig, "is_configured", return_value=True),
            patch.object(
                InfisicalConfig, "get_secret", return_value="from-infisical"
            ) as mock_get,
        ):
            result = get_env("MY_KEY", default="fallback")

        assert result == "from-infisical"
        mock_get.assert_called_once_with("MY_KEY", environment="dev")

    def test_get_env_falls_back_to_os_environ_when_infisical_unconfigured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """is_configured False → 走 os.getenv."""
        # 不设置 MI 三项 → is_configured False
        for k in MI_ENV:
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setenv("MY_KEY", "from-os-env")

        result = get_env("MY_KEY", default="fallback")
        assert result == "from-os-env"

    def test_get_env_returns_default_when_nothing_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """infisical 无值 + os.getenv 无值 → 返回 default."""
        for k in MI_ENV:
            monkeypatch.delenv(k, raising=False)
        monkeypatch.delenv("MY_KEY", raising=False)

        assert get_env("MY_KEY", default="fallback") == "fallback"
        # default=None 时返回 None
        assert get_env("MY_KEY") is None

    def test_get_env_skips_infisical_when_use_infisical_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """use_infisical=False → 直接走 os.getenv,不调 InfisicalConfig."""
        for k, v in MI_ENV.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("MY_KEY", "from-os-env")

        with patch.object(InfisicalConfig, "is_configured") as mock_is:
            result = get_env("MY_KEY", default="fallback", use_infisical=False)

        assert result == "from-os-env"
        mock_is.assert_not_called()  # use_infisical=False 短路,根本不查 is_configured

    def test_get_env_infisical_returns_none_falls_through_to_os(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """infisical 配置好但 get_secret 返 None → 降级到 os.getenv."""
        for k, v in MI_ENV.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("MY_KEY", "from-os-env")

        with (
            patch.object(InfisicalConfig, "is_configured", return_value=True),
            patch.object(InfisicalConfig, "get_secret", return_value=None),
        ):
            result = get_env("MY_KEY", default="fallback")

        assert result == "from-os-env"


class TestIsConfigured:
    """is_configured 检查三项 MI 环境变量."""

    @pytest.mark.parametrize("missing_key", list(MI_ENV.keys()))
    def test_is_configured_returns_false_when_any_mi_env_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        missing_key: str,
    ) -> None:
        """三项 MI 凭证缺一即 False."""
        for k, v in MI_ENV.items():
            if k == missing_key:
                monkeypatch.delenv(k, raising=False)
            else:
                monkeypatch.setenv(k, v)

        assert InfisicalConfig.is_configured() is False

    def test_is_configured_returns_true_when_all_three_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """三项齐备 → True."""
        for k, v in MI_ENV.items():
            monkeypatch.setenv(k, v)

        assert InfisicalConfig.is_configured() is True

    def test_is_configured_returns_true_when_already_initialized(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_initialized=True → 直接返回 True,不查环境变量."""
        for k in MI_ENV:  # 都不设置
            monkeypatch.delenv(k, raising=False)

        with patch.object(InfisicalConfig, "_initialized", True):
            assert InfisicalConfig.is_configured() is True


class TestReset:
    """reset() 清类状态."""

    def test_reset_clears_state(self) -> None:
        """reset() 后 _initialized=False, _access_token=None."""
        # 模拟已初始化状态
        InfisicalConfig._access_token = "stale-token"
        InfisicalConfig._initialized = True

        InfisicalConfig.reset()

        assert InfisicalConfig._access_token is None
        assert InfisicalConfig._initialized is False


class TestInitialize:
    """initialize() HTTP 调用路径(mock requests,不打真实网络)."""

    def test_initialize_returns_false_without_credentials(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """无 MI 凭证 → 不发请求,返回 False."""
        for k in MI_ENV:
            monkeypatch.delenv(k, raising=False)

        assert InfisicalConfig.initialize() is False
        assert InfisicalConfig._initialized is False

    def test_initialize_success_caches_access_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """凭证齐全 + HTTP 200 + accessToken → 缓存到类属性,返回 True."""
        for k, v in MI_ENV.items():
            monkeypatch.setenv(k, v)

        fake_response = {
            "accessToken": "fake-access-token",
            "expiresIn": 3600,
        }

        with patch("galaxy_core.shared_kernel.utils.infisical_config.requests.post") as mock_post:
            mock_post.return_value.json.return_value = fake_response
            mock_post.return_value.raise_for_status.return_value = None

            result = InfisicalConfig.initialize()

        assert result is True
        assert InfisicalConfig._access_token == "fake-access-token"
        assert InfisicalConfig._initialized is True
        # 验证调用了 Universal Auth 端点
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "/api/v1/auth/universal-auth/login" in args[0]
        assert kwargs["json"]["clientId"] == "test-client-id"
        assert kwargs["json"]["clientSecret"] == "test-client-secret"

    def test_initialize_returns_false_on_http_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """HTTP 异常被吞,返回 False(不 raise)."""
        for k, v in MI_ENV.items():
            monkeypatch.setenv(k, v)

        with patch("galaxy_core.shared_kernel.utils.infisical_config.requests.post") as mock_post:
            mock_post.return_value.raise_for_status.side_effect = Exception("network error")

            result = InfisicalConfig.initialize()

        assert result is False
        assert InfisicalConfig._initialized is False


class TestLoadInfisicalToEnv:
    """load_infisical_to_env 批量灌入."""

    def test_load_returns_empty_when_unconfigured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """未配置 → 空 dict,不改 os.environ."""
        for k in MI_ENV:
            monkeypatch.delenv(k, raising=False)

        result = load_infisical_to_env()
        assert result == {}

    def test_load_populates_env_from_secrets(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """已配置 → 拉 secrets 灌入 os.environ,返回 secrets dict."""
        for k, v in MI_ENV.items():
            monkeypatch.setenv(k, v)

        secrets = {"DB_HOST": "db.infisical", "DB_PASSWORD": "secret-from-infisical"}

        with (
            patch.object(InfisicalConfig, "is_configured", return_value=True),
            patch.object(InfisicalConfig, "get_secrets", return_value=secrets),
        ):
            result = load_infisical_to_env()

        assert result == secrets
        # monkeypatch 会自动恢复 os.environ
        import os
        assert os.environ["DB_HOST"] == "db.infisical"
        assert os.environ["DB_PASSWORD"] == "secret-from-infisical"
