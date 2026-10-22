"""AmazingData 资金流向 provider adapter — 实现 FundFlowProviderPort 的 AmazingData 部分.

asyncio.to_thread() 集中在此 adapter 层。构造注入 AmazingDataClient(复用现有),
保留 _get_local_path(HDF5 缓存,镜像 financial/exchange_index adapter)。

CRITICAL:get_margin_detail 返回 dict[str, DataFrame](经 _normalize_to_dict 归一),
其余 3 方法返回 DataFrame。adapter 层不做 DataFrame→VO(job 层负责)。
"""

import asyncio
import logging
from pathlib import Path

import pandas as pd

from galaxy_core.amazing_data.api.client import AmazingDataClient
from galaxy_core.shared_kernel.utils.config_loader import get_section

logger = logging.getLogger(__name__)


class FundFlowProviderAdapter:
    """FundFlowProviderPort 实现(AmazingData 部分)— 包装 AmazingDataClient 资金流向接口.

    4 async 方法:龙虎榜/大宗交易/两融汇总/两融明细。
    """

    def __init__(self, client: AmazingDataClient) -> None:
        self._client = client
        # SDK 阻塞型调用的 asyncio.wait_for 超时上限。防止 to_thread 包装的
        # SDK 调用在 AM 端挂起(hrtimer sleep)时无限阻塞事件循环(AGENTS.md
        # 2026-07-11 修复 3 要求所有 to_thread 必须包 wait_for,本 adapter 原漏)。
        self._api_timeout = get_section("amazing_data").get("api_timeout_seconds", 600)

    def _get_local_path(self) -> str:
        """从配置获取本地 HDF5 缓存绝对路径(SDK 要求绝对路径).

        与 exchange_index/financial adapter 的 _get_local_path 一致。
        """
        raw_cache = get_section("amazing_data").get("local_path", "./data/local_cache/")
        local_path = str(Path(raw_cache).resolve())
        if raw_cache.endswith("/"):
            local_path += "/"
        return local_path

    @staticmethod
    def _normalize_to_dict(
        data: dict[str, pd.DataFrame] | pd.DataFrame,
    ) -> dict[str, pd.DataFrame]:
        """将 SDK 返回数据统一为 dict[str, DataFrame].

        get_margin_detail SDK 可能返回 dict(按 code 分组)或单 DataFrame。
        空 DataFrame → {};非空 DataFrame → {"_all": df};dict passthrough。
        镜像 financial_data_provider_adapter.py:62-77。
        """
        if isinstance(data, pd.DataFrame):
            if data.empty:
                return {}
            return {"_all": data}
        if isinstance(data, dict):
            return data
        return {}

    async def get_long_hu_bang(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """获取龙虎榜明细.

        Raises:
            asyncio.TimeoutError: SDK 调用超过 self._api_timeout 秒
        """
        data = await asyncio.wait_for(
            asyncio.to_thread(
                self._client.get_long_hu_bang,
                code_list=code_list,
                local_path=local_path,
                is_local=is_local,
                begin_date=begin_date,
                end_date=end_date,
            ),
            timeout=self._api_timeout,
        )
        return data if isinstance(data, pd.DataFrame) else pd.DataFrame()

    async def get_block_trading(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """获取大宗交易明细.

        Raises:
            asyncio.TimeoutError: SDK 调用超过 self._api_timeout 秒
        """
        data = await asyncio.wait_for(
            asyncio.to_thread(
                self._client.get_block_trading,
                code_list=code_list,
                local_path=local_path,
                is_local=is_local,
                begin_date=begin_date,
                end_date=end_date,
            ),
            timeout=self._api_timeout,
        )
        return data if isinstance(data, pd.DataFrame) else pd.DataFrame()

    async def get_margin_summary(
        self,
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """获取两融汇总(全市场,无 code_list 参数).

        Raises:
            asyncio.TimeoutError: SDK 调用超过 self._api_timeout 秒
        """
        data = await asyncio.wait_for(
            asyncio.to_thread(
                self._client.get_margin_summary,
                local_path=local_path,
                is_local=is_local,
                begin_date=begin_date,
                end_date=end_date,
            ),
            timeout=self._api_timeout,
        )
        return data if isinstance(data, pd.DataFrame) else pd.DataFrame()

    async def get_margin_detail(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        """获取两融明细(返回 dict[str, DataFrame],经 _normalize_to_dict 归一).

        CRITICAL:返回 dict 非 DataFrame,与其余 3 方法不同。
        margin_detail 对无效代码严重卡顿(实测 5有效=3.4s, 5有效+1无效=35.1s = 10x)。
        调用前过滤无效代码(用 get_stock_list 预分类 + 试探)。
        """
        effective = await self._filter_invalid_codes(code_list)
        data = await asyncio.wait_for(
            asyncio.to_thread(
                self._client.get_margin_detail,
                code_list=effective,
                local_path=local_path,
                is_local=is_local,
                begin_date=begin_date,
                end_date=end_date,
            ),
            timeout=self._api_timeout,
        )
        return self._normalize_to_dict(data)

    async def _filter_invalid_codes(self, code_list: list[str]) -> list[str]:
        """过滤无效代码:预分类(get_stock_list) + 试探。

        margin_detail 对无效代码 10x 慢,需过滤。long_hu_bang/block_trading 不敏感,不需调用此方法。
        """
        if not code_list:
            return code_list
        # 推断 SDK 宽类型
        from galaxy_core.shared_kernel.utils.symbol_type_inference import infer_security_type
        first_type = infer_security_type(code_list[0])
        sdk_type = {
            "SH_A": "EXTRA_STOCK_A", "SZ_A": "EXTRA_STOCK_A", "BJ_A": "EXTRA_STOCK_A",
            "SH_ETF": "EXTRA_ETF", "SZ_ETF": "EXTRA_ETF",
        }.get(first_type)
        if not sdk_type or sdk_type == "EXTRA_INDEX_A":
            return code_list  # INDEX 类型 get_stock_list 会阻塞,不过滤

        # 预分类
        try:
            import asyncio
            valid_df = await asyncio.wait_for(
                asyncio.to_thread(self._client.get_stock_list, security_type=sdk_type),
                timeout=30,
            )
            valid_set = set(valid_df.index.tolist()) if valid_df is not None else set()
        except Exception:
            return code_list  # 预分类失败,不过滤

        valid_codes = [c for c in code_list if c in valid_set]
        invalid_codes = [c for c in code_list if c not in valid_set]

        if not invalid_codes:
            return code_list  # 全有效

        # 试探单只无效代码(10s 超时)
        import asyncio
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    self._client.get_margin_detail,
                    code_list=invalid_codes[:1],
                    local_path="", is_local=False, begin_date=20240101, end_date=20240102,
                ),
                timeout=10,
            )
            return code_list  # 试探通过,SDK 无限制,全量
        except asyncio.TimeoutError:
            logger.warning(
                f"margin_detail 无效代码试探超时,过滤 {len(invalid_codes)} 只无效,"
                f"只用 {len(valid_codes)} 只有效"
            )
            return valid_codes if valid_codes else code_list
        except Exception:
            return valid_codes if valid_codes else code_list
