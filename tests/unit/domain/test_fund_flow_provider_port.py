"""FundFlowProviderPort Protocol 合规性测试.

dummy 实现 5 async 方法(akshare 1 + amazingdata 4, 2026-06-19 范围修订后)。
关键回归:get_margin_detail 返回 dict[str, DataFrame] 非 DataFrame;
get_margin_summary 无 code_list 参数。
"""

import asyncio
import inspect

import pandas as pd

from galaxy_core.domain.ports import FundFlowProviderPort


class DummyFundFlowProvider:
    """FundFlowProviderPort 的 dummy 实现(5 async 方法, 范围修订后).

    get_margin_detail 返回空 dict(对齐 dict 契约),其余返回空 DataFrame。
    """

    # akshare 侧(1)

    async def get_sector_fund_flow(
        self, indicator: str, sector_type: str
    ) -> pd.DataFrame:
        return pd.DataFrame()

    # amazingdata 侧(4)

    async def get_long_hu_bang(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        return pd.DataFrame()

    async def get_block_trading(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        return pd.DataFrame()

    async def get_margin_summary(
        self,
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        return pd.DataFrame()

    async def get_margin_detail(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        return {}


class TestFundFlowProviderPort:
    """FundFlowProviderPort Protocol 合规性测试."""

    def test_dummy_is_instance(self):
        """DummyFundFlowProvider 应满足 FundFlowProviderPort Protocol."""
        dummy = DummyFundFlowProvider()
        assert isinstance(dummy, FundFlowProviderPort)

    def test_get_margin_detail_returns_dict(self):
        """关键回归:get_margin_detail 返回 dict[str, DataFrame] 非 DataFrame(RESEARCH §4 A16)."""
        dummy = DummyFundFlowProvider()
        result = asyncio.run(
            dummy.get_margin_detail(["600000"], "/tmp/cache")
        )
        assert isinstance(result, dict)

    def test_get_margin_summary_no_code_list(self):
        """get_margin_summary 无 code_list 参数(全市场汇总,RESEARCH §A16)."""
        sig = inspect.signature(FundFlowProviderPort.get_margin_summary)
        params = list(sig.parameters.keys())
        assert "code_list" not in params

    def test_all_5_methods_present(self):
        """dummy 应有全部 5 个 async 方法(akshare 1 + amazingdata 4, 范围修订后)."""
        dummy = DummyFundFlowProvider()
        expected = [
            "get_sector_fund_flow",
            "get_long_hu_bang",
            "get_block_trading",
            "get_margin_summary",
            "get_margin_detail",
        ]
        for name in expected:
            assert hasattr(dummy, name), f"missing method: {name}"

    def test_margin_detail_return_annotation_is_dict(self):
        """get_margin_detail 返回注解应为 dict[str, pd.DataFrame]."""
        sig = inspect.signature(FundFlowProviderPort.get_margin_detail)
        assert "dict" in str(sig.return_annotation)
