"""行业指数同步任务单元测试.

验证 run_daily（industry_daily + industry_weight）与 run_dimensions
（industry_base_info 月度 + industry_constituent 周度）的状态流程。

2026-07-17:4 方法改编排/执行两层分离(对齐 fundflow),新增重试/codes 空/
chunk 全失败回归测试。
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

pd = pytest.importorskip("pandas")

from galaxy_core.application.scheduler.jobs.industry_index_sync_job import (  # noqa: E402
    IndustryIndexSyncJob,
)


@pytest.fixture(autouse=True)
def _patch_retry_sleep(monkeypatch):
    """patch sync_with_retry 内 asyncio.sleep,避免重试测试等待 5min×3.

    对齐 fundflow test 的 autouse fixture(retry_handler.py 默认 retry_delay=300s)。
    """
    monkeypatch.setattr(
        "galaxy_core.application.scheduler.retry_handler.asyncio.sleep",
        AsyncMock(),
    )


@pytest.fixture
def mock_provider():
    p = MagicMock()
    p.get_industry_base_info = AsyncMock(return_value=None)
    p.get_industry_constituent = AsyncMock(return_value={})
    p.get_industry_weight = AsyncMock(return_value={})
    p.get_industry_daily = AsyncMock(return_value={})
    p.get_industry_index_codes = AsyncMock(return_value=["BK0001"])
    return p


@pytest.fixture
def mock_store():
    s = MagicMock()
    s.save_industry_base_info = AsyncMock(return_value=0)
    s.save_industry_constituent = AsyncMock(return_value=0)
    s.save_industry_weight = AsyncMock(return_value=0)
    s.save_industry_daily = AsyncMock(return_value=0)
    s.get_industry_daily_last_date = AsyncMock(return_value=None)
    # 2026-07-28: _resolve_daily_range 改用全局 max(last_date) 而非 codes[0]
    s.get_industry_daily_max_last_date = AsyncMock(return_value=None)
    s.is_industry_base_info_empty = AsyncMock(return_value=False)
    return s


@pytest.fixture
def calendar_store():
    """交易日历 mock:默认昨日非交易日(industry_daily 低覆盖率→成功,保持旧行为).

    熔断用例显式覆盖 get_trading_days 返回交易日列表。
    """
    store = MagicMock()
    store.get_trading_days = AsyncMock(return_value=[])
    return store


@pytest.fixture
def job(mock_state_manager, mock_provider, mock_store, calendar_store, monkeypatch):
    fake_config = {
        "index": {},
        "amazing_data": {"local_path": "./data/local_cache/"},
    }
    monkeypatch.setattr(
        "galaxy_core.application.scheduler.jobs.industry_index_sync_job.get_section",
        lambda key: fake_config.get(key, {}),
    )
    # Phase 03:last_sync_store 需 AsyncMock(get/set 都是 async)
    last_sync_store = MagicMock()
    last_sync_store.get_last_sync_date = AsyncMock(return_value=None)
    last_sync_store.set_last_sync_date = AsyncMock()
    return IndustryIndexSyncJob(
        state_manager=mock_state_manager,
        provider=mock_provider,
        store=mock_store,
        last_sync_store=last_sync_store,
        calendar_store=calendar_store,
    )


class TestRunDaily:
    async def test_runs_both_daily_and_weight(self, job, mock_state_manager):
        await job.run_daily(date(2024, 1, 15))
        # 两个 sync_type 都应标记成功
        success_calls = mock_state_manager.mark_success.call_args_list
        sync_types = [c[0][0] for c in success_calls]
        assert "industry_daily" in sync_types
        assert "industry_weight" in sync_types

    async def test_daily_codes_empty_marks_failed_after_retries(
        self, job, mock_provider, mock_state_manager
    ):
        """codes 空 → 执行层 raise → 重试耗尽 → mark_failed(不再 mark_success(0)).

        回归 2026-07-17 修复:旧版静默 mark_success(0) 导致 industry_daily
        连续多日 0 条无人告警。
        """
        mock_provider.get_industry_index_codes = AsyncMock(return_value=[])
        await job.run_daily(date(2024, 1, 15))
        # industry_daily 应 mark_failed(不再 mark_success)
        failed = [
            c for c in mock_state_manager.mark_failed.call_args_list
            if c[0][0] == "industry_daily"
        ]
        assert len(failed) == 1
        daily_success = [
            c for c in mock_state_manager.mark_success.call_args_list
            if c[0][0] == "industry_daily"
        ]
        assert len(daily_success) == 0
        # 初始 1 次 + 重试 3 次 = 4 次 provider 调用
        assert mock_provider.get_industry_index_codes.call_count >= 4

    async def test_daily_incremental_range(self, job, mock_provider, mock_store):
        # 最后同步日 20240110 → 首段 begin 应为 20240111;末段 end=20240115;
        # 段间无缝衔接(2026-08-27 SDK 安全限幅:窗口切段)
        mock_store.get_industry_daily_max_last_date = AsyncMock(return_value="20240110")
        calls = []

        async def fake_daily(codes, cache, **kw):
            calls.append(dict(kw))
            return {}

        mock_provider.get_industry_daily = fake_daily
        await job.run_daily(date(2024, 1, 15))
        assert calls[0]["begin_date"] == 20240111
        assert calls[-1]["end_date"] == 20240115
        for prev, nxt in zip(calls, calls[1:]):
            assert nxt["begin_date"] > prev["end_date"] or nxt["end_date"] <= prev["end_date"]


class TestRunDailyForce:
    """Phase 01：run_daily_force 两个 sync_type 都强制重跑."""

    async def test_both_sync_types_rerun_even_if_synced(
        self, job, mock_provider, mock_store, mock_state_manager
    ):
        """is_synced=True 也重跑 industry_daily + industry_weight."""
        mock_state_manager.is_synced = AsyncMock(return_value=True)
        mock_provider.get_industry_daily = AsyncMock(return_value={})
        mock_provider.get_industry_weight = AsyncMock(return_value={})
        await job.run_daily_force(date(2024, 1, 15))
        # 关键:mark_running 被调 2 次(daily + weight),说明都没短路
        running_calls = [c[0][0] for c in mock_state_manager.mark_running.call_args_list]
        assert running_calls.count("industry_daily") == 1
        assert running_calls.count("industry_weight") == 1

    async def test_force_marks_success_for_both(self, job, mock_state_manager):
        await job.run_daily_force(date(2024, 1, 15))
        success_types = [c[0][0] for c in mock_state_manager.mark_success.call_args_list]
        assert "industry_daily" in success_types
        assert "industry_weight" in success_types


class TestRunDimensions:
    async def test_base_info_monthly_period_id(self, job, mock_store, mock_state_manager):
        mock_store.is_industry_base_info_empty = AsyncMock(return_value=False)
        mock_state_manager.is_synced = AsyncMock(return_value=False)
        await job.run_dimensions(date(2024, 3, 15))
        running_calls = [c[0] for c in mock_state_manager.mark_running.call_args_list]
        # base_info 用月度 period_id
        assert ("industry_base_info", "2024-03") in running_calls

    async def test_constituent_weekly_period_id(self, job, mock_store, mock_state_manager):
        mock_state_manager.is_synced = AsyncMock(return_value=False)
        await job.run_dimensions(date(2024, 1, 15))
        running_calls = [c[0] for c in mock_state_manager.mark_running.call_args_list]
        # constituent 用周度 period_id（2024-01-15 = W03）
        assert ("industry_constituent", "2024-W03") in running_calls

    async def test_base_info_force_when_empty(self, job, mock_store, mock_state_manager):
        mock_store.is_industry_base_info_empty = AsyncMock(return_value=True)
        mock_state_manager.is_synced = AsyncMock(return_value=True)
        await job.run_dimensions(date(2024, 1, 15))
        # 空表强制同步，即使 is_synced=True 也执行
        mock_state_manager.mark_running.assert_called()


class TestRunDimensionsForce:
    """Phase 01：run_dimensions_force 两个 sync_type 都强制，base_info 保留空表分支."""

    async def test_both_sync_types_rerun_when_synced(
        self, job, mock_store, mock_state_manager
    ):
        """is_synced=True 也重跑 base_info + constituent."""
        mock_store.is_industry_base_info_empty = AsyncMock(return_value=False)
        mock_state_manager.is_synced = AsyncMock(return_value=True)
        mock_provider_codes = job._provider.get_industry_index_codes
        mock_provider_codes.return_value = ["BK0001"]
        await job.run_dimensions_force(date(2024, 1, 15))
        running_types = [c[0][0] for c in mock_state_manager.mark_running.call_args_list]
        assert running_types.count("industry_base_info") == 1
        assert running_types.count("industry_constituent") == 1

    async def test_force_base_info_still_runs_when_empty(
        self, job, mock_store, mock_state_manager
    ):
        """表空 → force 路径仍执行 base_info（不跳过空表初始化）."""
        mock_store.is_industry_base_info_empty = AsyncMock(return_value=True)
        mock_state_manager.is_synced = AsyncMock(return_value=True)
        await job.run_dimensions_force(date(2024, 1, 15))
        base_info_running = [
            c for c in mock_state_manager.mark_running.call_args_list
            if c[0][0] == "industry_base_info"
        ]
        assert len(base_info_running) == 1


class TestRetryBehavior:
    """2026-07-17 编排/执行两层分离的重试行为回归."""

    async def test_provider_exception_marks_failed_after_retries(
        self, job, mock_provider, mock_state_manager
    ):
        """provider 持续抛异常 → 重试耗尽 → mark_failed(不再静默 mark_success)."""
        mock_provider.get_industry_index_codes = AsyncMock(
            side_effect=RuntimeError("API 异常")
        )
        await job.run_daily(date(2024, 1, 15))
        failed = [
            c for c in mock_state_manager.mark_failed.call_args_list
            if c[0][0] == "industry_daily"
        ]
        assert len(failed) == 1
        assert "retries exhausted" in failed[0].args[2].lower()

    async def test_retry_succeeds_on_second_attempt(
        self, job, mock_provider, mock_state_manager
    ):
        """间歇性失败:首次抛异常,重试成功 → mark_success."""
        call_count = {"n": 0}

        async def flaky(codes, cache, **kw):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("瞬时故障")
            return {}

        # get_industry_index_codes 返 1 code(避免 codes 空分支)
        mock_provider.get_industry_index_codes = AsyncMock(return_value=["BK0001"])
        mock_provider.get_industry_daily = flaky
        await job.run_daily(date(2024, 1, 15))
        success = [
            c for c in mock_state_manager.mark_success.call_args_list
            if c[0][0] == "industry_daily"
        ]
        assert len(success) == 1

    async def test_all_chunks_fail_marks_failed(
        self, job, mock_provider, mock_state_manager, monkeypatch
    ):
        """所有 chunk 失败 → 执行层 raise → 重试耗尽 mark_failed.

        回归:旧版 chunk 全失败仍 mark_success(0) 静默 false-success。
        """
        # 强制 chunk_size=1,使单 code 也走 chunk 循环
        monkeypatch.setattr(
            "galaxy_core.application.scheduler.jobs.industry_index_sync_job."
            "resolve_daily_chunk_size",
            lambda start, end: 1,
        )
        mock_provider.get_industry_index_codes = AsyncMock(return_value=["BK0001", "BK0002"])
        mock_provider.get_industry_daily = AsyncMock(
            side_effect=RuntimeError("chunk API 故障")
        )
        await job.run_daily(date(2024, 1, 15))
        failed = [
            c for c in mock_state_manager.mark_failed.call_args_list
            if c[0][0] == "industry_daily"
        ]
        assert len(failed) == 1

    async def test_partial_chunk_failure_still_success(
        self, job, mock_provider, mock_state_manager, monkeypatch
    ):
        """部分 chunk 失败(但非全部) → 不 raise → mark_success(容错)."""
        monkeypatch.setattr(
            "galaxy_core.application.scheduler.jobs.industry_index_sync_job."
            "resolve_daily_chunk_size",
            lambda start, end: 1,
        )
        mock_provider.get_industry_index_codes = AsyncMock(return_value=["BK0001", "BK0002"])
        call_count = {"n": 0}

        async def partial_fail(codes, cache, **kw):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("单 chunk 故障")
            return {}

        mock_provider.get_industry_daily = partial_fail
        await job.run_daily(date(2024, 1, 15))
        success = [
            c for c in mock_state_manager.mark_success.call_args_list
            if c[0][0] == "industry_daily"
        ]
        assert len(success) == 1

    async def test_zero_saved_emits_warning(
        self, job, mock_provider, mock_state_manager, monkeypatch, caplog
    ):
        """0 条入库时应 emit warning(避免静默 false-success,AGENTS.md 2026-07-28)。

        scheduler 凌晨 AM 时段 SDK 返空时,saved=0 + mark_success 会连续多日无人告警。
        加 warning 让运维能看出跑了但没数据。
        """
        import logging

        monkeypatch.setattr(
            "galaxy_core.application.scheduler.jobs.industry_index_sync_job."
            "resolve_daily_chunk_size",
            lambda start, end: 100,
        )
        mock_provider.get_industry_index_codes = AsyncMock(
            return_value=["BK0001", "BK0002"]
        )
        # SDK 返空 df(模拟 AM 时段性返空)
        mock_provider.get_industry_daily = AsyncMock(return_value={})

        with caplog.at_level(
            logging.WARNING,
            logger="galaxy_core.application.scheduler.jobs.industry_index_sync_job",
        ):
            await job.run_daily(date(2024, 1, 15))

        # 应有 warning 含「0 条」+ 窗口信息
        assert any(
            "0 条" in rec.message and "window=" in rec.message
            for rec in caplog.records
        ), f"未找到 0 条 warning,实际: {[r.message for r in caplog.records]}"


class TestSdkSafeBatching:
    """2026-08-27:industry_daily SDK 批量安全限幅(探针矩阵回归).

    AM SDK get_industry_daily 对 >20 codes 或 >25 自然日窗口静默挂死;
    修复 = 双维限幅(chunk cap + 窗口切段)。本类验证纯函数与调用参数。
    """

    def test_split_window_single_short_window(self):
        from galaxy_core.application.scheduler.jobs.industry_index_sync_job import (
            _split_window,
        )

        assert _split_window(20260821, 20260827) == [(20260821, 20260827)]

    def test_split_window_long_range_segments(self):
        from galaxy_core.application.scheduler.jobs.industry_index_sync_job import (
            INDUSTRY_DAILY_WINDOW_DAYS,
            _split_window,
        )

        segs = _split_window(20260710, 20260827)
        assert len(segs) >= 2
        # 首段起点、末段终点不变;段间无缝(seg[i+1].begin == seg[i].end + 1 天)
        assert segs[0][0] == 20260710
        assert segs[-1][1] == 20260827
        from datetime import date as d

        for (b0, e0), (b1, _) in zip(segs, segs[1:]):
            db = d(b0 // 10000, b0 // 100 % 100, b0 % 100)
            de = d(e0 // 10000, e0 // 100 % 100, e0 % 100)
            assert (db - de).days <= INDUSTRY_DAILY_WINDOW_DAYS

    async def test_sync_uses_capped_chunk_and_segmented_window(self):
        """执行层每次 provider 调用的 codes ≤ cap 且窗口 ≤ 安全天数."""
        import inspect

        src = inspect.getsource(
            IndustryIndexSyncJob._sync_industry_daily
        )
        assert "INDUSTRY_DAILY_CODE_CAP" in src
        assert "_split_window(" in src


class TestIndustryDailyCoverageGuard:
    """industry_daily 空结果/低覆盖率熔断(2026-09-11,margin_detail 同款).

    AM 端 T+1 发布不稳且涓流(9/9 实证 0→38→94/414 跨小时),0 条或显著
    低于预期标成功 = false-success 阻断当日补救;昨日非交易日豁免。
    """

    def _make_job(self, calendar_store, **shared):
        return IndustryIndexSyncJob(
            state_manager=shared["mock_state_manager"],
            provider=shared["mock_provider"],
            store=shared["mock_store"],
            last_sync_store=shared["last_sync_store"],
            calendar_store=calendar_store,
        )

    def _patch_config(self, monkeypatch):
        fake_config = {
            "index": {},
            "amazing_data": {"local_path": "./data/local_cache/"},
        }
        monkeypatch.setattr(
            "galaxy_core.application.scheduler.jobs.industry_index_sync_job.get_section",
            lambda key: fake_config.get(key, {}),
        )

    async def test_zero_rows_raises_when_yesterday_trading(
        self, mock_state_manager, mock_provider, mock_store, monkeypatch
    ):
        calendar_store = MagicMock()
        calendar_store.get_trading_days = AsyncMock(
            return_value=[date(2024, 1, 14)]
        )
        self._patch_config(monkeypatch)
        last_sync_store = MagicMock()
        last_sync_store.get_last_sync_date = AsyncMock(return_value=None)
        last_sync_store.set_last_sync_date = AsyncMock()
        job = self._make_job(
            calendar_store,
            mock_state_manager=mock_state_manager,
            mock_provider=mock_provider,
            mock_store=mock_store,
            last_sync_store=last_sync_store,
        )
        await job.run_daily(date(2024, 1, 15))
        failed = [
            c for c in mock_state_manager.mark_failed.call_args_list
            if c[0][0] == "industry_daily"
        ]
        assert len(failed) == 1
        success = [
            c for c in mock_state_manager.mark_success.call_args_list
            if c[0][0] == "industry_daily"
        ]
        assert len(success) == 0

    async def test_zero_rows_ok_when_yesterday_not_trading(
        self, mock_state_manager, mock_provider, mock_store, monkeypatch
    ):
        calendar_store = MagicMock()
        calendar_store.get_trading_days = AsyncMock(return_value=[])
        self._patch_config(monkeypatch)
        last_sync_store = MagicMock()
        last_sync_store.get_last_sync_date = AsyncMock(return_value=None)
        last_sync_store.set_last_sync_date = AsyncMock()
        job = self._make_job(
            calendar_store,
            mock_state_manager=mock_state_manager,
            mock_provider=mock_provider,
            mock_store=mock_store,
            last_sync_store=last_sync_store,
        )
        await job.run_daily(date(2024, 1, 15))
        success = [
            c for c in mock_state_manager.mark_success.call_args_list
            if c[0][0] == "industry_daily"
        ]
        assert len(success) == 1

    async def test_partial_below_threshold_raises(
        self, mock_state_manager, mock_provider, mock_store, monkeypatch
    ):
        """涓流形态:预期 10 只 × 1 交易日,仅回 1 行 → 熔断 mark_failed."""
        calendar_store = MagicMock()
        calendar_store.get_trading_days = AsyncMock(
            return_value=[date(2024, 1, 14)]
        )
        self._patch_config(monkeypatch)
        last_sync_store = MagicMock()
        last_sync_store.get_last_sync_date = AsyncMock(return_value=None)
        last_sync_store.set_last_sync_date = AsyncMock()
        mock_store.save_industry_daily = AsyncMock(return_value=1)
        mock_provider.get_industry_index_codes = AsyncMock(
            return_value=[f"BK{i:04d}" for i in range(10)]
        )
        job = self._make_job(
            calendar_store,
            mock_state_manager=mock_state_manager,
            mock_provider=mock_provider,
            mock_store=mock_store,
            last_sync_store=last_sync_store,
        )
        await job.run_daily(date(2024, 1, 15))
        failed = [
            c for c in mock_state_manager.mark_failed.call_args_list
            if c[0][0] == "industry_daily"
        ]
        assert len(failed) == 1

    async def test_partial_above_threshold_passes(
        self, mock_state_manager, mock_provider, mock_store, monkeypatch
    ):
        """接近预期(9/10)→ 不熔断,mark_success."""
        calendar_store = MagicMock()
        calendar_store.get_trading_days = AsyncMock(
            return_value=[date(2024, 1, 14)]
        )
        self._patch_config(monkeypatch)
        last_sync_store = MagicMock()
        last_sync_store.get_last_sync_date = AsyncMock(return_value=None)
        last_sync_store.set_last_sync_date = AsyncMock()
        mock_store.save_industry_daily = AsyncMock(return_value=9)
        mock_provider.get_industry_index_codes = AsyncMock(
            return_value=[f"BK{i:04d}" for i in range(10)]
        )
        job = self._make_job(
            calendar_store,
            mock_state_manager=mock_state_manager,
            mock_provider=mock_provider,
            mock_store=mock_store,
            last_sync_store=last_sync_store,
        )
        await job.run_daily(date(2024, 1, 15))
        success = [
            c for c in mock_state_manager.mark_success.call_args_list
            if c[0][0] == "industry_daily"
        ]
        assert len(success) == 1


class TestDfFormatRobustness:
    """SDK 返回格式漂移回归(2026-09-17 断供一个月的根因).

    新格式:TRADE_DATE 为索引名(datetime)+ INDEX_CODE/TOTAL_CAP 为普通列
    → 旧守卫 `reset if "INDEX_CODE" not in columns` 跳过 reset,
    row.get("TRADE_DATE") 恒 None → 100% 行静默丢弃。
    """

    def _new_format_df(self) -> pd.DataFrame:
        idx = pd.DatetimeIndex(
            [pd.Timestamp("2026-10-27"), pd.Timestamp("2026-10-26")],
            name="TRADE_DATE",
        )
        return pd.DataFrame(
            {
                "OPEN": [2467.69, 2483.87],
                "CLOSE": [2443.14, 2476.01],
                "PRE_CLOSE": [2476.01, 2491.17],
                "TOTAL_CAP": [55553272.0, 56300681.0],
                "INDEX_CODE": ["801010.SI", "801010.SI"],
            },
            index=idx,
        )

    def test_new_format_daily_records_not_dropped(self):
        """新格式(TRADE_DATE 索引 + INDEX_CODE 列)不再 100% 丢行."""
        records = IndustryIndexSyncJob._df_to_daily_records(
            self._new_format_df()
        )
        assert len(records) == 2
        rec = records[0]
        assert rec.index_code == "801010.SI"
        assert rec.trade_date == "20261027"
        assert rec.total_cap == 55553272.0

    def test_new_format_index_code_fallback(self):
        """INDEX_CODE 列缺失时回退 dict key."""
        df = self._new_format_df().drop(columns=["INDEX_CODE"])
        records = IndustryIndexSyncJob._df_to_daily_records(df, "801010.SI")
        assert len(records) == 2
        assert records[0].index_code == "801010.SI"

    def test_old_format_still_works(self):
        """旧格式(纯 OHLC 列 + 日期索引,无 INDEX_CODE)reset 路径不回归."""
        idx = pd.DatetimeIndex([pd.Timestamp("2024-01-15")], name="TRADE_DATE")
        df = pd.DataFrame({"OPEN": [1.0], "CLOSE": [2.0]}, index=idx)
        records = IndustryIndexSyncJob._df_to_daily_records(df, "BK0001")
        assert len(records) == 1
        assert records[0].trade_date == "20240115"
        assert records[0].index_code == "BK0001"

    def test_normalize_trade_date_string_datetime(self):
        """字符串 datetime("2026-10-27 00:00:00")归一为 YYYYMMDD."""
        assert (
            IndustryIndexSyncJob._normalize_trade_date("2026-10-27 00:00:00")
            == "20261027"
        )
        assert (
            IndustryIndexSyncJob._normalize_trade_date("20261027") == "20261027"
        )
        assert IndustryIndexSyncJob._normalize_trade_date(None) is None

    def test_weight_records_new_format(self):
        """weight 同款守卫修复:TRADE_DATE 索引格式不再丢行."""
        idx = pd.DatetimeIndex([pd.Timestamp("2024-01-15")], name="TRADE_DATE")
        df = pd.DataFrame(
            {"CON_CODE": ["600000.SH"], "WEIGHT": [3.5]}, index=idx
        )
        records = IndustryIndexSyncJob._df_to_weight_records(df, "BK0001")
        assert len(records) == 1
        assert records[0].trade_date == "20240115"
        assert records[0].index_code == "BK0001"
