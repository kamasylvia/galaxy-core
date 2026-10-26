"""LazyAmazingDataClient 延迟登录代理单元测试.

验证(2026-10-26 realtime_sub TGW 互踢死循环修复):
1. 构造 ≠ 登录,属性访问本身也不登录 —— DI 构造链、白天窗口一律 0 次登录;
   首次实际 SDK 方法**调用**才经 factory 登录(生产 = from_config,恰好一次);
2. 后续调用复用同一底层客户端(factory 不再调用);
3. logout 幂等:未登录 no-op、已登录委托底层、绝不触发登录;
4. logout 后首次 SDK 调用自动重新登录(re-login,替换底层实例,恰好一次);
5. 早前取得的包装函数在 re-login 后指向新会话;
6. 方法面委托:adapters 实际调用的全部 client 方法均可经代理调用;
7. 未知公开方法名调用时抛 AttributeError;私有属性不代理且不触发登录。
"""

from unittest.mock import MagicMock, patch

import pytest

from galaxy_core.amazing_data.api.client import AmazingDataClient
from galaxy_core.amazing_data.api.lazy_client import LazyAmazingDataClient

# adapters(services 等)实际调用的 client 同步方法面(2026-10-26 审计,
# 见 grep "client.get_" src/galaxy_core/amazing_data/api/adapters/)。
ADAPTER_CALLED_METHODS = [
    "get_hist_code_list",
    "get_stock_list",
    "get_listing_dates",
    "get_trading_calendar",
    "get_backward_factor",
    "get_kline",
    "query_snapshot",
    "get_balance_sheet",
    "get_income_statement",
    "get_cash_flow",
    "get_profit_express",
    "get_profit_notice",
    "get_dividend",
    "get_stock_basic",
    "get_index_constituent",
    "get_index_weight",
    "get_industry_base_info",
    "get_industry_constituent",
    "get_industry_weight",
    "get_industry_daily",
    "get_long_hu_bang",
    "get_block_trading",
    "get_margin_summary",
    "get_margin_detail",
]

# async 包装(adapters 经 asyncio.to_thread 调同步版,async 版存在即可)
ASYNC_WRAPPER_METHODS = [
    "get_hist_code_list_async",
    "get_stock_list_async",
    "get_listing_dates_async",
    "get_kline_async",
]


def _make_inner_client(is_logged_in: bool = True) -> MagicMock:
    client = MagicMock()
    client._is_logged_in = is_logged_in
    return client


class TestLazyConstruction:
    """构造 ≠ 登录."""

    def test_construction_does_not_invoke_factory(self):
        factory = MagicMock()
        LazyAmazingDataClient(factory)
        factory.assert_not_called()

    def test_is_logged_in_check_does_not_login(self):
        """is_logged_in 是只读检查,不触发登录."""
        factory = MagicMock()
        proxy = LazyAmazingDataClient(factory)
        assert proxy.is_logged_in is False
        factory.assert_not_called()

    def test_logout_before_any_use_is_noop(self):
        """从未登录时 logout 为 no-op,不触发登录."""
        factory = MagicMock()
        proxy = LazyAmazingDataClient(factory)
        proxy.logout()
        factory.assert_not_called()


class TestFirstCallAndReuse:
    """首次 SDK 方法调用登录;后续复用."""

    def test_first_method_call_logs_in_once_and_delegates(self):
        inner = _make_inner_client()
        factory = MagicMock(return_value=inner)
        proxy = LazyAmazingDataClient(factory)

        result = proxy.get_kline(code_list=["600000.SH"], begin_date=1, end_date=2, interval="day")

        factory.assert_called_once()
        inner.get_kline.assert_called_once_with(
            code_list=["600000.SH"], begin_date=1, end_date=2, interval="day"
        )
        assert result is inner.get_kline.return_value
        assert proxy.is_logged_in is True

    def test_subsequent_calls_reuse_same_client(self):
        inner = _make_inner_client()
        factory = MagicMock(return_value=inner)
        proxy = LazyAmazingDataClient(factory)

        proxy.get_stock_list()
        proxy.get_stock_list()
        proxy.get_hist_code_list(
            security_type="EXTRA_STOCK_A", start_date=1, end_date=2, local_path="/tmp"
        )

        assert factory.call_count == 1

    def test_method_attribute_access_does_not_login(self):
        """属性访问本身不触发登录(登录只发生在调用时)."""
        factory = MagicMock()
        proxy = LazyAmazingDataClient(factory)
        _ = proxy.get_kline  # 仅属性访问,不调用
        factory.assert_not_called()
        assert proxy.is_logged_in is False


