"""行业指数提供者适配器单元测试.

验证 adapter 正确包装 SDK 调用，并从 base_info 提取 INDEX_CODE 列表。
"""

import asyncio
import time
from unittest.mock import MagicMock

import pandas as pd
import pytest

from galaxy_core.amazing_data.api.adapters.industry_index_provider_adapter import (
    IndustryIndexProviderAdapter,
)


@pytest.fixture
def adapter():
    class _FakeClient:
        def __init__(self) -> None:
            self.get_industry_base_info = lambda **kw: pd.DataFrame()
            self.get_industry_constituent = lambda **kw: {}
            self.get_industry_weight = lambda **kw: {}
            self.get_industry_daily = lambda **kw: {}

    return IndustryIndexProviderAdapter(client=_FakeClient())


class TestGetIndustryBaseInfo:
    async def test_returns_dataframe(self, adapter):
        df = pd.DataFrame({"INDEX_CODE": ["BK0001"], "INDUSTRY_CODE": ["I01"]})
        adapter._client.get_industry_base_info = lambda **kw: df
        result = await adapter.get_industry_base_info("/cache/", is_local=False)
        assert len(result) == 1
        assert "INDEX_CODE" in result.columns

    async def test_non_df_returns_empty(self, adapter):
        adapter._client.get_industry_base_info = lambda **kw: None
        result = await adapter.get_industry_base_info("/cache/")
        assert result.empty


class TestGetIndustryDaily:
    async def test_passes_date_params(self, adapter):
        captured = {}

        def fake(**kw):
            captured.update(kw)
            return {}

        adapter._client.get_industry_daily = fake
        await adapter.get_industry_daily(
            ["BK0001"], "/cache/", begin_date=20240101, end_date=20240105,
        )
        assert captured["begin_date"] == 20240101
        assert captured["end_date"] == 20240105


class TestGetIndustryIndexCodes:
    async def test_extracts_unique_codes(self, adapter):
        df = pd.DataFrame({"INDEX_CODE": ["BK0001", "BK0002", "BK0001"]})
        adapter._client.get_industry_base_info = lambda **kw: df
        codes = await adapter.get_industry_index_codes("/cache/")
        assert codes == ["BK0001", "BK0002"]

    async def test_empty_df_returns_empty(self, adapter):
        adapter._client.get_industry_base_info = lambda **kw: pd.DataFrame()
        codes = await adapter.get_industry_index_codes("/cache/")
        assert codes == []

    async def test_missing_index_code_col(self, adapter):
        df = pd.DataFrame({"OTHER_COL": ["x"]})
        adapter._client.get_industry_base_info = lambda **kw: df
        codes = await adapter.get_industry_index_codes("/cache/")
        assert codes == []


class TestIndustryTimeoutProtection:
    """超时保护测试(2026-07-28: 4 方法补 asyncio.wait_for)。

    背景: 原 get_industry_base_info/constituent/weight/daily 的 to_thread 无超时,
    AM 端挂起(hrtimer sleep)时无限阻塞,卡死整个 industry job + scheduler 调用链
    (AGENTS.md 2026-07-14 P1 同模式遗留)。修复后 SDK 阻塞超过 _api_timeout 秒
    即抛 TimeoutError(传到 sync_with_retry 触发重试,不再无限卡死)。
    """

    def _blocking_client(self, method_name: str) -> MagicMock:
        """构造 SDK 调用永久阻塞的 mock client(模拟 AM 端 hrtimer sleep)。"""
        client = MagicMock()

        def block_forever(*args, **kwargs):  # noqa: ARG001
            time.sleep(2)  # 远超测试超时,模拟 SDK 挂起

        setattr(client, method_name, MagicMock(side_effect=block_forever))
        return client

    def test_get_industry_base_info_times_out(self):
        """get_industry_base_info SDK 阻塞超时 → TimeoutError。"""
        adapter = IndustryIndexProviderAdapter(
            self._blocking_client("get_industry_base_info")
        )
        adapter._api_timeout = 0.1
        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(adapter.get_industry_base_info("/cache/", is_local=False))

    def test_get_industry_constituent_times_out(self):
        """get_industry_constituent SDK 阻塞超时 → TimeoutError。"""
        adapter = IndustryIndexProviderAdapter(
            self._blocking_client("get_industry_constituent")
        )
        adapter._api_timeout = 0.1
        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(
                adapter.get_industry_constituent(
                    ["801001.SI"], "/cache/", is_local=False
                )
            )

    def test_get_industry_weight_times_out(self):
        """get_industry_weight SDK 阻塞超时 → TimeoutError。"""
        adapter = IndustryIndexProviderAdapter(
            self._blocking_client("get_industry_weight")
        )
        adapter._api_timeout = 0.1
        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(
                adapter.get_industry_weight(
                    ["801001.SI"], "/cache/", is_local=False,
                    begin_date=20240101, end_date=20240131,
                )
            )

    def test_get_industry_daily_times_out(self):
        """get_industry_daily SDK 阻塞超时 → TimeoutError。"""
        adapter = IndustryIndexProviderAdapter(
            self._blocking_client("get_industry_daily")
        )
        adapter._api_timeout = 0.1
        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(
                adapter.get_industry_daily(
                    ["801001.SI"], "/cache/", is_local=False,
                    begin_date=20240101, end_date=20240131,
                )
            )
