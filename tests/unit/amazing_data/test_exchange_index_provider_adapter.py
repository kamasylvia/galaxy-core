"""交易所指数提供者适配器单元测试.

验证 adapter 正确通过 asyncio.to_thread 包装 SDK 调用，
并返回 dict[str, DataFrame] / list[str]。所有 SDK 调用 mock。
"""

import pandas as pd
import pytest

from galaxy_core.amazing_data.api.adapters.exchange_index_provider_adapter import (
    ExchangeIndexProviderAdapter,
)


class _FakeClient:
    """带可记录调用参数的 fake client."""

    def __init__(self) -> None:
        self.constituent_return: object = {}
        self.weight_return: object = {}
        self.stock_list_return: object = pd.DataFrame()
        self.last_weight_kwargs: dict = {}

    def get_index_constituent(self, **kw):
        return self.constituent_return

    def get_index_weight(self, **kw):
        self.last_weight_kwargs = kw
        return self.weight_return

    def get_stock_list(self, **kw):
        return self.stock_list_return


@pytest.fixture
def fake():
    return _FakeClient()


@pytest.fixture
def adapter(fake):
    return ExchangeIndexProviderAdapter(client=fake)


class TestGetIndexConstituent:
    async def test_returns_dict_from_client(self, adapter, fake):
        df = pd.DataFrame({"INDEX_CODE": ["000300.SH"], "CON_CODE": ["600000.SH"]})
        fake.constituent_return = {"000300.SH": df}

        result = await adapter.get_index_constituent(
            ["000300.SH"], "/cache/", is_local=False
        )

        assert "000300.SH" in result
        assert len(result["000300.SH"]) == 1

    async def test_non_dict_returns_empty(self, adapter, fake):
        fake.constituent_return = None
        result = await adapter.get_index_constituent([], "/cache/")
        assert result == {}


class TestGetIndexWeight:
    async def test_passes_date_params(self, adapter, fake):
        fake.weight_return = {}
        await adapter.get_index_weight(
            ["000300.SH"], "/cache/", is_local=False,
            begin_date=20240101, end_date=20240105,
        )
        assert fake.last_weight_kwargs["begin_date"] == 20240101
        assert fake.last_weight_kwargs["end_date"] == 20240105

    async def test_dates_optional(self, adapter, fake):
        """None 日期不应出现在转发给 SDK 的参数中（adapter 过滤 None）."""
        fake.weight_return = {}
        await adapter.get_index_weight(["000300.SH"], "/cache/")
        assert "begin_date" not in fake.last_weight_kwargs
        assert "end_date" not in fake.last_weight_kwargs


class TestGetIndexCodeList:
    async def test_extracts_from_index(self, adapter, fake):
        """SDK 的 get_code_info 返回 DataFrame，代码在 index（index 名 code_market）."""
        fake.stock_list_return = pd.DataFrame(
            {"symbol": ["沪深300", "上证50"]},
            index=pd.Index(["000300.SH", "000016.SH"], name="code_market"),
        )
        codes = await adapter.get_index_code_list("EXTRA_INDEX_A")
        assert codes == ["000300.SH", "000016.SH"]

    async def test_extracts_from_index_with_extra_columns(self, adapter, fake):
        """index 是 code，其余列（symbol/pre_close 等）应被忽略."""
        fake.stock_list_return = pd.DataFrame(
            {"symbol": ["沪深300", "上证50"], "pre_close": [4000.0, 3000.0]},
            index=pd.Index(["000300.SH", "000016.SH"], name="code_market"),
        )
        codes = await adapter.get_index_code_list("EXTRA_INDEX_A")
        assert codes == ["000300.SH", "000016.SH"]

    async def test_empty_df_returns_empty(self, adapter, fake):
        fake.stock_list_return = pd.DataFrame()
        codes = await adapter.get_index_code_list("EXTRA_INDEX_A")
        assert codes == []

    async def test_none_df_returns_empty(self, adapter, fake):
        fake.stock_list_return = None
        codes = await adapter.get_index_code_list("EXTRA_INDEX_A")
        assert codes == []