class TestLogoutAndRelogin:
    """logout 幂等;logout 后首次 SDK 调用自动重新登录."""

    def test_logout_delegates_without_relogin(self):
        inner = _make_inner_client()
        factory = MagicMock(return_value=inner)
        proxy = LazyAmazingDataClient(factory)
        proxy.get_stock_list()

        proxy.logout()
        inner._is_logged_in = False  # 模拟真实 client.logout() 的状态翻转副作用

        inner.logout.assert_called_once()
        assert factory.call_count == 1  # logout 不触发登录
        assert proxy.is_logged_in is False

    def test_relogin_after_logout_replaces_client(self):
        first = _make_inner_client()
        second = _make_inner_client()
        factory = MagicMock(side_effect=[first, second])
        proxy = LazyAmazingDataClient(factory)

        proxy.get_stock_list()  # 首次登录 → first
        proxy.logout()  # 09:00 spawn 前登出
        first._is_logged_in = False  # 模拟底层登录态已翻转

        proxy.get_stock_list()  # 次日 00:10 首次 SDK 调用 → 自动 re-login

        assert factory.call_count == 2
        second.get_stock_list.assert_called_once()
        assert first.get_stock_list.call_count == 1  # 旧实例不再被调用

    def test_stale_wrapper_resolves_current_session(self):
        """logout→re-login 后,早前取得的包装函数指向新会话."""
        first = _make_inner_client()
        second = _make_inner_client()
        factory = MagicMock(side_effect=[first, second])
        proxy = LazyAmazingDataClient(factory)

        wrapper = proxy.get_kline  # 首次解析(创建 first)
        first._is_logged_in = False
        proxy.logout()

        wrapper(code_list=["x"], begin_date=1, end_date=2, interval="day")

        second.get_kline.assert_called_once()
        assert first.get_kline.call_count == 0  # 旧实例的方法从未被调用

    def test_logout_failure_state_still_relogin(self):
        """底层 logout 内部吞错(真实 client 语义)时,re-login 仍可靠."""
        inner = _make_inner_client()
        factory = MagicMock(return_value=inner)
        proxy = LazyAmazingDataClient(factory)
        proxy.get_stock_list()
        proxy.logout()
        inner._is_logged_in = False

        proxy.get_trading_calendar(market="SH", data_type="datetime")

        assert factory.call_count == 2
        inner.get_trading_calendar.assert_called_once()


class TestMethodSurface:
    """方法面覆盖:adapters 实际调用的全部 client 方法均可经代理委托."""

    def test_surface_methods_exist_on_real_client(self):
        """防清单笔误:清单方法必须真实存在于 AmazingDataClient."""
        from galaxy_core.amazing_data.api.client import AmazingDataClient

        for name in ADAPTER_CALLED_METHODS + ASYNC_WRAPPER_METHODS:
            assert callable(getattr(AmazingDataClient, name)), name

    @pytest.mark.parametrize("method", ADAPTER_CALLED_METHODS)
    def test_adapter_method_delegates(self, method):
        inner = _make_inner_client()
        proxy = LazyAmazingDataClient(MagicMock(return_value=inner))

        getattr(proxy, method)(code_list=["600000.SH"], local_path="/tmp")

        getattr(inner, method).assert_called_once()


class TestAttributeErrors:
    """未知公开方法名调用时抛 AttributeError;私有属性不代理、不触发登录."""

    def test_unknown_public_method_raises_at_call(self):
        """未知公开方法名:调用时抛 AttributeError(真实 client 语义)."""
        real = AmazingDataClient()  # 构造不登录
        real._is_logged_in = True
        proxy = LazyAmazingDataClient(MagicMock(return_value=real))
        with pytest.raises(AttributeError):
            proxy.get_klinee()  # type: ignore[attr-defined] # 拼错的方法名

    def test_private_attribute_not_proxied_and_no_login(self):
        factory = MagicMock()
        proxy = LazyAmazingDataClient(factory)
        with pytest.raises(AttributeError):
            _ = proxy._nonexistent  # type: ignore[attr-defined]
        factory.assert_not_called()


class TestDIWiring:
    """DI 接线:amazing_data_client 单例返回懒代理,解析 adapter 不登录."""

    def test_container_resolves_lazy_client_without_login(self):
        from galaxy_core.di.container import Container

        container = Container()
        with patch("galaxy_core.di.container.AmazingDataClient.from_config") as mock_factory:
            client = container.amazing_data_client()
            assert isinstance(client, LazyAmazingDataClient)
            mock_factory.assert_not_called()

    def test_kline_provider_receives_lazy_proxy(self):
        from galaxy_core.di.container import Container

        container = Container()
        client = container.amazing_data_client()
        provider = container.kline_provider()
        assert provider._client is client
        assert isinstance(provider._client, LazyAmazingDataClient)
