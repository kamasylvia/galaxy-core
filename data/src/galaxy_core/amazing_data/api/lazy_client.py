"""LazyAmazingDataClient — AmazingDataClient 延迟登录代理.

背景(2026-10-26 realtime_sub TGW 互踢死循环修复):

- AmazingData TGW 账户为单会话:后登录者触发 SDK ForceLogout,把先登录的
  进程踢死(SDK 内部直接 exit 0,无 traceback 无信号)。
- 原 DI Singleton 为 ``AmazingDataClient.from_config`` —— 构造即 login,
  scheduler 主进程启动即持有 TGW 会话;09:00 spawn 的 realtime_sub 登录后
  ~5-10s 把主进程踢死,systemd Restart=always 重启 → 新实例再登录 → 再互踢
  → 死循环(10/23 208 轮、10/26 122 轮)。
- 本代理使「构造 ≠ 登录」:DI 构造链、各 job 构造、白天窗口(09:00-15:30,
  含 11:50 refresh 重启)内的属性解析一律不触发登录;首次实际 SDK 方法调用
  (如凌晨 00:10 全量链)才经 factory 创建底层客户端并登录。
- re-login:09:00 spawn 前主进程 logout() 释放会话让 realtime_sub 独占
  TGW;次日 00:10 首次 SDK 调用时检测到已登出,自动重新登录。

方法面覆盖:adapters/services 实际调用的全部 client 方法
(get_hist_code_list / get_stock_list / get_listing_dates / get_trading_calendar /
get_backward_factor / get_kline / query_snapshot / get_balance_sheet /
get_income_statement / get_cash_flow / get_profit_express / get_profit_notice /
get_dividend / get_stock_basic / get_index_constituent / get_index_weight /
get_industry_base_info / get_industry_constituent / get_industry_weight /
get_industry_daily / get_long_hu_bang / get_block_trading / get_margin_summary /
get_margin_detail,及 get_*_async 包装)经 ``__getattr__`` 全量委托,无需逐一转发。
仅 ``logout`` / ``is_logged_in`` 在代理上显式实现(不可触发登录)。
"""

import logging
from collections.abc import Callable
from typing import Any

from galaxy_core.amazing_data.api.client import AmazingDataClient

logger = logging.getLogger(__name__)


class LazyAmazingDataClient:
    """AmazingDataClient 延迟登录代理.

    Args:
        factory: 零参工厂,返回已登录的 AmazingDataClient
            (生产用 ``AmazingDataClient.from_config``,读取配置 + 登录)。
    """

    def __init__(self, factory: Callable[[], AmazingDataClient]) -> None:
        self._factory = factory
        self._client: AmazingDataClient | None = None

    def _ensure_client(self) -> AmazingDataClient:
        """返回底层客户端;从未登录时经 factory 创建并登录(仅此一次)."""
        if self._client is None:
            logger.info("懒客户端首次 SDK 方法调用,登录 AmazingData ...")
            self._client = self._factory()
        return self._client

    def _ensure_logged_in(self) -> AmazingDataClient:
        """返回已登录的底层客户端;logout 后再次调用时自动重新登录.

        重新登录创建新实例替换 ``self._client``:adapters 持有的是本代理
        (而非底层实例),替换对它们透明。
        """
        client = self._ensure_client()
        if not client._is_logged_in:
            logger.info("AmazingData 会话已登出,懒客户端重新登录 ...")
            client = self._factory()
            self._client = client
        return client

    def logout(self) -> None:
        """登出底层会话(幂等;未登录时为 no-op,绝不触发登录).

        scheduler 在 spawn realtime_sub 前调用,释放主进程 TGW 会话,
        让 realtime_sub 独占单会话(互踢死循环修复的第二、三部分配套)。
        """
        if self._client is None:
            logger.info("懒客户端从未登录,无需登出")
            return
        self._client.logout()

    @property
    def is_logged_in(self) -> bool:
        """当前是否持有底层会话(只读检查,不触发登录)."""
        return self._client is not None and self._client._is_logged_in

    def __getattr__(self, name: str) -> Any:
        """委托全部 SDK 方法面;登录只发生在**调用时**,属性访问本身不登录.

        仅在常规属性查找失败时进入(_factory/_client/显式方法都能常规命中)。
        返回包装函数、调用时再解析目标实例:logout → re-login 替换底层实例
        后,早前取得的包装(如 adapters 存下的 bound 引用)仍指向当前会话;
        且每次方法调用最多解析一次,不会重复登录。

        生产 client 的公共属性面全部为方法(adapters 仅调用 get_*),非方法
        属性不保证访问期直读(经包装调用)。未知公开方法名在调用时抛
        AttributeError(与真实 client 一致)。
        """
        if name.startswith("_"):
            # 内部/私有属性不代理;同时防 __getattr__ 内访问缺失的 _xxx
            # 属性时无限递归。
            raise AttributeError(f"{type(self).__name__} object has no attribute {name!r}")

        def _lazy_call(*args: Any, **kwargs: Any) -> Any:
            current = self._ensure_logged_in()
            return getattr(current, name)(*args, **kwargs)

        return _lazy_call
