"""AmazingData API 客户端.

封装银河证券 AmazingData SDK 的连接和数据获取功能.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

# Monkey-patch pandas 3.x compatibility for AmazingData SDK
# SDK uses fillna(method=...) which was removed in pandas 2.0+
import pandas.core.generic as _generic

_original_ndframe_fillna = _generic.NDFrame.fillna


def _patched_fillna(self, value=None, method=None, axis=None, inplace=False, limit=None, downcast=None, **kwargs):
    if method is not None:
        if inplace:
            if method in ("ffill", "pad"):
                self.ffill(axis=axis, limit=limit, inplace=True)
            elif method in ("bfill", "backfill"):
                self.bfill(axis=axis, limit=limit, inplace=True)
            return None
        else:
            if method in ("ffill", "pad"):
                return self.ffill(axis=axis, limit=limit)
            elif method in ("bfill", "backfill"):
                return self.bfill(axis=axis, limit=limit)
    return _original_ndframe_fillna(self, value=value, axis=axis, inplace=inplace, limit=limit)


_generic.NDFrame.fillna = _patched_fillna

import AmazingData as ad

from galaxy_db_sync.shared_kernel.utils.config_loader import get_config
from galaxy_db_sync.shared_kernel.exceptions import (
    APIConnectionError,
    APITimeoutError,
    APIResponseError,
    SDKError,
)
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from .client import AmazingDataClient

logger = logging.getLogger(__name__)


class AmazingDataClient:
    """AmazingData API 客户端.

    封装 SDK 的登录、基础数据、行情数据接口。
    """

    _instance = None
    _is_logged_in = False
    _ad = None  # AmazingData module

    def __new__(cls) -> "AmazingDataClient":
        """单例模式."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """初始化（延迟加载）."""
        self._base_data = None
        self._market_data = None
        self._info_data = None
        self._calendar = None

    @classmethod
    def from_config(cls) -> "AmazingDataClient":
        """从配置创建并初始化客户端.

        自动从配置中读取 amazing_data 相关参数并初始化客户端.

        Returns:
            AmazingDataClient: 已初始化的客户端实例

        Raises:
            ValueError: 如果缺少必要的配置信息
            RuntimeError: 如果初始化失败
        """
        # 从配置读取参数
        username = get_config("amazing_data", "username")
        password = get_config("amazing_data", "password")
        host = get_config("amazing_data", "host")
        port = get_config("amazing_data", "port")

        if not all([username, password, host]):
            logger.error("缺少必要的配置信息")
            logger.error(
                f"username: {username}, password: {'***' if password else '(none)'}, host: {host}, port: {port}"
            )
            logger.error("请确保环境变量中配置了 GALAXY_USERNAME, GALAXY_PASSWORD")
            raise ValueError("缺少必要的配置信息")

        # 获取单例实例并初始化
        client = cls()
        client.initialize(username=username, password=password, host=host, port=port)
        return client

    def initialize(
        self,
        username: str,
        password: str,
        host: str,
        port: int,
    ) -> None:
        """初始化并登录 AmazingData.

        Args:
            username: 用户名
            password: 密码
            host: 服务器 IP
            port: 服务器端口
        """
        if self._is_logged_in:
            logger.info("Already logged in")
            return

        try:
            self._ad = ad
            ad.login(  # type: ignore
                username=username,
                password=password,
                host=host,
                port=port,
            )
            self._is_logged_in = True

            # 初始化数据接口
            self._base_data = ad.BaseData()  # type: ignore
            self._info_data = ad.InfoData()  # type: ignore

            # 获取交易日历
            self._calendar = self._base_data.get_calendar()  # type: ignore

            logger.info(f"AmazingData login success: {host}:{port}")

        except ImportError:
            logger.error("AmazingData SDK not installed")
            raise RuntimeError(
                "AmazingData SDK not installed. "
                "Please install from wheels/amazing_data_client-*.whl"
            )
        except ConnectionError as e:
            logger.error(f"AmazingData connection failed: {e}")
            raise APIConnectionError(
                endpoint=f"{host}:{port}",
                reason=str(e),
                message=f"无法连接到 AmazingData 服务器: {host}:{port}",
            ) from e
        except TimeoutError as e:
            logger.error(f"AmazingData login timeout: {e}")
            raise APITimeoutError(
                endpoint=f"{host}:{port}",
                timeout_duration=30.0,
                message=f"连接 AmazingData 服务器超时: {host}:{port}",
            ) from e
        except Exception as e:
            logger.error(f"AmazingData login failed: {e}")
            raise SDKError(
                message=f"AmazingData 登录失败: {e}",
                endpoint=f"{host}:{port}",
                original_error=e,
            ) from e

    def logout(self, username: str = None) -> None:
        """登出."""
        if self._is_logged_in and self._ad:
            try:
                if username:
                    self._ad.logout(username)  # type: ignore
                else:
                    # 如果没有提供用户名，尝试不带参数的登出
                    try:
                        self._ad.logout()  # type: ignore
                    except TypeError:
                        # 如果不带参数失败，记录警告但继续
                        logger.warning("Need username to logout, skipping logout procedure")
                self._is_logged_in = False
                logger.info("AmazingData logout success")
            except Exception as e:
                # 登出是非关键操作，记录警告但不抛出异常
                logger.warning(f"Logout failed (non-critical): {type(e).__name__}: {e}")

    def ensure_logged_in(self) -> None:
        """确保已登录."""
        if not self._is_logged_in:
            raise RuntimeError("Not logged in. Call initialize() first.")

    # =============================================================================
    # 基础数据接口
    # =============================================================================

    def get_hist_code_list(
        self, security_type: str, start_date: int, end_date: int, local_path: str
    ) -> list[str]:
        """获取历史代码表.

        Args:
            security_type: 代码类型
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            local_path: 本地缓存路径

        Returns:
            代码列表

        Raises:
            APIConnectionError: 连接失败
            APITimeoutError: 请求超时
            SDKError: SDK 内部错误
        """
        self.ensure_logged_in()
        endpoint = "get_hist_code_list"
        try:
            logger.info(
                f"Calling get_hist_code_list with: security_type={security_type}, start_date={start_date}, end_date={end_date}, local_path={local_path}"
            )
            hist_code_list = self._base_data.get_hist_code_list(
                security_type=security_type,
                start_date=start_date,
                end_date=end_date,
                local_path=local_path,
            )  # type: ignore
            logger.info(f"Fetched {len(hist_code_list)} historical codes for {security_type}")  # type: ignore
            return hist_code_list  # type: ignore
        except ConnectionError as e:
            raise APIConnectionError(endpoint=endpoint, reason=str(e)) from e
        except TimeoutError as e:
            raise APITimeoutError(endpoint=endpoint, timeout_duration=30.0) from e
        except Exception as e:
            raise SDKError(
                message=f"获取历史代码表失败: {e}", endpoint=endpoint, original_error=e
            ) from e

    async def get_hist_code_list_async(
        self, security_type: str, start_date: int, end_date: int, local_path: str
    ) -> list[str]:
        """异步获取历史代码表.

        使用 asyncio.to_thread 包装同步 SDK 调用，避免阻塞事件循环。

        Args:
            security_type: 代码类型
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            local_path: 本地缓存路径

        Returns:
            代码列表
        """
        return await asyncio.to_thread(
            self.get_hist_code_list,
            security_type=security_type,
            start_date=start_date,
            end_date=end_date,
            local_path=local_path,
        )

    def get_stock_list(self, security_type: str = "EXTRA_STOCK_A") -> pd.DataFrame:
        """获取股票代码列表.

        Args:
            security_type: 代码类型，默认 EXTRA_STOCK_A

        Returns:
            DataFrame 包含股票代码和基本信息

        Raises:
            APIConnectionError: 连接失败
            APITimeoutError: 请求超时
            SDKError: SDK 内部错误
        """
        self.ensure_logged_in()
        endpoint = "get_code_info"
        try:
            code_info = self._base_data.get_code_info(security_type=security_type)  # type: ignore
            logger.info(f"Fetched {len(code_info)} stocks")  # type: ignore
            return code_info  # type: ignore
        except ConnectionError as e:
            raise APIConnectionError(endpoint=endpoint, reason=str(e)) from e
        except TimeoutError as e:
            raise APITimeoutError(endpoint=endpoint, timeout_duration=30.0) from e
        except Exception as e:
            raise SDKError(
                message=f"获取股票列表失败: {e}", endpoint=endpoint, original_error=e
            ) from e

    async def get_stock_list_async(self, security_type: str = "EXTRA_STOCK_A") -> pd.DataFrame:
        """异步获取股票代码列表.

        Args:
            security_type: 代码类型，默认 EXTRA_STOCK_A

        Returns:
            DataFrame 包含股票代码和基本信息
        """
        return await asyncio.to_thread(
            self.get_stock_list,
            security_type=security_type,
        )

    def get_listing_dates(
        self,
        symbols: list[str],
        security_type: str = "EXTRA_ETF",
    ) -> dict[str, str | None]:
        """获取证券上市日期.

        通过 get_code_info 获取证券的上市日期（list_day 字段）。

        Args:
            symbols: 证券代码列表
            security_type: 代码类型，用于确定查询范围

        Returns:
            dict {symbol: list_day} 上市日期字符串 (YYYYMMDD)，无上市日期则为 None

        Note:
            此方法在失败时返回空字典而不是抛出异常，因为上市日期是可选信息。
        """
        self.ensure_logged_in()
        endpoint = "get_code_info"
        try:
            # 获取指定类型的所有证券信息
            code_info = self._base_data.get_code_info(security_type=security_type)  # type: ignore

            result: dict[str, str | None] = {}
            for symbol in symbols:
                if symbol in code_info.index:
                    list_day = code_info.loc[symbol].get("list_day")
                    if pd.notna(list_day):
                        # list_day 可能是 int 或 str，统一转为 str
                        result[symbol] = (
                            str(int(list_day)) if isinstance(list_day, float) else str(list_day)
                        )
                    else:
                        result[symbol] = None
                else:
                    result[symbol] = None

            logger.info(
                f"获取 {len(symbols)} 个证券的上市日期，成功 {sum(1 for v in result.values() if v)} 个"
            )
            return result
        except Exception as e:
            # 上市日期是可选信息，失败时返回空字典而不抛出异常
            logger.warning(f"Failed to get listing dates (non-critical): {type(e).__name__}: {e}")
            return {symbol: None for symbol in symbols}

    async def get_listing_dates_async(
        self,
        symbols: list[str],
        security_type: str = "EXTRA_ETF",
    ) -> dict[str, str | None]:
        """异步获取证券上市日期.

        Args:
            symbols: 证券代码列表
            security_type: 代码类型，用于确定查询范围

        Returns:
            dict {symbol: list_day} 上市日期字符串 (YYYYMMDD)，无上市日期则为 None
        """
        return await asyncio.to_thread(
            self.get_listing_dates,
            symbols=symbols,
            security_type=security_type,
        )

    def get_trading_calendar(
        self,
        market: str = "SH",
        data_type: str = "datetime",
    ) -> list[int] | list[datetime]:
        """获取交易日历.

        Args:
            market: 市场代码 SH/SZ/BJ
            data_type: 返回类型 str/datetime

        Returns:
            交易日列表

        Raises:
            APIConnectionError: 连接失败
            APITimeoutError: 请求超时
            SDKError: SDK 内部错误
        """
        self.ensure_logged_in()
        endpoint = "get_calendar"
        try:
            calendar = self._base_data.get_calendar(market=market, data_type=data_type)
            return calendar
        except ConnectionError as e:
            raise APIConnectionError(endpoint=endpoint, reason=str(e)) from e
        except TimeoutError as e:
            raise APITimeoutError(endpoint=endpoint, timeout_duration=30.0) from e
        except Exception as e:
            raise SDKError(
                message=f"获取交易日历失败: {e}", endpoint=endpoint, original_error=e
            ) from e

    def get_backward_factor(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """获取复权因子（后复权）.

        Args:
            code_list: 股票代码列表
            local_path: 本地缓存路径
            is_local: 是否使用本地缓存

        Returns:
            DataFrame index=日期, columns=股票代码

        Raises:
            APIConnectionError: 连接失败
            APITimeoutError: 请求超时
            SDKError: SDK 内部错误
        """
        self.ensure_logged_in()
        endpoint = "get_backward_factor"
        try:
            factor = self._base_data.get_backward_factor(
                code_list=code_list,
                local_path=local_path,
                is_local=is_local,
            )
            return factor
        except ConnectionError as e:
            raise APIConnectionError(endpoint=endpoint, reason=str(e)) from e
        except TimeoutError as e:
            raise APITimeoutError(endpoint=endpoint, timeout_duration=30.0) from e
        except Exception as e:
            raise SDKError(
                message=f"获取复权因子失败: {e}", endpoint=endpoint, original_error=e
            ) from e

    # =============================================================================
    # 行情数据接口
    # =============================================================================

    def get_kline(
        self,
        code_list: list[str],
        begin_date: int,
        end_date: int,
        interval: str,
        begin_time: int = None,
        end_time: int = None,
    ) -> dict[str, pd.DataFrame]:
        """获取历史K线数据.

        Args:
            code_list: 股票代码列表
            begin_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            interval: K线周期 (如 "day", "min1", "week" 等)
            begin_time: 开始时间（可选）
            end_time: 结束时间（可选）

        Returns:
            dict {code: DataFrame}

        Raises:
            APIConnectionError: 连接失败
            APITimeoutError: 请求超时
            SDKError: SDK 内部错误
        """
        from galaxy_db_sync.shared_kernel.enums.interval import Interval

        self.ensure_logged_in()
        endpoint = "get_kline"
        try:
            # 确保交易日历已初始化
            if self._calendar is None:
                logger.warning("Calendar is not initialized, fetching trading calendar...")
                self._calendar = self._base_data.get_calendar()

            # 初始化 MarketData（需要交易日历）
            market_data = self._ad.MarketData(self._calendar)

            # interval str → SDK period int
            period_value = Interval(interval).to_sdk_period_value()

            # 准备参数，仅在提供时传递可选参数
            query_kwargs = {
                "code_list": code_list,
                "begin_date": begin_date,
                "end_date": end_date,
                "period": period_value,
            }

            # 只有当参数不为None时才添加到参数字典中
            if begin_time is not None:
                query_kwargs["begin_time"] = begin_time
            if end_time is not None:
                query_kwargs["end_time"] = end_time

            kline_dict = market_data.query_kline(**query_kwargs)
            # 使用 DEBUG 级别避免批量同步时大量日志输出
            logger.debug(
                f"Fetched kline for {len(kline_dict)} codes from {begin_date} to {end_date}"
            )
            return kline_dict
        except ConnectionError as e:
            raise APIConnectionError(endpoint=endpoint, reason=str(e)) from e
        except TimeoutError as e:
            raise APITimeoutError(endpoint=endpoint, timeout_duration=30.0) from e
        except Exception as e:
            raise SDKError(
                message=f"获取K线数据失败: {e}", endpoint=endpoint, original_error=e
            ) from e

    async def get_kline_async(
        self,
        code_list: list[str],
        begin_date: int,
        end_date: int,
        interval: str,
        begin_time: int = None,
        end_time: int = None,
    ) -> dict[str, pd.DataFrame]:
        """异步获取历史K线数据.

        使用 asyncio.to_thread 包装同步 SDK 调用。
        注意：切勿在 async 函数中直接调用同步 SDK 方法，否则会阻塞事件循环。

        Args:
            code_list: 股票代码列表
            begin_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            interval: K线周期 (如 "day", "min1", "week" 等)
            begin_time: 开始时间（可选）
            end_time: 结束时间（可选）

        Returns:
            dict {code: DataFrame}
        """
        return await asyncio.to_thread(
            self.get_kline,
            code_list=code_list,
            begin_date=begin_date,
            end_date=end_date,
            interval=interval,
            begin_time=begin_time,
            end_time=end_time,
        )

    def query_snapshot(
        self,
        code_list: list[str],
        begin_date: int,
        end_date: int,
        begin_time: int = 0,
        end_time: int = 0,
    ) -> dict[str, pd.DataFrame]:
        """查询历史快照数据.

        Args:
            code_list: 股票代码列表
            begin_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            begin_time: 开始时间 HHMMSSmmm
            end_time: 结束时间 HHMMSSmmm

        Returns:
            dict {code: DataFrame}

        Raises:
            APIConnectionError: 连接失败
            APITimeoutError: 请求超时
            SDKError: SDK 内部错误
        """
        self.ensure_logged_in()
        endpoint = "query_snapshot"
        try:
            market_data = self._ad.MarketData(self._calendar)
            snapshot_dict = market_data.query_snapshot(
                code_list=code_list,
                begin_date=begin_date,
                end_date=end_date,
                begin_time=begin_time,
                end_time=end_time,
            )
            logger.info(f"Fetched snapshot for {len(snapshot_dict)} codes")
            return snapshot_dict
        except ConnectionError as e:
            raise APIConnectionError(endpoint=endpoint, reason=str(e)) from e
        except TimeoutError as e:
            raise APITimeoutError(endpoint=endpoint, timeout_duration=30.0) from e
        except Exception as e:
            raise SDKError(
                message=f"查询快照数据失败: {e}", endpoint=endpoint, original_error=e
            ) from e

    # =============================================================================
    # 财务数据接口
    # =============================================================================

    def get_balance_sheet(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        """获取资产负债表.

        Args:
            code_list: 股票代码列表
            local_path: 本地缓存路径
            is_local: 是否使用本地缓存
            begin_date: 报告期开始日期（可选）
            end_date: 报告期结束日期（可选）

        Returns:
            dict {code: DataFrame}

        Raises:
            APIConnectionError: 连接失败
            APITimeoutError: 请求超时
            SDKError: SDK 内部错误
        """
        self.ensure_logged_in()
        endpoint = "get_balance_sheet"
        try:
            kwargs = {
                "code_list": code_list,
                "local_path": local_path,
                "is_local": is_local,
            }
            if begin_date is not None:
                kwargs["begin_date"] = begin_date
            if end_date is not None:
                kwargs["end_date"] = end_date

            data = self._info_data.get_balance_sheet(**kwargs)
            return data
        except ConnectionError as e:
            raise APIConnectionError(endpoint=endpoint, reason=str(e)) from e
        except TimeoutError as e:
            raise APITimeoutError(endpoint=endpoint, timeout_duration=30.0) from e
        except Exception as e:
            raise SDKError(
                message=f"获取资产负债表失败: {e}", endpoint=endpoint, original_error=e
            ) from e

    def get_income_statement(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """获取利润表.

        Raises:
            APIConnectionError: 连接失败
            APITimeoutError: 请求超时
            SDKError: SDK 内部错误
        """
        self.ensure_logged_in()
        endpoint = "get_income"
        try:
            data = self._info_data.get_income(
                code_list=code_list,
                local_path=local_path,
                is_local=is_local,
            )
            return data
        except ConnectionError as e:
            raise APIConnectionError(endpoint=endpoint, reason=str(e)) from e
        except TimeoutError as e:
            raise APITimeoutError(endpoint=endpoint, timeout_duration=30.0) from e
        except Exception as e:
            raise SDKError(
                message=f"获取利润表失败: {e}", endpoint=endpoint, original_error=e
            ) from e

    def get_cash_flow(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """获取现金流量表.

        Raises:
            APIConnectionError: 连接失败
            APITimeoutError: 请求超时
            SDKError: SDK 内部错误
        """
        self.ensure_logged_in()
        endpoint = "get_cash_flow"
        try:
            data = self._info_data.get_cash_flow(
                code_list=code_list,
                local_path=local_path,
                is_local=is_local,
            )
            return data
        except ConnectionError as e:
            raise APIConnectionError(endpoint=endpoint, reason=str(e)) from e
        except TimeoutError as e:
            raise APITimeoutError(endpoint=endpoint, timeout_duration=30.0) from e
        except Exception as e:
            raise SDKError(
                message=f"获取现金流量表失败: {e}", endpoint=endpoint, original_error=e
            ) from e

    def get_history_stock_status(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        """获取历史证券状态（停牌/ST/涨跌停价/除权除息）.

        Args:
            code_list: 股票代码列表
            local_path: 本地缓存路径
            is_local: 是否使用本地缓存
            begin_date: 开始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            dict {code: DataFrame}

        Raises:
            APIConnectionError: 连接失败
            APITimeoutError: 请求超时
            SDKError: SDK 内部错误
        """
        self.ensure_logged_in()
        endpoint = "get_history_stock_status"
        try:
            kwargs = {
                "code_list": code_list,
                "local_path": local_path,
                "is_local": is_local,
            }
            if begin_date is not None:
                kwargs["begin_date"] = begin_date
            if end_date is not None:
                kwargs["end_date"] = end_date

            data = self._info_data.get_history_stock_status(**kwargs)
            return data
        except ConnectionError as e:
            raise APIConnectionError(endpoint=endpoint, reason=str(e)) from e
        except TimeoutError as e:
            raise APITimeoutError(endpoint=endpoint, timeout_duration=30.0) from e
        except Exception as e:
            raise SDKError(
                message=f"获取历史证券状态失败: {e}", endpoint=endpoint, original_error=e
            ) from e

    def get_stock_basic(
        self,
        code_list: list[str],
    ) -> pd.DataFrame:
        """获取证券基础信息.

        Args:
            code_list: 股票代码列表

        Returns:
            DataFrame 包含证券基础信息

        Raises:
            APIConnectionError: 连接失败
            APITimeoutError: 请求超时
            SDKError: SDK 内部错误
        """
        self.ensure_logged_in()
        endpoint = "get_stock_basic"
        try:
            data = self._info_data.get_stock_basic(code_list)
            return data
        except ConnectionError as e:
            raise APIConnectionError(endpoint=endpoint, reason=str(e)) from e
        except TimeoutError as e:
            raise APITimeoutError(endpoint=endpoint, timeout_duration=30.0) from e
        except Exception as e:
            raise SDKError(
                message=f"获取证券基础信息失败: {e}", endpoint=endpoint, original_error=e
            ) from e


class LazyAmazingDataClient:
    """延迟加载的AmazingData客户端.

    首次访问时自动从配置初始化客户端.
    """

    def __init__(self):
        self._instance: AmazingDataClient | None = None
        self._initialized = False

    def __getattr__(self, name: str):
        # 首次访问任何属性时初始化客户端
        if not self._initialized:
            logger.info("首次访问AmazingDataClient，正在从配置初始化...")
            from .client import AmazingDataClient

            self._instance = AmazingDataClient.from_config()
            self._initialized = True

        # 返回实例的属性
        return getattr(self._instance, name)

    def force_initialize(self) -> AmazingDataClient:
        """强制初始化客户端."""
        if not self._initialized:
            from .client import AmazingDataClient

            self._instance = AmazingDataClient.from_config()
            self._initialized = True
        # return self._instance
        return cast(AmazingDataClient, self._instance)

    def get_instance(self) -> AmazingDataClient:
        """获取客户端实例（如果尚未初始化则进行初始化）."""
        if not self._initialized:
            self.force_initialize()
        return cast(AmazingDataClient, self._instance)


# 全局延迟加载客户端实例
amazing_data_client = LazyAmazingDataClient()
