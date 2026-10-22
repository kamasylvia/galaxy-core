"""AkshareFundFlowProviderAdapter 单元测试.

monkeypatch akshare 模块函数,验证参数透传 + None/empty 防御。

2026-06-19 范围修订后(见 02-SCOPE-REVISION-REPORT.md)仅 1 方法:
get_sector_fund_flow。原 5 方法(sector/individual/north/market/industry_pe)收敛为 1。

注:akshare 用模块级 __getattr__ 懒加载子模块,pytest monkeypatch.setattr 字符串
路径会触发 annotated_getattr 走懒加载分支报 AttributeError。改为显式 import akshare
后 setattr akshare 模块对象(绕开字符串路径解析)。
"""

import asyncio

import akshare
import pandas as pd
import pytest

from galaxy_core.third_party.akshare.adapters.akshare_fund_flow_adapter import (
    AkshareFundFlowProviderAdapter,
)


@pytest.fixture
def adapter():
    return AkshareFundFlowProviderAdapter()


def _patch(monkeypatch, func_name: str, fake):
    """setattr akshare 模块的 func_name(显式对象,非字符串路径).

    akshare 用模块级 __getattr__ 懒加载子模块。用 hasattr(而非 getattr)触发懒加载
    避免抛异常;若仍不存在则 raising=False setattr 让其新建。
    """
    if not hasattr(akshare, func_name):
        # 懒加载未触发,强制 setattr 新建(raising=False)
        monkeypatch.setattr(akshare, func_name, fake, raising=False)
    else:
        monkeypatch.setattr(akshare, func_name, fake)


class TestAkshareFundFlowAdapter:
    def test_get_sector_fund_flow_passes_indicator_sector_type(self, adapter, monkeypatch):
        captured = {}

        def fake(indicator, sector_type):
            captured["indicator"] = indicator
            captured["sector_type"] = sector_type
            return pd.DataFrame()

        _patch(monkeypatch, "stock_sector_fund_flow_rank", fake)
        asyncio.run(adapter.get_sector_fund_flow("今日", "行业资金流"))
        assert captured == {"indicator": "今日", "sector_type": "行业资金流"}

    def test_empty_dataframe_returns_empty_not_raise(self, adapter, monkeypatch):
        """RESEARCH §A15:akshare 返空 df,adapter 不抛返 empty df."""
        _patch(monkeypatch, "stock_sector_fund_flow_rank", lambda **kw: pd.DataFrame())
        result = asyncio.run(adapter.get_sector_fund_flow())
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_none_return_defended(self, adapter, monkeypatch):
        """RESEARCH §A15:akshare 返 None,adapter 防御返 empty df 不崩."""
        _patch(monkeypatch, "stock_sector_fund_flow_rank", lambda **kw: None)
        result = asyncio.run(adapter.get_sector_fund_flow())
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_exception_returns_empty_df(self, adapter, monkeypatch):
        """SDK 抛异常,adapter log warning + 返 empty df(不抛,让 job mark_failed)."""
        def raise_fn(**kw):
            raise RuntimeError("network down")

        _patch(monkeypatch, "stock_sector_fund_flow_rank", raise_fn)
        result = asyncio.run(adapter.get_sector_fund_flow())
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_no_client_parameter(self, adapter):
        """关键回归:akshare adapter 无 client 参数(stateless)."""
        import inspect
        sig = inspect.signature(AkshareFundFlowProviderAdapter.__init__)
        params = [p for p in sig.parameters if p != "self"]
        assert params == [], f"akshare __init__ 应无参数,实得 {params}"
