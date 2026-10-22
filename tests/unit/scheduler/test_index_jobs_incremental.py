"""Phase 03(03-04)index_weight + industry_weight 增量回归测试.

验证:
- index_weight 增量走 _resolve_incremental_range(scope_key=None 全局)
- industry_weight 同
- 空响应不推进 last_sync_date(D-08)
- 空表首次 begin=20130101,有数据 begin=last+1
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from galaxy_core.application.scheduler.jobs.exchange_index_sync_job import (
    ExchangeIndexSyncJob,
)
from galaxy_core.application.scheduler.jobs.industry_index_sync_job import (
    IndustryIndexSyncJob,
)


def _weight_df() -> pd.DataFrame:
    """单 index_weight 记录(trade_date str YYYYMMDD)."""
    return pd.DataFrame({
        "INDEX_CODE": ["000300.SH"],
        "CON_CODE": ["600000.SH"],
        "TRADE_DATE": ["20240115"],
        "WEIGHT": [5.0],
    })


def _make_last_sync_store(last=None):
    store = MagicMock()
    store.get_last_sync_date = AsyncMock(return_value=last)
    store.set_last_sync_date = AsyncMock()
    return store


def _make_index_job_config(monkeypatch, job_module):
    fake_config = {
        "index": {"index_weight_codes": ["000300.SH"]},
        "amazing_data": {"local_path": "./data/local_cache/"},
    }
    monkeypatch.setattr(
        f"galaxy_core.application.scheduler.jobs.{job_module}.get_section",
        lambda key: fake_config.get(key, {}),
    )


@pytest.fixture
def exchange_job(monkeypatch):
    _make_index_job_config(monkeypatch, "exchange_index_sync_job")
    state = MagicMock()
    state.is_synced = AsyncMock(return_value=False)
    state.mark_running = AsyncMock()
    state.mark_success = AsyncMock()
    state.mark_failed = AsyncMock()
    provider = MagicMock()
    provider.get_index_weight = AsyncMock(return_value={"000300.SH": _weight_df()})
    store = MagicMock()
    store.save_index_weight = AsyncMock(return_value=1)
    last_sync = _make_last_sync_store()
    job = ExchangeIndexSyncJob(
        state_manager=state,
        provider=provider,
        store=store,
        last_sync_store=last_sync,
    )
    return job, last_sync


@pytest.fixture
def industry_job(monkeypatch):
    _make_index_job_config(monkeypatch, "industry_index_sync_job")
    # patch retry_handler asyncio.sleep 避免 industry_daily 真重试等待
    monkeypatch.setattr(
        "galaxy_core.application.scheduler.retry_handler.asyncio.sleep",
        AsyncMock(),
    )
    state = MagicMock()
    state.is_synced = AsyncMock(return_value=False)
    state.mark_running = AsyncMock()
    state.mark_success = AsyncMock()
    state.mark_failed = AsyncMock()
    provider = MagicMock()
    provider.get_industry_index_codes = AsyncMock(return_value=["801010.SI"])
    provider.get_industry_weight = AsyncMock(return_value={"801010.SI": _weight_df()})
    # 2026-07-17:run_daily 现在先跑 industry_daily 再跑 industry_weight,
    # 需 mock get_industry_daily 避免未 mock 调用返 MagicMock 导致迭代 hang
    provider.get_industry_daily = AsyncMock(return_value={})
    store = MagicMock()
    store.save_industry_weight = AsyncMock(return_value=1)
    store.save_industry_daily = AsyncMock(return_value=0)
    store.get_industry_daily_last_date = AsyncMock(return_value=None)
    last_sync = _make_last_sync_store()
    job = IndustryIndexSyncJob(
        state_manager=state,
        provider=provider,
        store=store,
        last_sync_store=last_sync,
    )
    return job, last_sync


class TestIndexWeightIncremental:
    """index_weight 增量回归."""

    async def test_index_weight_advances_global_null_scope(self, exchange_job):
        job, last_sync = exchange_job
        await job.run_daily(date(2024, 1, 15))
        last_sync.set_last_sync_date.assert_any_call(
            "index_weight", None, date(2024, 1, 15)
        )

    async def test_index_weight_first_sync_20130101(self, exchange_job):
        """空表首次:last=None → begin=20130101."""
        job, last_sync = exchange_job
        last_sync.get_last_sync_date = AsyncMock(return_value=None)
        await job.run_daily(date(2024, 1, 15))
        call = job._provider.get_index_weight.call_args
        assert call.kwargs.get("begin_date") == 20130101

    async def test_index_weight_incremental_last_plus_one(self, exchange_job):
        """有数据 last=2024-01-10 → begin=20240111."""
        job, last_sync = exchange_job
        last_sync.get_last_sync_date = AsyncMock(return_value=date(2024, 1, 10))
        await job.run_daily(date(2024, 1, 15))
        call = job._provider.get_index_weight.call_args
        assert call.kwargs.get("begin_date") == 20240111

    async def test_index_weight_empty_does_not_advance(self, exchange_job):
        """D-08:API 返空 → 不 set."""
        job, last_sync = exchange_job
        job._provider.get_index_weight = AsyncMock(return_value={})
        await job.run_daily(date(2024, 1, 15))
        last_sync.set_last_sync_date.assert_not_called()


class TestIndustryWeightIncremental:
    """industry_weight 增量回归."""

    async def test_industry_weight_advances_global_null_scope(self, industry_job):
        job, last_sync = industry_job
        await job.run_daily(date(2024, 1, 15))
        last_sync.set_last_sync_date.assert_any_call(
            "industry_weight", None, date(2024, 1, 15)
        )

    async def test_industry_weight_first_sync_20130101(self, industry_job):
        job, last_sync = industry_job
        last_sync.get_last_sync_date = AsyncMock(return_value=None)
        await job.run_daily(date(2024, 1, 15))
        call = job._provider.get_industry_weight.call_args
        assert call.kwargs.get("begin_date") == 20130101

    async def test_industry_weight_incremental_last_plus_one(self, industry_job):
        job, last_sync = industry_job
        last_sync.get_last_sync_date = AsyncMock(return_value=date(2024, 1, 10))
        await job.run_daily(date(2024, 1, 15))
        call = job._provider.get_industry_weight.call_args
        assert call.kwargs.get("begin_date") == 20240111
