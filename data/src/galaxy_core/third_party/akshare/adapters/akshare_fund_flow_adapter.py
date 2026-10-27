"""akshare 资金流 provider adapter — 实现 FundFlowProviderPort 的 akshare 部分.

asyncio.to_thread() 集中在此 adapter 层。无 client 注入(akshare 是 stateless lib,
顶部 `import akshare as ak`)。无 _get_local_path(akshare 无 HDF5 缓存)。

防御性处理:每个方法显式判 None/empty(RESEARCH §A15 — akshare 接口偶发返 None/空 df),
返回空 DataFrame 而非 None/抛异常,让 job 层 mark_failed。

2026-06-19 范围修订(见 02-SCOPE-REVISION-REPORT.md):
原 5 方法(板块/个股/北向/大盘资金流 + 行业 PE)收敛为 1 方法(板块资金流)。
删除的 4 方法对应表未启用, 不建表, 仅留 .planning 备查。
"""

import asyncio
import logging

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)


class AkshareFundFlowProviderAdapter:
    """FundFlowProviderPort 实现(akshare 部分)— stateless 包装 akshare 接口.

    1 async 方法:板块资金流(范围修订后)。
    """

    def __init__(self) -> None:
        """stateless adapter,无构造参数."""

    async def get_sector_fund_flow(
        self, indicator: str = "今日", sector_type: str = "行业资金流"
    ) -> pd.DataFrame:
        """获取板块资金流排名(仅当日快照).

        对应 akshare stock_sector_fund_flow_rank(indicator, sector_type)。
        scheduler 日度累积建库, 直答「主力在哪个行业」。
        """
        try:
            df = await asyncio.to_thread(
                ak.stock_sector_fund_flow_rank,
                indicator=indicator,
                sector_type=sector_type,
            )
        except Exception as e:
            logger.warning("akshare get_sector_fund_flow 失败: %s", e)
            return pd.DataFrame()
        return df if df is not None else pd.DataFrame()
