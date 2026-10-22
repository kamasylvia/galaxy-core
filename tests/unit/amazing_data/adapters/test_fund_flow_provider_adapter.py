"""FundFlowProviderAdapter(AmazingData)单元测试.

mock AmazingDataClient,验证 4 方法透传 + get_margin_summary 无 code_list +
get_margin_detail 返 dict 经 _normalize_to_dict 归一。
"""

import asyncio
from unittest.mock import MagicMock

import pandas as pd
import pytest

from galaxy_core.amazing_data.api.adapters.fund_flow_provider_adapter import (
    FundFlowProviderAdapter,
)


@pytest.fixture
def adapter():
    mock_client = MagicMock()
    mock_client.get_long_hu_bang.return_value = pd.DataFrame()
    mock_client.get_block_trading.return_value = pd.DataFrame()
    mock_client.get_margin_summary.return_value = pd.DataFrame()
    mock_client.get_margin_detail.return_value = {}
    return FundFlowProviderAdapter(mock_client)


class TestFundFlowProviderAdapter:
    def test_get_long_hu_bang_passes_code_list(self, adapter):
        asyncio.run(
            adapter.get_long_hu_bang(
                code_list=["600000"], local_path="/tmp/x", begin_date=20240101, end_date=20240131
            )
        )
        adapter._client.get_long_hu_bang.assert_called_once_with(
            code_list=["600000"],
            local_path="/tmp/x",
            is_local=True,
            begin_date=20240101,
            end_date=20240131,
        )

    def test_get_block_trading_passes_code_list(self, adapter):
        asyncio.run(
            adapter.get_block_trading(
                code_list=["600000"], local_path="/tmp/x", begin_date=20240101, end_date=20240131
            )
        )
        adapter._client.get_block_trading.assert_called_once()

    def test_get_margin_summary_no_code_list(self, adapter):
        """关键回归:get_margin_summary 不传 code_list(全市场汇总,RESEARCH §A16)."""
        asyncio.run(
            adapter.get_margin_summary(local_path="/tmp/x", begin_date=20240101, end_date=20240131)
        )
        kwargs = adapter._client.get_margin_summary.call_args.kwargs
        assert "code_list" not in kwargs
        assert kwargs["local_path"] == "/tmp/x"

    def test_get_margin_detail_returns_dict_normalized_passthrough(self, adapter):
        """get_margin_detail SDK 返 dict,_normalize_to_dict passthrough."""
        df = pd.DataFrame({"x": [1]})
        adapter._client.get_margin_detail.return_value = {"600000.SH": df}
        result = asyncio.run(
            adapter.get_margin_detail(
                code_list=["600000"], local_path="/tmp/x", begin_date=20240101, end_date=20240131
            )
        )
        assert result == {"600000.SH": df}

    def test_get_margin_detail_dataframe_normalized_to_all_key(self, adapter):
        """SDK 返单 DataFrame,_normalize_to_dict 转 {"_all": df}."""
        df = pd.DataFrame({"x": [1]})
        adapter._client.get_margin_detail.return_value = df
        result = asyncio.run(adapter.get_margin_detail(["600000"], "/tmp/x"))
        assert "_all" in result
        assert result["_all"] is df

    def test_get_margin_detail_empty_dataframe_returns_empty_dict(self, adapter):
        """SDK 返空 DataFrame → _normalize_to_dict → {}."""
        adapter._client.get_margin_detail.return_value = pd.DataFrame()
        result = asyncio.run(adapter.get_margin_detail(["600000"], "/tmp/x"))
        assert result == {}

    def test_get_margin_detail_return_annotation_is_dict(self):
        """get_margin_detail 返回注解为 dict[str, pd.DataFrame](Port 契约)."""
        import inspect
        sig = inspect.signature(FundFlowProviderAdapter.get_margin_detail)
        assert "dict" in str(sig.return_annotation)

    def test_normalize_to_dict_empty_dataframe(self):
        """_normalize_to_dict 空 df → {}."""
        result = FundFlowProviderAdapter._normalize_to_dict(pd.DataFrame())
        assert result == {}

    def test_normalize_to_dict_non_empty_dataframe(self):
        """_normalize_to_dict 非空 df → {"_all": df}."""
        df = pd.DataFrame({"x": [1]})
        result = FundFlowProviderAdapter._normalize_to_dict(df)
        assert result == {"_all": df}

    def test_normalize_to_dict_passthrough(self):
        """_normalize_to_dict dict → passthrough."""
        df = pd.DataFrame({"x": [1]})
        result = FundFlowProviderAdapter._normalize_to_dict({"k": df})
        assert result == {"k": df}

    def test_normalize_to_dict_other_returns_empty(self):
        """_normalize_to_dict 其他类型 → {}."""
        result = FundFlowProviderAdapter._normalize_to_dict("garbage")
        assert result == {}

    def test_get_margin_detail_dict_passthrough_other_data(self, adapter):
        """SDK 返非 df/dict(None),_normalize_to_dict → {}."""
        adapter._client.get_margin_detail.return_value = None
        result = asyncio.run(adapter.get_margin_detail(["600000"], "/tmp/x"))
        assert result == {}


