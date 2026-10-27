"""K线数据提供者适配器 — 包装 AmazingDataClient 为 KlineProviderPort."""

import asyncio
import logging
from datetime import date, datetime

import pandas as pd

from galaxy_core.amazing_data.api.client import AmazingDataClient
from galaxy_core.domain.ports.kline_provider import KlineProviderPort
from galaxy_core.domain.value_objects import Interval, KlineBar, SecurityType, StockInfo
from galaxy_core.shared_kernel.utils.symbol_type_inference import infer_security_type

logger = logging.getLogger(__name__)


class KlineProviderAdapter:
    """KlineProviderPort 实现 — 包装 AmazingDataClient 同步 SDK 为 async 接口.

    asyncio.to_thread() 集中在此 adapter 层，应用层代码完全异步。
    SDK 阻塞型调用用 asyncio.wait_for 包裹超时,防止事件循环卡死
    (2026-07-09:month 周期曾观察到 SDK 端挂起,to_thread 无限等待导致整个
    事件循环冻结。对齐 reference_provider_adapter 2026-07-07 Bug 7 修法)。
    """

    def __init__(self, client: AmazingDataClient) -> None:
        self._client = client
        # SDK 阻塞型调用的 asyncio.wait_for 超时上限。
        # 实测 month 周期 500 只 × 13 年正常响应 ~5-7min,取 600s(10min)覆盖最慢正常响应。
        from galaxy_core.shared_kernel.utils.config_loader import get_section

        self._api_timeout = get_section("amazing_data").get("api_timeout_seconds", 600)

    async def get_kline(
        self,
        symbols: list[str],
        interval: Interval,
        start: str,
        end: str,
    ) -> list[KlineBar]:
        """获取K线数据并转换为 domain 值对象.

        无效代码降级策略(SDK 对退市/不存在代码在 month/season/year 周期会挂起):
        1. 预分类:调 get_stock_list 取有效代码集合,把 symbols 分为有效/无效两组
        2. 试探无效组:用少量无效代码(≤5只)探测 SDK 是否能正常返回
        3. 试探秒回 → SDK 无限制 → 全量(有效+无效)大批量同步
           试探超时 → SDK 有限制 → 只用有效代码大批量同步

        Args:
            symbols: 证券代码列表
            interval: K线周期
            start: 开始日期 (YYYYMMDD 格式字符串)
            end: 结束日期 (YYYYMMDD 格式字符串)

        Returns:
            KlineBar 列表
        """
        # 参数转换: domain 类型 → SDK 类型
        begin_date = int(start[:8])
        end_date = int(end[:8])
        interval_str = interval.value

        # 按市场分组(SH/SZ/BJ):SDK get_kline 对「沪深+BJ 混合」的 code_list
        # 静默丢沪深 codes(2026-08-06 实锤:DB fallback 8045 只含 591 BJ,
        # SDK 只发 458 个新股单查,沪深增量全丢,应用层却标 8045 只全成功)。
        # 8/4 用 SDK universe(纯沪深 5536 只)批量成功 → SDK 对纯市场 code_list
        # 正常,混合市场触发静默丢弃。按市场分组成独立调用规避。
        market_groups = self._group_by_market(symbols)

        if len(market_groups) == 1:
            return await self._get_kline_group(
                next(iter(market_groups.values())), interval_str, begin_date, end_date
            )

        # 多市场(如 STOCK_A 含沪深+BJ):逐市场独立调 SDK,串行(API 不支持并发)
        logger.info(
            f"按市场分组同步: {len(symbols)} 只 → "
            f"{[f'{k}:{len(v)}' for k, v in market_groups.items()]}"
        )
        all_bars: list[KlineBar] = []
        for market, market_symbols in market_groups.items():
            try:
                bars = await self._get_kline_group(
                    market_symbols, interval_str, begin_date, end_date
                )
                all_bars.extend(bars)
                logger.info(f"市场组 {market}: {len(bars)} 条")
            except Exception as e:
                # 单市场组失败:raise 让上层把该组所有 symbol 记为失败重试,
                # 不静默丢(比 SDK 混合丢更可观测)
                logger.error(f"市场组 {market} 同步失败 ({len(market_symbols)} 只): {e}")
                raise
        return all_bars

        # DataFrame → domain 值对象转换
        return self._convert_kline_dict(kline_dict, symbols)

    # 内部细分类型 → SDK 宽类型(get_stock_list 的 security_type 参数)
    # infer_security_type 返回 SH_A/SZ_A/BJ_A/SH_ETF/SH_INDEX 等细分类型,
    # 但 get_stock_list 需要 EXTRA_STOCK_A/EXTRA_ETF/EXTRA_INDEX_A 等宽类型。
    _SDK_TYPE_MAP = {
        "SH_A": "EXTRA_STOCK_A", "SZ_A": "EXTRA_STOCK_A", "BJ_A": "EXTRA_STOCK_A",
        "SH_ETF": "EXTRA_ETF", "SZ_ETF": "EXTRA_ETF",
        "SH_INDEX": "EXTRA_INDEX_A", "SZ_INDEX": "EXTRA_INDEX_A", "BJ_INDEX": "EXTRA_INDEX_A",
    }

    # 市场后缀 → 分组 key(按首次出现顺序保持稳定)
    @staticmethod
    def _group_by_market(symbols: list[str]) -> dict[str, list[str]]:
        """按交易所后缀分组,规避 SDK 对混合市场 code_list 的静默丢弃.

        Returns:
            有序 dict {市场key: [codes]},key 为 SH/SZ/BJ/OTHER。
        """
        groups: dict[str, list[str]] = {}
        for symbol in symbols:
            if symbol.endswith(".SH"):
                key = "SH"
            elif symbol.endswith(".SZ"):
                key = "SZ"
            elif symbol.endswith(".BJ"):
                key = "BJ"
            else:
                key = "OTHER"
            groups.setdefault(key, []).append(symbol)
        return groups

    async def _get_kline_group(
        self,
        symbols: list[str],
        interval_str: str,
        begin_date: int,
        end_date: int,
    ) -> list[KlineBar]:
        """单市场组的同步逻辑(原 get_kline 主体):降级策略 + 大批量调用."""
        # 决定最终同步的 code_list + 是否小批量模式(降级策略)
        effective_codes, small_batch = await self._resolve_effective_codes(
            symbols, interval_str, begin_date, end_date
        )

        if not effective_codes:
            logger.warning(f"所有 {len(symbols)} 只代码均被过滤,跳过")
            return []

        if len(effective_codes) < len(symbols):
            logger.info(
                f"降级模式: {len(symbols)} → {len(effective_codes)} 只有效代码 "
                f"(过滤 {len(symbols) - len(effective_codes)} 只无效)"
            )

        if small_batch:
            # INDEX 类型 + 试探超时:逐小批(5只)调 SDK,有效秒回,无效超时跳过
            return await self._get_kline_small_batch(
                effective_codes, interval_str, begin_date, end_date
            )

        # 大批量调 SDK(带超时防挂起)
        kline_dict: dict[str, pd.DataFrame] = await asyncio.wait_for(
            asyncio.to_thread(
                self._client.get_kline,
                code_list=effective_codes,
                begin_date=begin_date,
                end_date=end_date,
                interval=interval_str,
            ),
            timeout=self._api_timeout,
        )

        return self._convert_kline_dict(kline_dict, symbols)

    async def _get_kline_small_batch(
        self,
        symbols: list[str],
        interval_str: str,
        begin_date: int,
        end_date: int,
    ) -> list[KlineBar]:
        """小批量模式:逐 5 只调 SDK,有效秒回,无效超时跳过。

        用于 INDEX 类型(无法预分类)且试探超时的场景。
        每批 5 只 + 15s 超时:有效代码秒回,无效代码超时跳过。
        """
        all_bars: list[KlineBar] = []
        batch_size = 5
        skipped = 0
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]
            try:
                kline_dict = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._client.get_kline,
                        code_list=batch,
                        begin_date=begin_date,
                        end_date=end_date,
                        interval=interval_str,
                    ),
                    timeout=15,
                )
                all_bars.extend(self._convert_kline_dict(kline_dict, batch))
            except asyncio.TimeoutError:
                skipped += len(batch)
                logger.debug(f"小批量超时跳过 {len(batch)} 只: {batch[:2]}...")
            except Exception as e:
                skipped += len(batch)
                logger.debug(f"小批量异常跳过 {len(batch)} 只: {e}")
        if skipped:
            logger.info(f"小批量模式完成: {len(symbols)-skipped} 只有效, {skipped} 只跳过")
        return all_bars

    async def _resolve_effective_codes(
        self,
        symbols: list[str],
        interval_str: str,
        begin_date: int,
        end_date: int,
    ) -> tuple[list[str], bool]:
        """降级策略:预分类 + 试探无效代码,决定最终同步的 code_list.

        返回 (effective_codes, small_batch_mode)。
        - small_batch_mode=False:正常大批量同步
        - small_batch_mode=True:INDEX 类型试探超时,逐 5 只小批量(有效秒回,无效超时跳过)

        1. 调 get_stock_list 取有效代码集合,分 symbols 为有效/无效
        2. 单只代码探测 SDK 是否能正常返回(短超时 10s)
        3. 探测秒回 → 全量;探测超时 → 只用有效(或 INDEX 小批量)

        day 周期对无效代码不敏感(返回空不卡),直接全量不做降级。
        """
        # day 周期不卡,直接全量
        if interval_str == "day":
            return symbols, False

        # 从 symbols 推断 SDK 宽类型(取第一个代码的类型 → 映射到 SDK 宽类型)
        first_type = infer_security_type(symbols[0]) if symbols else None
        sdk_type = self._SDK_TYPE_MAP.get(first_type) if first_type else None
        if not sdk_type:
            return symbols, False  # 无法映射到 SDK 类型,不做降级

        # EXTRA_INDEX_A 的 get_stock_list 会 SDK 端阻塞(AGENTS.md 2026-07-07/09 已知),
        # 且泄漏 semaphore 导致进程退出。INDEX 代码集稳定(交易所维护,很少退市),
        # 直接全量不做降级。
        if sdk_type == "EXTRA_INDEX_A":
            return symbols, False

        # 预分类:取有效代码集合
        # 注意:EXTRA_INDEX_A 的 get_stock_list 会 SDK 端阻塞(AGENTS.md 已知),
        # 对该类型跳过预分类,直接试探单只代码决定降级。
        valid_set: set[str] = set()
        if sdk_type != "EXTRA_INDEX_A":
            try:
                valid_df = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._client.get_stock_list, security_type=sdk_type
                    ),
                    timeout=30,
                )
                valid_set = set(valid_df.index.tolist()) if valid_df is not None else set()
            except Exception as e:
                logger.debug(f"get_stock_list({sdk_type}) 失败,跳过降级: {e}")
                return symbols, False  # 预分类失败,不降级

        valid_codes = [s for s in symbols if s in valid_set]
        invalid_codes = [s for s in symbols if s not in valid_set]
        no_prefilter = len(valid_set) == 0  # INDEX 类型跳过了预分类

        if not invalid_codes:
            return symbols, False  # 全部有效,不需要降级

        # 试探单只无效代码(短超时 10s)
        # 用 invalid_codes 的第一只;若未预分类则用 symbols 的第一只
        probe_code = (invalid_codes if not no_prefilter else symbols)[:1]
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    self._client.get_kline,
                    code_list=probe_code,
                    begin_date=begin_date,
                    end_date=end_date,
                    interval=interval_str,
                ),
                timeout=10,
            )
            # 试探秒回 → SDK 无限制 → 全量
            logger.debug(f"试探通过({probe_code[0]} {interval_str}),全量同步")
            return symbols, False
        except asyncio.TimeoutError:
            if no_prefilter:
                # INDEX 类型无法预分类 → 试探超时 → 切小批量模式(每批 5 只)
                logger.warning(
                    f"试探超时({probe_code[0]} {interval_str}),"
                    f"INDEX 类型无法预分类,切小批量模式"
                )
                return symbols, True  # 全量传回 + small_batch 标记
            # 试探超时 → SDK 有限制 → 只用有效
            logger.warning(
                f"试探超时({probe_code[0]} {interval_str}),"
                f"降级为只同步 {len(valid_codes)} 只有效代码"
            )
            return valid_codes, False
        except Exception as e:
            # 试探报错(非超时)→ 保守只同步有效
            logger.warning(f"无效代码试探异常: {e},降级为只同步有效代码")
            return valid_codes

    def _convert_kline_dict(
        self, kline_dict: dict[str, pd.DataFrame], original_symbols: list[str]
    ) -> list[KlineBar]:
        """SDK 返回的 dict[str, DataFrame] → list[KlineBar]。"""
        bars: list[KlineBar] = []
        for symbol, df in kline_dict.items():
            if df is None or df.empty:
                continue

            # Pitfall 1 防护: reset_index 确保 trade_time 不丢失
            df_reset = df.reset_index()
            records = df_reset.to_dict("records")

            inferred_str = infer_security_type(symbol)
            inferred_security_type = SecurityType(inferred_str) if inferred_str else None

            for rec in records:
                # Pitfall 2 防护: 显式检查列名，使用 .get() 防御性取值
                trade_time_raw = rec.get("trade_time") or rec.get("kline_time")
                trade_time = _parse_trade_time(trade_time_raw)

                volume_raw = rec.get("volume")
                volume = int(volume_raw) if volume_raw is not None and pd.notna(volume_raw) else None

                bars.append(
                    KlineBar(
                        symbol=symbol,
                        trade_time=trade_time,
                        open=rec.get("open") if pd.notna(rec.get("open")) else None,
                        high=rec.get("high") if pd.notna(rec.get("high")) else None,
                        low=rec.get("low") if pd.notna(rec.get("low")) else None,
                        close=rec.get("close") if pd.notna(rec.get("close")) else None,
                        volume=volume,
                        amount=rec.get("amount") if pd.notna(rec.get("amount")) else None,
                        security_type=inferred_security_type or SecurityType.EXTRA_STOCK_A,
                    )
                )

        logger.debug(f"获取到 {len(bars)} 条K线数据，symbols={len(original_symbols)} 只")
        return bars

    async def get_stock_list(self, market: str) -> list[StockInfo]:
        """获取证券列表并转换为 domain 值对象.

        Args:
            market: 证券类型 (如 "EXTRA_ETF", "EXTRA_STOCK_A")

        Returns:
            StockInfo 列表
        """
        df: pd.DataFrame = await asyncio.to_thread(
            self._client.get_stock_list,
            security_type=market,
        )

        if df is None or df.empty:
            return []

        # DataFrame → list[StockInfo]
        df_reset = df.reset_index()
        records = df_reset.to_dict("records")
        stock_infos: list[StockInfo] = []
        for rec in records:
            # symbol 可能在 index 或 code 列
            symbol = rec.get("code") or rec.get("symbol") or rec.get("index")
            if symbol is None:
                continue

            list_date_raw = rec.get("LISTDATE") or rec.get("list_day") or rec.get("list_date")
            list_date = str(int(list_date_raw)) if pd.notna(list_date_raw) else None

            stock_infos.append(
                StockInfo(
                    symbol=str(symbol),
                    list_date=list_date,
                )
            )

        logger.debug(f"获取到 {len(stock_infos)} 只证券，market={market}")
        return stock_infos

    async def get_listing_dates(self, symbols: list[str]) -> dict[str, date]:
        """获取证券上市日期.

        Args:
            symbols: 证券代码列表

        Returns:
            {symbol: 上市日期} 字典
        """
        # SDK 返回 {symbol: str|None}，需要转换为 {symbol: date|None}
        raw_dates: dict[str, str | None] = await asyncio.to_thread(
            self._client.get_listing_dates,
            symbols=symbols,
        )

        result: dict[str, date] = {}
        for symbol, date_str in raw_dates.items():
            if date_str is not None:
                try:
                    result[symbol] = datetime.strptime(str(date_str)[:8], "%Y%m%d").date()
                except ValueError:
                    logger.warning(f"无法解析 {symbol} 的上市日期: {date_str}")
            # 不在结果中包含无法解析的日期

        return result


def _parse_trade_time(value) -> datetime:
    """解析交易时间值,兼容多种格式.

    返回带北京时区(CST)的 aware datetime。SDK 字面值是北京 wall-clock。
    """
    from galaxy_core.shared_kernel.utils.constants import localize_cst

    if isinstance(value, datetime):
        return localize_cst(value)

    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise ValueError("无法解析交易时间: 值为 None")

    if isinstance(value, str):
        # 尝试常见格式
        for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
            try:
                return localize_cst(datetime.strptime(value[:len(fmt.replace('%', 'X'))], fmt))
            except ValueError:
                continue
        # 最后尝试前 8 位
        try:
            return localize_cst(datetime.strptime(value[:8], "%Y%m%d"))
        except ValueError:
            pass

    if isinstance(value, int):
        return localize_cst(datetime.strptime(str(value)[:8], "%Y%m%d"))

    raise ValueError(f"无法解析交易时间: {value} (type={type(value)})")
