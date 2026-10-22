"""参考数据提供者适配器 — 包装 AmazingDataClient 为 ReferenceProviderPort."""

import asyncio
import logging
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from galaxy_core.amazing_data.api.client import AmazingDataClient
from galaxy_core.domain.value_objects import BackwardFactor, SecurityType, StockBasic
from galaxy_core.shared_kernel.utils.config_loader import get_section
from galaxy_core.shared_kernel.utils.symbol_type_inference import infer_security_type

logger = logging.getLogger(__name__)


class ReferenceProviderAdapter:
    """ReferenceProviderPort 实现 — 包装 AmazingDataClient 同步 SDK 为 async 接口.

    asyncio.to_thread() 集中在此 adapter 层，应用层代码完全异步。
    """

    def __init__(self, client: AmazingDataClient) -> None:
        self._client = client
        # SDK 阻塞型调用的 asyncio.wait_for 超时上限。实测 STOCK_A 10501 只
        # 正常响应 ~4-7min,month 周期 500 只 ~5-7min,取 600s(10min)覆盖最慢
        # 正常响应,拦截 SDK 端真挂起。见 AGENTS.md 2026-07-07/09。
        self._api_timeout = get_section("amazing_data").get("api_timeout_seconds", 600)

    async def get_stock_basic(self, symbols: list[str]) -> list[StockBasic]:
        """获取证券基础信息并转换为 domain 值对象.

        Args:
            symbols: 证券代码列表

        Returns:
            StockBasic 列表
        """
        df: pd.DataFrame = await asyncio.to_thread(
            self._client.get_stock_basic,
            code_list=symbols,
        )

        if df is None or df.empty:
            return []

        df_reset = df.reset_index()
        records = df_reset.to_dict("records")

        stock_basics: list[StockBasic] = []
        for rec in records:
            symbol = rec.get("code") or rec.get("symbol") or rec.get("index")
            if symbol is None:
                continue

            symbol_str = str(symbol)
            inferred_str = infer_security_type(symbol_str)
            # infer_security_type 返回 str，需转换为 SecurityType 枚举
            inferred_security_type = SecurityType(inferred_str) if inferred_str else None

            # 安全提取字段
            list_date_raw = rec.get("LISTDATE") or rec.get("list_day") or rec.get("list_date")
            list_date = str(int(list_date_raw)) if pd.notna(list_date_raw) else None

            delist_date_raw = (
                rec.get("DELISTDATE") or rec.get("delist_day") or rec.get("delist_date")
            )
            delist_date = str(int(delist_date_raw)) if pd.notna(delist_date_raw) else None

            stock_name_raw = rec.get("SECURITY_NAME") or rec.get("stock_name") or rec.get("name")
            stock_name = str(stock_name_raw) if pd.notna(stock_name_raw) else None

            market_raw = rec.get("market")
            market = str(market_raw) if pd.notna(market_raw) else None

            exchange_raw = rec.get("exchange")
            exchange = str(exchange_raw) if pd.notna(exchange_raw) else None

            stock_basics.append(
                StockBasic(
                    symbol=symbol_str,
                    security_type=inferred_security_type or SecurityType.EXTRA_STOCK_A,
                    list_date=list_date,
                    delist_date=delist_date,
                    stock_name=stock_name,
                    market=market,
                    exchange=exchange,
                )
            )

        logger.debug(f"获取到 {len(stock_basics)} 条证券基础信息")
        return stock_basics

    async def get_delist_date(self, symbol: str) -> date | None:
        """获取证券退市日期.

        Args:
            symbol: 证券代码

        Returns:
            退市日期，未退市则为 None
        """
        try:
            stock_basics = await self.get_stock_basic([symbol])
            if stock_basics:
                stock_basic = stock_basics[0]
                if hasattr(stock_basic, 'delist_date') and stock_basic.delist_date:
                    # Parse YYYYMMDD format
                    delist_str = stock_basic.delist_date
                    return date(
                        int(delist_str[:4]),
                        int(delist_str[4:6]),
                        int(delist_str[6:8]),
                    )
            return None
        except Exception as e:
            logger.warning(f"获取退市日期失败 {symbol}: {e}")
            return None

    async def update_stock_basic_from_api(self, symbols: list[str]) -> None:
        """从 API 更新 stock_basic 表.

        用于确认流程中发现退市/未上市等情况时，更新 stock_basic 表。

        Args:
            symbols: 需要更新的证券代码列表
        """
        # This is a placeholder - actual implementation would update the database
        # For now, we just log that update was requested
        logger.info(f"请求更新 stock_basic: {symbols}")

    async def get_hist_code_list(
        self, security_type: str, start_date: int, end_date: int, local_path: str
    ) -> list[str]:
        """获取历史代码表.

        Args:
            security_type: 代码类型（如 EXTRA_ETF）
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            local_path: 本地缓存路径

        Returns:
            历史代码列表
        """
        result: list[str] = await asyncio.wait_for(
            asyncio.to_thread(
                self._client.get_hist_code_list,
                security_type=security_type,
                start_date=start_date,
                end_date=end_date,
                local_path=local_path,
            ),
            timeout=self._api_timeout,
        )
        logger.debug(f"获取历史代码表: {len(result)} 个 ({security_type})")
        return result

    async def get_stock_list(self, security_type: str) -> list[str]:
        """获取指定 security_type 的证券代码列表.

        调用 AmazingDataClient.get_stock_list_async，提取 DataFrame 的 index
        作为 code_market 格式的代码列表。

        Args:
            security_type: 代码类型名称（如 EXTRA_ETF, EXTRA_STOCK_A）

        Returns:
            code_market 格式的代码列表
        """
        df: pd.DataFrame = await asyncio.wait_for(
            asyncio.to_thread(
                self._client.get_stock_list,
                security_type=security_type,
            ),
            timeout=self._api_timeout,
        )

        if df is None or df.empty:
            return []

        symbol_list = df.index.tolist()
        logger.debug(f"获取到 {len(symbol_list)} 个证券代码 ({security_type})")
        return symbol_list

    async def get_listing_dates(
        self, symbols: list[str], security_type: str
    ) -> dict[str, str | None]:
        """获取证券上市日期.

        调用 AmazingDataClient.get_listing_dates，返回 {symbol: YYYYMMDD} 字典。

        Args:
            symbols: 证券代码列表
            security_type: 代码类型，用于确定查询范围

        Returns:
            {symbol: YYYYMMDD} 字典，无上市日期则为 None
        """
        result: dict[str, str | None] = await asyncio.to_thread(
            self._client.get_listing_dates,
            symbols=symbols,
            security_type=security_type,
        )
        logger.debug(
            f"获取 {len(symbols)} 只证券的上市日期，"
            f"成功 {sum(1 for v in result.values() if v)} 只"
        )
        return result

    async def get_code_info(self, security_type: str) -> pd.DataFrame:
        """获取指定类型的证券代码信息.

        调用 SDK get_code_info，返回包含证券代码、简称、上市日期等信息的 DataFrame。
        主要用于 ETF 等无法通过 get_stock_basic 获取的类型。

        Args:
            security_type: 证券类型（如 EXTRA_ETF）

        Returns:
            原始 DataFrame（SDK 返回格式，index 为 code_market）

        Raises:
            asyncio.TimeoutError: SDK 调用超过 self._api_timeout 秒（默认 600s）
        """
        df: pd.DataFrame = await asyncio.wait_for(
            asyncio.to_thread(
                self._client.get_stock_list,
                security_type=security_type,
            ),
            timeout=self._api_timeout,
        )
        if df is None:
            logger.warning(f"get_code_info 返回 None ({security_type})")
            return pd.DataFrame()
        logger.debug(f"get_code_info 返回: {len(df)} 条 ({security_type})")
        return df

    async def get_stock_basic_df(self, symbols: list[str]) -> pd.DataFrame:
        """获取证券基础信息原始 DataFrame.

        Args:
            symbols: 证券代码列表

        Returns:
            原始 DataFrame（SDK 返回格式）

        Raises:
            asyncio.TimeoutError: SDK 调用超过 self._api_timeout 秒（默认 600s）
        """
        logger.info(f"get_stock_basic: {len(symbols)} symbols")
        logger.debug(f"symbols 前5个: {symbols[:5]}")
        df: pd.DataFrame = await asyncio.wait_for(
            asyncio.to_thread(
                self._client.get_stock_basic,
                code_list=symbols,
            ),
            timeout=self._api_timeout,
        )
        if df is None:
            logger.warning("get_stock_basic 返回 None")
            return pd.DataFrame()
        shape = df.shape if hasattr(df, 'shape') else 'N/A'
        logger.info(f"get_stock_basic 返回: shape={shape}")
        logger.debug(f"type={type(df)}, 列名: {list(df.columns) if hasattr(df, 'columns') else 'N/A'}")
        return df

    async def get_backward_factor_df(
        self, symbols: list[str], local_path: str
    ) -> pd.DataFrame:
        """获取后复权因子原始 DataFrame.

        Args:
            symbols: 证券代码列表
            local_path: 本地缓存路径

        Returns:
            原始 DataFrame（宽格式：index=日期, columns=股票代码）
        """
        df: pd.DataFrame = await asyncio.to_thread(
            self._client.get_backward_factor,
            code_list=symbols,
            local_path=local_path,
            is_local=False,
        )
        if df is None:
            return pd.DataFrame()
        return df

    async def ensure_stock_basic(self, symbols: list[str]) -> list[dict[str, object]]:
        """从 API 获取 stock_basic 数据并转换为记录列表.

        区分股票和 ETF，调用合适的 API。返回的记录可直接 UPSERT 到 stock_basic 表。

        Args:
            symbols: 证券代码列表

        Returns:
            记录列表，每条包含 symbol, security_name, list_date, delist_date, security_type
        """
        if not symbols:
            return []

        records: list[dict[str, object]] = []

        # 区分股票和 ETF
        stock_symbols = []
        etf_symbols = []
        for symbol in symbols:
            if self._is_etf_symbol(symbol):
                etf_symbols.append(symbol)
            else:
                stock_symbols.append(symbol)

        # 股票：调用 get_stock_basic
        if stock_symbols:
            try:
                df = await self.get_stock_basic_df(stock_symbols)
                if df is not None and not df.empty:
                    df_reset = df.reset_index()
                    total = len(df_reset)
                    for i, (_, row) in enumerate(df_reset.iterrows()):
                        symbol = row.get("MARKET_CODE") or row.get("code") or row.get("index")
                        if symbol is None:
                            continue
                        records.append(self._make_stock_basic_record(symbol, row, "EXTRA_STOCK_A"))
                        if (i + 1) % 100 == 0 or i + 1 == total:
                            logger.info(f"stock_basic 解析进度: {i + 1}/{total}")
            except Exception as e:
                logger.warning(f"get_stock_basic 失败: {e}")

        # ETF：调用 get_code_info
        if etf_symbols:
            try:
                df = await self.get_code_info("EXTRA_ETF")
                if df is not None and not df.empty:
                    for symbol in etf_symbols:
                        if symbol in df.index:
                            row = df.loc[symbol]
                            rec = self._make_stock_basic_record_from_code_info(symbol, row)
                            records.append(rec)
            except Exception as e:
                logger.warning(f"get_code_info 失败: {e}")

        return records

    def _is_etf_symbol(self, symbol: str) -> bool:
        """判断是否为 ETF 代码."""
        from galaxy_core.domain.symbol.type_inference import is_etf_symbol

        return is_etf_symbol(symbol)

    def _make_stock_basic_record(
        self, symbol: str, row: object, security_type: str
    ) -> dict[str, object]:
        """从 get_stock_basic 行构造记录."""
        list_date = self._parse_date_value(row.get("LISTDATE"))
        delist_date = self._parse_date_value(row.get("DELISTDATE"))
        return {
            "symbol": str(symbol),
            "security_name": row.get("SECURITY_NAME"),
            "list_date": list_date,
            "delist_date": delist_date,
            "security_type": security_type,
        }

    def _make_stock_basic_record_from_code_info(
        self, symbol: str, row: object
    ) -> dict[str, object]:
        """从 get_code_info 行构造记录."""
        list_day = row.get("list_day") if hasattr(row, "get") else getattr(row, "list_day", None)
        name = row.get("symbol") if hasattr(row, "get") else getattr(row, "symbol", None)
        list_date = self._parse_date_value(list_day)
        return {
            "symbol": str(symbol),
            "security_name": name,
            "list_date": list_date,
            "delist_date": None,
            "security_type": "EXTRA_ETF",
        }

    def _parse_date_value(self, value) -> date | None:
        """解析日期值."""
        if value is None or (hasattr(value, "isna") and value.isna()):
            return None
        try:
            if isinstance(value, date) and not isinstance(value, datetime):
                return value
            if isinstance(value, datetime):
                return value.date()
            # 支持 Python int/float 和 numpy 标量（numpy.int64 等）
            if isinstance(value, (int, float)) or hasattr(value, "item"):
                value = str(int(value))
            if isinstance(value, str):
                value = value.strip()
                if len(value) == 8:
                    return date(int(value[:4]), int(value[4:6]), int(value[6:]))
        except (ValueError, TypeError):
            pass
        return None

    async def get_backward_factor(self, symbols: list[str]) -> list[BackwardFactor]:
        """获取复权因子并转换为 domain 值对象.

        SDK 返回 DataFrame: index=日期, columns=股票代码。
        需要 melt/stack 转换为 long format。

        Args:
            symbols: 证券代码列表

        Returns:
            BackwardFactor 列表
        """
        raw_cache = get_section("amazing_data").get("local_path", "./data/local_cache/")
        local_path = str(Path(raw_cache).resolve())
        if raw_cache.endswith("/"):
            local_path += "/"
        df: pd.DataFrame = await asyncio.to_thread(
            self._client.get_backward_factor,
            code_list=symbols,
            local_path=local_path,
            is_local=True,
        )

        if df is None or df.empty:
            return []

        # DataFrame: index=日期(datetime), columns=股票代码(str)
        # 使用 melt 转换为 long format，避免 iterrows()
        df_reset = df.reset_index()
        date_col = df_reset.columns[0]  # 日期列名

        # melt: 将宽格式（每只股票一列）转为长格式（symbol, trade_time, factor）
        df_melted = df_reset.melt(
            id_vars=[date_col],
            var_name="symbol",
            value_name="backward_factor",
        )
        # 删除 NaN 行（某些股票在某些日期没有因子）
        df_melted = df_melted.dropna(subset=["backward_factor"])

        records = df_melted.to_dict("records")

        from galaxy_core.shared_kernel.utils.constants import localize_cst

        factors: list[BackwardFactor] = []
        for rec in records:
            trade_date_raw = rec[date_col]
            # 统一转 aware datetime(北京时区),timestamptz 列需要
            if isinstance(trade_date_raw, datetime):
                trade_date = localize_cst(trade_date_raw)
            elif isinstance(trade_date_raw, date):
                trade_date = localize_cst(
                    datetime(trade_date_raw.year, trade_date_raw.month, trade_date_raw.day)
                )
            elif isinstance(trade_date_raw, str):
                trade_date = localize_cst(datetime.strptime(trade_date_raw[:8], "%Y%m%d"))
            elif isinstance(trade_date_raw, (int, float)):
                trade_date = localize_cst(
                    datetime.strptime(str(int(trade_date_raw))[:8], "%Y%m%d")
                )
            else:
                logger.warning(f"无法解析复权因子日期: {trade_date_raw}")
                continue

            factors.append(
                BackwardFactor(
                    symbol=str(rec["symbol"]),
                    trade_time=trade_date,
                    backward_factor=float(rec["backward_factor"]),
                )
            )

        logger.debug(f"获取到 {len(factors)} 条复权因子，symbols={symbols}")
        return factors