class TestFundFlowTimeoutProtection:
    """超时保护测试(2026-07-14: 4 方法补 asyncio.wait_for)。

    背景: 原 get_long_hu_bang/block_trading/margin_summary/margin_detail 的
    to_thread 无超时,AM 端挂起(hrtimer sleep)时无限阻塞,卡死整个 fundflow
    job。修复后 SDK 阻塞超过 _api_timeout 秒即抛 TimeoutError(传到
    sync_with_retry 触发重试,不再无限卡死)。
    """

    def _blocking_client(self, method_name: str) -> MagicMock:
        """构造 SDK 调用永久阻塞的 mock client(模拟 AM 端 hrtimer sleep)。"""
        client = MagicMock()

        def block_forever(*args, **kwargs):  # noqa: ARG001
            import time

            time.sleep(2)  # 远超测试超时,模拟 SDK 挂起

        setattr(client, method_name, MagicMock(side_effect=block_forever))
        return client

    def test_get_long_hu_bang_times_out(self):
        """get_long_hu_bang SDK 阻塞超时 → TimeoutError。"""
        adapter = FundFlowProviderAdapter(self._blocking_client("get_long_hu_bang"))
        adapter._api_timeout = 0.1  # 缩短超时加速测试
        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(
                adapter.get_long_hu_bang(
                    code_list=["600000"], local_path="/tmp/x", begin_date=20240101, end_date=20240131
                )
            )

    def test_get_block_trading_times_out(self):
        """get_block_trading SDK 阻塞超时 → TimeoutError。"""
        adapter = FundFlowProviderAdapter(self._blocking_client("get_block_trading"))
        adapter._api_timeout = 0.1
        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(
                adapter.get_block_trading(
                    code_list=["600000"], local_path="/tmp/x", begin_date=20240101, end_date=20240131
                )
            )

    def test_get_margin_summary_times_out(self):
        """get_margin_summary SDK 阻塞超时 → TimeoutError。"""
        adapter = FundFlowProviderAdapter(self._blocking_client("get_margin_summary"))
        adapter._api_timeout = 0.1
        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(
                adapter.get_margin_summary(local_path="/tmp/x", begin_date=20240101, end_date=20240131)
            )

    def test_get_margin_detail_times_out(self):
        """get_margin_detail SDK 阻塞超时 → TimeoutError(margin_detail 经 _filter_invalid_codes)。"""
        client = MagicMock()
        # get_stock_list 预分类快速返回,让流程走到 get_margin_detail 阻塞点
        client.get_stock_list.return_value = pd.DataFrame(index=["600000.SH"])
        import time

        client.get_margin_detail.side_effect = lambda *a, **k: time.sleep(2)
        adapter = FundFlowProviderAdapter(client)
        adapter._api_timeout = 0.1
        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(
                adapter.get_margin_detail(
                    code_list=["600000.SH"], local_path="/tmp/x", begin_date=20240101, end_date=20240131
                )
            )
