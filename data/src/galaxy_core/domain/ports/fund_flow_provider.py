"""资金流向数据提供者端口 — 同时对接 akshare 与 AmazingData 两源.

单 Protocol 合并两源资金流,因 DI 注入单一 FundFlowSyncJob
(RESEARCH §10 Q6 single-job 决议,CONTEXT D-10):
- akshare 侧(1 方法):板块资金流(2026-06-19 范围修订:原 5 方法收敛为 1)
- AmazingData 侧(4 方法):龙虎榜/大宗/两融汇总/两融明细(D-07)

CRITICAL: get_margin_detail 返回 dict[str, pd.DataFrame](key=market_code,
value=该标的券的明细 DataFrame),与其他 3 个 amazingdata 方法返回单
DataFrame 不同。adapter 层须 isinstance 分支处理(镜像
financial_data_provider_adapter._normalize_to_dict 模式,RESEARCH §4 A16)。
"""

from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class FundFlowProviderPort(Protocol):
    """资金流向提供者接口(async,to_thread 集中在 adapter).

    合并 akshare(1 方法)+ AmazingData(4 方法)共 5 方法(2026-06-19 范围修订)。

    CRITICAL 契约:get_margin_detail 返回 dict[str, pd.DataFrame]
    (keyed by market_code),非 DataFrame。adapter 层须 isinstance 分支处理,
    不可假设返回 DataFrame(回归 RESEARCH §8 风险清单)。
    """

    # =========================================================================
    # akshare 侧(1 方法 — 范围修订后)
    # =========================================================================

    async def get_sector_fund_flow(
        self, indicator: str, sector_type: str
    ) -> pd.DataFrame:
        """获取板块资金流排名(仅当日快照).

        对应 akshare stock_sector_fund_flow_rank(indicator, sector_type)。

        Args:
            indicator: 周期,'今日'/'5日'/'10日'
            sector_type: 板块类型,'行业资金流'/'概念资金流'/'地域资金流'

        Returns:
            DataFrame,每板块一行(仅当日快照,scheduler 日度累积建库)
        """
        ...

    # =========================================================================
    # AmazingData 侧(4 方法,SDK 复用现有 amazing_data 基础设施)
    # =========================================================================

    async def get_long_hu_bang(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """获取龙虎榜明细.

        对应 SDK get_long_hu_bang(code_list, local_path, is_local, **kwargs)。

        Args:
            code_list: 证券代码列表(单 code 循环最优,AGENTS.md 2026-06-16 chunk lesson)
            local_path: 本地 HDF5 缓存绝对路径
            is_local: True 仅本地;False 强制服务器获取(首次必须 False)
            begin_date: 起始日期 YYYYMMDD(可选)
            end_date: 截止日期 YYYYMMDD(可选)

        Returns:
            DataFrame,龙虎榜明细,列含
            MARKET_CODE/TRADE_DATE/SECURITY_NAME/REASON_TYPE/REASON_TYPE_NAME/
            CHANGE_RANGE/TRADER_NAME/FLOW_MARK/BUY_AMOUNT/SELL_AMOUNT/
            TOTAL_AMOUNT/TOTAL_VOLUME
        """
        ...

    async def get_block_trading(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """获取大宗交易明细.

        对应 SDK get_block_trading(code_list, ...)。

        Args:
            code_list: 证券代码列表
            local_path: 本地 HDF5 缓存绝对路径
            is_local: 本地缓存方案开关
            begin_date: 起始日期 YYYYMMDD(可选)
            end_date: 截止日期 YYYYMMDD(可选)

        Returns:
            DataFrame,大宗交易,列含
            MARKET_CODE/TRADE_DATE/B_SHARE_PRICE/B_SHARE_VOLUME/B_FREQUENCY/
            BLOCK_AVG_VOLUME/B_SHARE_AMOUNT/B_BUYER_NAME/B_SELLER_NAME
        """
        ...

    async def get_margin_summary(
        self,
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """获取两融汇总(全市场,无 code_list 参数).

        对应 SDK get_margin_summary(local_path, is_local, **kwargs)。

        Args:
            local_path: 本地 HDF5 缓存绝对路径
            is_local: 本地缓存方案开关
            begin_date: 起始日期 YYYYMMDD(可选)
            end_date: 截止日期 YYYYMMDD(可选)

        Returns:
            DataFrame,两融汇总,列含
            TRADE_DATE/SUM_BORROW_MONEY_BALANCE/SUM_PURCH_WITH_BORROW_MONEY/
            SUM_REPAYMENT_OF_BORROW_MONEY/SUM_SEC_LENDING_BALANCE/
            SUM_SALES_OF_BORROWED_SEC/SUM_MARGIN_TRADE_BALANCE
        """
        ...

    async def get_margin_detail(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        """获取两融明细(返回 dict 非 DataFrame).

        对应 SDK get_margin_detail(code_list, ...)。

        Args:
            code_list: 证券代码列表(单 code 循环最优,chunk lesson)
            local_path: 本地 HDF5 缓存绝对路径
            is_local: 本地缓存方案开关
            begin_date: 起始日期 YYYYMMDD(可选)
            end_date: 截止日期 YYYYMMDD(可选)

        Returns:
            **dict[str, pd.DataFrame]** keyed by market_code,value 为该标的券的
            融资融券明细 DataFrame(列含
            MARKET_CODE/SECURITY_NAME/TRADE_DATE/BORROW_MONEY_BALANCE/
            PURCH_WITH_BORROW_MONEY/REPAYMENT_OF_BORROW_MONEY/SEC_LENDING_BALANCE/
            SALES_OF_BORROWED_SEC/REPAYMENT_OF_BORROW_SEC/SEC_LENDING_BALANCE_VOL/
            MARGIN_TRADE_BALANCE)。

            CRITICAL:返回 dict[str, pd.DataFrame] 非 DataFrame,与其他 3 个
            amazingdata 方法返回单 DataFrame 不同。adapter 层须 isinstance 分支
            处理,不可假设返回 DataFrame。
        """
        ...
