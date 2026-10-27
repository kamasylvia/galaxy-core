"""AmazingDataClient.logout 用户名处理单元测试（2026-10-27 互踢残余 bug 修复）.

背景：SDK 的 ``ad.logout`` 必须显式传 username，无参调用抛 TypeError。
此前 logout 无参调用失败后仍翻转 ``_is_logged_in`` 并打「登出成功」假成功
日志——服务端会话未释放，realtime_sub 登录触发 ForceLogout 踢死 scheduler
主进程（2026-10-27 09:00 北京实证，见 .work/TODO.md）。

验证：
1. initialize 保存 username，logout() 不传参时用它真正调 SDK 登出；
2. 显式传参覆盖保存值；
3. 无用户名：告警 + 本地置未登录，不调 SDK（服务端会话由超时/ForceLogout 回收）；
4. SDK 登出抛错：告警非关键、保持已登录标记（会话可能仍有效）；
5. 未登录时 logout no-op。
"""

import logging
from unittest.mock import MagicMock, patch

from galaxy_core.amazing_data.api.client import AmazingDataClient


def _make_logged_in_client(username: str | None = None) -> AmazingDataClient:
    client = AmazingDataClient()
    client._ad = MagicMock()
    client._is_logged_in = True
    if username is not None:
        client._username = username
    return client


class TestLogoutUsername:
    def test_logout_uses_stored_username(self):
        client = _make_logged_in_client(username="user_a")

        client.logout()

        client._ad.logout.assert_called_once_with("user_a")
        assert client._is_logged_in is False

    def test_logout_explicit_username_overrides_stored(self):
        client = _make_logged_in_client(username="user_a")

        client.logout(username="user_b")

        client._ad.logout.assert_called_once_with("user_b")
        assert client._is_logged_in is False

    def test_logout_without_username_warns_and_clears_local_flag(
        self, caplog: pytest.LogCaptureFixture
    ):
        client = _make_logged_in_client()

        with caplog.at_level(logging.WARNING, logger="galaxy_core.amazing_data.api.client"):
            client.logout()

        client._ad.logout.assert_not_called()
        assert client._is_logged_in is False
        assert "无用户名" in caplog.text

    def test_logout_failure_keeps_logged_in_flag(self, caplog: pytest.LogCaptureFixture):
        client = _make_logged_in_client(username="user_a")
        client._ad.logout.side_effect = RuntimeError("tgw reset")

        with caplog.at_level(logging.WARNING, logger="galaxy_core.amazing_data.api.client"):
            client.logout()

        assert client._is_logged_in is True
        assert "登出失败" in caplog.text

    def test_logout_noop_when_not_logged_in(self):
        client = _make_logged_in_client(username="user_a")
        client._is_logged_in = False

        client.logout()

        client._ad.logout.assert_not_called()
        assert client._is_logged_in is False


class TestInitializeStoresUsername:
    def test_initialize_stores_username_and_logs_in(self):
        client = AmazingDataClient()

        with (
            patch("galaxy_core.amazing_data.api.client.ad") as ad_mock,
            patch("galaxy_core.amazing_data.api.client._install_tgw_filter"),
        ):
            client.initialize(username="user_a", password="pw", host="127.0.0.1", port=1)

        assert client._username == "user_a"
        assert client._is_logged_in is True
        ad_mock.login.assert_called_once_with(
            username="user_a", password="pw", host="127.0.0.1", port=1
        )

    def test_initialize_skip_when_already_logged_in_keeps_session(self):
        client = AmazingDataClient()
        client._is_logged_in = True

        with (
            patch("galaxy_core.amazing_data.api.client.ad") as ad_mock,
            patch("galaxy_core.amazing_data.api.client._install_tgw_filter"),
        ):
            client.initialize(username="user_a", password="pw", host="127.0.0.1", port=1)

        ad_mock.login.assert_not_called()
