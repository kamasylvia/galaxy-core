"""回归测试 — akshare adapter 空 DataFrame 防御(RESEARCH §A15).

AkshareFundFlowProviderAdapter 1 方法(板块资金流, 2026-06-19 范围修订后)在 SDK 抛异常
或返 None 时必须返空 pd.DataFrame(),不向上抛。这是 02-05 实现的关键不变量。

mock 策略:monkeypatch adapter 模块的 `ak` 引用(顶部 `import akshare as ak`),
注入受控 side_effect。asyncio.to_thread 调 sync mock → adapter 的 try/except
捕获 → 返空 DataFrame。
"""

import pandas as pd
import pytest

from galaxy_core.third_party.akshare.adapters import (
    akshare_fund_flow_adapter as adapter_mod,
)
from galaxy_core.third_party.akshare.adapters.akshare_fund_flow_adapter import (
    AkshareFundFlowProviderAdapter,
)


@pytest.fixture
def adapter():
    return AkshareFundFlowProviderAdapter()


def _set_ak_funcs(monkeypatch, **funcs):
    """注入受控 ak.* 函数到 adapter 模块的 ak 引用."""
    fake_ak = type("FakeAk", (), {})()  # bare namespace
    for name, fn in funcs.items():
        setattr(fake_ak, name, fn)
    monkeypatch.setattr(adapter_mod, "ak", fake_ak)


class TestSectorFundFlowEmptyDefensive:
    """get_sector_fund_flow 空/异常防御."""

    @pytest.mark.asyncio
    async def test_none_returns_empty_df(self, adapter, monkeypatch):
        _set_ak_funcs(
            monkeypatch,
            stock_sector_fund_flow_rank=lambda **kw: None,
        )
        result = await adapter.get_sector_fund_flow()
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @pytest.mark.asyncio
    async def test_exception_returns_empty_df(self, adapter, monkeypatch):
        def _raise(**kw):
            raise RuntimeError("akshare down")
        _set_ak_funcs(monkeypatch, stock_sector_fund_flow_rank=_raise)
        result = await adapter.get_sector_fund_flow()
        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestSourceCodeDefensivePattern:
    """源码层:方法含 try/except + return pd.DataFrame() 防御(范围修订后 ≥ 1)."""

    def test_adapter_contains_empty_df_returns(self):
        from pathlib import Path
        src = Path(
            "data/src/galaxy_core/third_party/akshare/adapters/akshare_fund_flow_adapter.py"
        ).read_text()
        # 防御模式:方法 try/except + return pd.DataFrame()
        empty_returns = src.count("return pd.DataFrame()")
        assert empty_returns >= 1, (
            f"akshare_fund_flow_adapter 方法应有 return pd.DataFrame() 防御,"
            f"实际 {empty_returns} 处"
        )
        # `df if df is not None else pd.DataFrame()` 模式
        assert "is not None" in src, (
            "adapter 应用 `df if df is not None else pd.DataFrame()` 模式"
        )
