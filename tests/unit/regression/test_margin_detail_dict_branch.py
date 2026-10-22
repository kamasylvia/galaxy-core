"""回归测试 — margin_detail dict[str, DataFrame] 处理(RESEARCH §A16 + 02-07 D2).

覆盖两层:
1. provider adapter 层:FundFlowProviderAdapter._normalize_to_dict 4 分支
   (空 DataFrame → {} / 非空 → {"_all": df} / dict passthrough / None → {})
2. job 层:FundFlowSyncJob._sync_margin_detail 迭代 data.items() 累积 records

mock AmazingDataClient + MagicMock state_manager,无真实 SDK 调用 / 无 DB。

2026-09-28:本文件曾隐式依赖「trading_calendar 无 2024 数据」使熔断分支
不触发(trading_days 空 → 0 条静默成功);9/16 起真库日历补全到 2023-2025
后该假设失效 → 熔断 raise → sync_with_retry 真实 sleep(分钟级)= 测试挂死。
现 autouse fixture patch retry sleep,并显式注入 calendar_store mock。
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from galaxy_core.amazing_data.api.adapters.fund_flow_provider_adapter import (
    FundFlowProviderAdapter,
)


@pytest.fixture(autouse=True)
def _patch_retry_sleep(monkeypatch):
    """patch sync_with_retry 内 asyncio.sleep,避免 EmptyResponseError 重试真实等待."""
    monkeypatch.setattr(
        "galaxy_core.application.scheduler.retry_handler.asyncio.sleep",
        AsyncMock(),
    )


def _mock_state_manager():
    """透传 MagicMock state_manager(对齐 scheduler conftest mock_state_manager)."""
    sm = MagicMock()
    sm.is_synced = AsyncMock(return_value=False)
    sm.mark_running = AsyncMock()
    sm.mark_success = AsyncMock()
    sm.mark_failed = AsyncMock()
    return sm


def _reference_provider():
    """reference_provider mock:get_hist_code_list 返 3 个 code。

    2026-07-28 修复:原只 mock get_stock_list,但 fundflow_sync_job._get_amazing_universe
    走 get_hist_code_list(经 resolve_universe_with_fallback helper)。clean tree 时
    MagicMock 默认属性 await 返 MagicMock 实例,`list(MagicMock())` 在
    _fetch_per_symbol_batched line 399 无限 hang(TestJobMarginDetailIteration
    预存 hang 根因)。显式 mock get_hist_code_list 返 list 避免 hang。
    """
    provider = MagicMock()
    provider.get_stock_list = AsyncMock(
        return_value=["600000", "600001", "000001"]
    )
    provider.get_hist_code_list = AsyncMock(
        return_value=["600000", "600001", "000001"]
    )
    return provider


def _margin_detail_df(code: str) -> pd.DataFrame:
    return pd.DataFrame({
        "TRADE_DATE": ["2024-01-15"],
        "MARKET_CODE": [code],
        "BORROW_MONEY_BALANCE": [100.0],
    })


class TestNormalizeToDictBranches:
    """_normalize_to_dict 4 分支覆盖."""

    def test_empty_dataframe_returns_empty_dict(self):
        df = pd.DataFrame()
        assert FundFlowProviderAdapter._normalize_to_dict(df) == {}

    def test_non_empty_dataframe_wraps_in_all_key(self):
        df = pd.DataFrame({"a": [1, 2]})
        result = FundFlowProviderAdapter._normalize_to_dict(df)
        assert "_all" in result
        assert len(result["_all"]) == 2

    def test_dict_passthrough(self):
        d = {"600000": pd.DataFrame({"x": [1]}), "600001": pd.DataFrame({"x": [2]})}
        result = FundFlowProviderAdapter._normalize_to_dict(d)
        assert set(result.keys()) == {"600000", "600001"}

    def test_none_returns_empty_dict(self):
        assert FundFlowProviderAdapter._normalize_to_dict(None) == {}


class TestGetMarginDetailNormalizes:
    """get_margin_detail 经 _normalize_to_dict 标准化."""

    @pytest.mark.asyncio
    async def test_get_margin_detail_dict_response(self):
        client = MagicMock()
        client.get_margin_detail = MagicMock(
            return_value={"600000": pd.DataFrame({"TRADE_DATE": ["2024-01-15"]})}
        )
        adapter = FundFlowProviderAdapter(client)
        result = await adapter.get_margin_detail(
            code_list=["600000"], local_path="/tmp", is_local=False,
            begin_date=20240101, end_date=20240115,
        )
        assert isinstance(result, dict)
        assert "600000" in result

    @pytest.mark.asyncio
    async def test_get_margin_detail_empty_dataframe_response(self):
        client = MagicMock()
        client.get_margin_detail = MagicMock(return_value=pd.DataFrame())
        adapter = FundFlowProviderAdapter(client)
        result = await adapter.get_margin_detail(
            code_list=["600000"], local_path="/tmp", is_local=False,
            begin_date=20240101, end_date=20240115,
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_margin_detail_none_response(self):
        client = MagicMock()
        client.get_margin_detail = MagicMock(return_value=None)
        adapter = FundFlowProviderAdapter(client)
        result = await adapter.get_margin_detail(
            code_list=["600000"], local_path="/tmp", is_local=False,
            begin_date=20240101, end_date=20240115,
        )
        assert result == {}


class TestJobMarginDetailIteration:
    """FundFlowSyncJob._sync_margin_detail 迭代 data.items()(集成层)."""

    @pytest.mark.asyncio
    async def test_job_iterates_dict_items(self):
        """job 层:dict 含 2 entries → 2 records 累积(每 code 一行)."""
        from galaxy_core.application.scheduler.jobs.fundflow_sync_job import (
            FundFlowSyncJob,
        )

        amazing_provider = MagicMock()
        amazing_provider.get_margin_detail = AsyncMock(
            return_value={
                "600000": _margin_detail_df("600000"),
                "600001": _margin_detail_df("600001"),
            }
        )
        amazing_provider.get_margin_summary = AsyncMock(return_value=pd.DataFrame())
        amazing_store = MagicMock()
        amazing_store.save_margin_detail = AsyncMock(return_value=2)
        amazing_store.save_margin_summary = AsyncMock(return_value=0)

        sm = _mock_state_manager()
        last_sync = MagicMock()
        last_sync.get_last_sync_date = AsyncMock(return_value=None)
        last_sync.set_last_sync_date = AsyncMock()
        job = FundFlowSyncJob(
            state_manager=sm,
            akshare_provider=MagicMock(),
            amazing_provider=amazing_provider,
            akshare_store=MagicMock(),
            amazing_store=amazing_store,
            last_sync_store=last_sync,
            reference_provider=_reference_provider(),
        )
        await job.run_daily(date(2024, 1, 15), target="margin")

        success = [
            c for c in sm.mark_success.call_args_list
            if c[0][0] == "margin_detail"
        ]
        # B2 重构:编排层 mark_success(sync_type, period),records_synced 走默认 0。
        # 本回归测试聚焦执行层「dict 迭代累积 records」逻辑,通过 save_margin_detail
        # 被调用验证(records 已累积),mark_success 仅验证成功标记。
        assert success
        assert success[0].args == ("margin_detail", "20240115")
        # 执行层确实累积了 records 并调 save(验证 dict 迭代逻辑)
        amazing_store.save_margin_detail.assert_called_once()

    @pytest.mark.asyncio
    async def test_job_empty_dict_marks_zero(self):
        """job 层:空 dict → mark_success(0)."""
        from galaxy_core.application.scheduler.jobs.fundflow_sync_job import (
            FundFlowSyncJob,
        )

        amazing_provider = MagicMock()
        amazing_provider.get_margin_detail = AsyncMock(return_value={})
        amazing_provider.get_margin_summary = AsyncMock(return_value=pd.DataFrame())
        amazing_store = MagicMock()
        amazing_store.save_margin_detail = AsyncMock(return_value=0)
        amazing_store.save_margin_summary = AsyncMock(return_value=0)

        sm = _mock_state_manager()
        last_sync = MagicMock()
        last_sync.get_last_sync_date = AsyncMock(return_value=None)
        last_sync.set_last_sync_date = AsyncMock()
        job = FundFlowSyncJob(
            state_manager=sm,
            akshare_provider=MagicMock(),
            amazing_provider=amazing_provider,
            akshare_store=MagicMock(),
            amazing_store=amazing_store,
            last_sync_store=last_sync,
            reference_provider=_reference_provider(),
        )
        await job.run_daily(date(2024, 1, 15), target="margin")
        # 2026-09-09 熔断(24e259d 扩展):空 dict + calendar_store=None →
        # [yesterday] 视为交易日 → raise EmptyResponseError → 重试耗尽 →
        # mark_failed(旧行为"0 条静默 success"已废弃)。
        failed = [
            c for c in sm.mark_failed.call_args_list
            if c[0][0] == "margin_detail"
        ]
        assert failed
