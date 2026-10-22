"""Tests for ReferenceDataSyncJob.

测试 reference_data_sync_job 的核心路径：
- 构造函数参数验证
- run() 根据日期触发 stock_basic（每周）、backward_factor（每月）
- stock_basic 同步通过 reference_provider.get_stock_basic_df（非 _client）
- backward_factor 同步通过 reference_provider.get_backward_factor_df（非 _client）
- state_manager 集成（is_synced/mark_running/mark_success/mark_failed）
"""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd

from galaxy_core.application.scheduler.reference_data_sync_job import ReferenceDataSyncJob


class TestReferenceDataSyncJobInit:
    """Tests for ReferenceDataSyncJob initialization."""

    def test_init_with_all_params(self, mock_state_manager):
        """Initializes with state_manager, reference_provider, db_manager, calendar_store."""
        mock_ref_provider = MagicMock()
        mock_db = MagicMock()
        mock_calendar_store = MagicMock()

        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=mock_ref_provider,
            db_manager=mock_db,
            calendar_store=mock_calendar_store,
        )

        assert job._state_manager is mock_state_manager
        assert job._reference_provider is mock_ref_provider
        assert job._db is mock_db
        assert job._calendar_store is mock_calendar_store


class TestRun:
    """Tests for ReferenceDataSyncJob 入口方法(run/run_stock_basic/run_backward_factor)。

    2026-08-04 拆分:原 run() 内 per-type 交错 stock_basic↔backward_factor,现拆为
    run_stock_basic(快)+ run_backward_factor(慢),scheduler chain 把 backward_factor
    移到末尾不阻塞 fundflow。run() 保留向后兼容(顺序调两者)。
    """

    @pytest.mark.asyncio
    async def test_run_stock_basic_triggers_per_type(self, mock_state_manager):
        """run_stock_basic() 遍历 security_types 调 _maybe_sync_stock_basic。"""
        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=MagicMock(),
            db_manager=MagicMock(),
            calendar_store=MagicMock(),
        )
        # 显式设 3 个 type(conftest mock config 默认无 security_types key)
        job._config = {"security_types": ["EXTRA_ETF", "EXTRA_STOCK_A", "EXTRA_INDEX_A"]}
        job._maybe_sync_stock_basic = AsyncMock()
        job._maybe_sync_backward_factor = AsyncMock()

        await job.run_stock_basic(date(2025, 3, 24))

        # 3 个 type,各调一次
        assert job._maybe_sync_stock_basic.call_count == 3
        # backward_factor 不应被触发
        job._maybe_sync_backward_factor.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_backward_factor_triggers_per_type(self, mock_state_manager):
        """run_backward_factor() 遍历 security_types 调 _maybe_sync_backward_factor。"""
        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=MagicMock(),
            db_manager=MagicMock(),
            calendar_store=MagicMock(),
        )
        job._config = {"security_types": ["EXTRA_ETF", "EXTRA_STOCK_A", "EXTRA_INDEX_A"]}
        job._maybe_sync_stock_basic = AsyncMock()
        job._maybe_sync_backward_factor = AsyncMock()

        await job.run_backward_factor(date(2025, 3, 15))

        assert job._maybe_sync_backward_factor.call_count == 3
        job._maybe_sync_stock_basic.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_backward_compat_calls_both(self, mock_state_manager):
        """run() 向后兼容:顺序调 run_stock_basic + run_backward_factor。"""
        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=MagicMock(),
            db_manager=MagicMock(),
            calendar_store=MagicMock(),
        )
        job._config = {"security_types": ["EXTRA_ETF", "EXTRA_STOCK_A", "EXTRA_INDEX_A"]}
        job._maybe_sync_stock_basic = AsyncMock()
        job._maybe_sync_backward_factor = AsyncMock()

        await job.run(date(2025, 3, 15))

        # run() 内部调两者(各 3 type)
        assert job._maybe_sync_stock_basic.call_count == 3
        assert job._maybe_sync_backward_factor.call_count == 3

    @pytest.mark.asyncio
    async def test_run_stock_basic_respects_security_types_order(
        self, mock_state_manager
    ):
        """run_stock_basic 按 config security_types 顺序遍历。"""
        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=MagicMock(),
            db_manager=MagicMock(),
            calendar_store=MagicMock(),
        )
        job._config = {"security_types": ["EXTRA_ETF", "EXTRA_STOCK_A"]}
        job._maybe_sync_stock_basic = AsyncMock()

        await job.run_stock_basic(date(2025, 3, 24))

        called_types = [c.args[1] for c in job._maybe_sync_stock_basic.call_args_list]
        assert called_types == ["EXTRA_ETF", "EXTRA_STOCK_A"]


class TestSyncStockBasic:
    """Tests for _sync_stock_basic method.

    SDK endpoint 分流（AGENTS.md 2026-07-07）：
    - 股票类（EXTRA_STOCK_A 等）走 get_stock_basic_df
    - ETF/INDEX 类走 get_code_info（get_stock_basic 对这些代码返回空）
    """

    @pytest.mark.asyncio
    async def test_stock_routes_to_get_stock_basic_df(self, mock_state_manager):
        """EXTRA_STOCK_A → 走 get_stock_basic_df（股票路径）。"""
        mock_ref_provider = MagicMock()
        mock_ref_provider.get_stock_list = AsyncMock(return_value=["600000.SH", "000001.SZ"])
        mock_ref_provider.get_stock_basic_df = AsyncMock(
            return_value=pd.DataFrame({
                "MARKET_CODE": ["600000.SH", "000001.SZ"],
                "SECURITY_NAME": ["浦发银行", "平安银行"],
                "LISTDATE": ["19991110", "19910403"],
            })
        )
        mock_ref_provider.get_code_info = AsyncMock(return_value=pd.DataFrame())

        mock_db = MagicMock()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_db.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.session.return_value.__aexit__ = AsyncMock(return_value=False)

        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=mock_ref_provider,
            db_manager=mock_db,
            calendar_store=MagicMock(),
        )

        await job._sync_stock_basic(date(2025, 3, 24), "EXTRA_STOCK_A", "2025-W13")

        # 股票路径应调 get_stock_basic_df，不调 get_code_info
        mock_ref_provider.get_stock_basic_df.assert_called_once_with(
            ["600000.SH", "000001.SZ"]
        )
        mock_ref_provider.get_code_info.assert_not_called()

    @pytest.mark.asyncio
    async def test_etf_routes_to_get_code_info(self, mock_state_manager):
        """EXTRA_ETF → 走 get_code_info（get_stock_basic 对 ETF 返回空）。"""
        mock_ref_provider = MagicMock()
        mock_ref_provider.get_stock_list = AsyncMock(
            return_value=["159596.SZ", "159587.SZ"]
        )
        mock_ref_provider.get_code_info = AsyncMock(
            return_value=pd.DataFrame(
                {"symbol": ["A50华宝", "粮食50"], "list_day": ["20240318", "20240821"]},
                index=pd.Index(["159596.SZ", "159587.SZ"], name="code_market"),
            )
        )
        mock_ref_provider.get_stock_basic_df = AsyncMock(return_value=pd.DataFrame())

        mock_db = MagicMock()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_db.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.session.return_value.__aexit__ = AsyncMock(return_value=False)

        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=mock_ref_provider,
            db_manager=mock_db,
            calendar_store=MagicMock(),
        )

        await job._sync_stock_basic(date(2025, 3, 24), "EXTRA_ETF", "2025-W13")

        # ETF 路径应调 get_code_info，不调 get_stock_basic_df
        mock_ref_provider.get_code_info.assert_called_once_with("EXTRA_ETF")
        mock_ref_provider.get_stock_basic_df.assert_not_called()

    @pytest.mark.asyncio
    async def test_index_routes_to_get_code_info(self, mock_state_manager):
        """EXTRA_INDEX_A → 走 get_code_info（get_stock_basic 对指数返回空）。"""
        mock_ref_provider = MagicMock()
        mock_ref_provider.get_stock_list = AsyncMock(return_value=["000300.SH"])
        mock_ref_provider.get_code_info = AsyncMock(
            return_value=pd.DataFrame(
                {"symbol": ["沪深300"], "list_day": ["20020101"]},
                index=pd.Index(["000300.SH"], name="code_market"),
            )
        )
        mock_ref_provider.get_stock_basic_df = AsyncMock(return_value=pd.DataFrame())

        mock_db = MagicMock()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_db.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.session.return_value.__aexit__ = AsyncMock(return_value=False)

        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=mock_ref_provider,
            db_manager=mock_db,
            calendar_store=MagicMock(),
        )

        await job._sync_stock_basic(date(2025, 3, 24), "EXTRA_INDEX_A", "2025-W13")

        mock_ref_provider.get_code_info.assert_called_once_with("EXTRA_INDEX_A")
        mock_ref_provider.get_stock_basic_df.assert_not_called()

    @pytest.mark.asyncio
    async def test_etf_empty_code_info_returns_silently(self, mock_state_manager):
        """ETF 分支 get_code_info 返回空 → 静默 return（不 raise，用户决策）。"""
        mock_ref_provider = MagicMock()
        mock_ref_provider.get_stock_list = AsyncMock(return_value=["159596.SZ"])
        mock_ref_provider.get_code_info = AsyncMock(return_value=pd.DataFrame())
        mock_ref_provider.get_stock_basic_df = AsyncMock(return_value=pd.DataFrame())

        mock_db = MagicMock()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [("159596.SZ",)]  # 表里已存在 → codes 过滤后为空
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_db.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.session.return_value.__aexit__ = AsyncMock(return_value=False)

        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=mock_ref_provider,
            db_manager=mock_db,
            calendar_store=MagicMock(),
        )

        # Should not raise even though get_code_info returns empty
        await job._sync_stock_basic(date(2025, 3, 24), "EXTRA_ETF", "2025-W13")

    @pytest.mark.asyncio
    async def test_stock_empty_basic_df_returns_silently(self, mock_state_manager):
        """股票分支 get_stock_basic_df 返回空 → 静默 return（不 raise）。"""
        mock_ref_provider = MagicMock()
        mock_ref_provider.get_stock_list = AsyncMock(return_value=["600000.SH"])
        mock_ref_provider.get_stock_basic_df = AsyncMock(return_value=pd.DataFrame())
        mock_ref_provider.get_code_info = AsyncMock(return_value=pd.DataFrame())

        mock_db = MagicMock()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_db.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.session.return_value.__aexit__ = AsyncMock(return_value=False)

        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=mock_ref_provider,
            db_manager=mock_db,
            calendar_store=MagicMock(),
        )

        # Should not raise
        await job._sync_stock_basic(date(2025, 3, 24), "EXTRA_STOCK_A", "2025-W13")


class TestSyncBackwardFactor:
    """Tests for _sync_backward_factor method."""

    @pytest.mark.asyncio
    async def test_sync_backward_factor_calls_port_method(self, mock_state_manager):
        """_sync_backward_factor calls reference_provider.get_backward_factor_df (not _client)."""
        mock_ref_provider = MagicMock()
        mock_ref_provider.get_stock_list = AsyncMock(return_value=["600000.SH"])
        mock_ref_provider.get_backward_factor_df = AsyncMock(
            return_value=pd.DataFrame(
                {"600000.SH": [1.0, 0.95]},
                index=pd.to_datetime(["2025-03-20", "2025-03-21"]),
            )
        )

        mock_db = MagicMock()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_db.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.session.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_calendar_store = MagicMock()

        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=mock_ref_provider,
            db_manager=mock_db,
            calendar_store=mock_calendar_store,
        )

        await job._sync_backward_factor(date(2025, 3, 24), "EXTRA_ETF", "2025-03")

        # Verify port method was called with correct args
        mock_ref_provider.get_backward_factor_df.assert_called_once_with(
            ["600000.SH"], job._cache_dir
        )

    @pytest.mark.asyncio
    async def test_sync_backward_factor_handles_empty_result(self, mock_state_manager):
        """_sync_backward_factor handles empty DataFrame gracefully."""
        mock_ref_provider = MagicMock()
        mock_ref_provider.get_stock_list = AsyncMock(return_value=["600000.SH"])
        mock_ref_provider.get_backward_factor_df = AsyncMock(return_value=pd.DataFrame())

        mock_db = MagicMock()
        mock_calendar_store = MagicMock()

        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=mock_ref_provider,
            db_manager=mock_db,
            calendar_store=mock_calendar_store,
        )

        # Should not raise
        await job._sync_backward_factor(date(2025, 3, 24), "EXTRA_ETF", "2025-03")


class TestMaybeSyncStockBasic:
    """Tests for _maybe_sync_stock_basic state management."""

    @pytest.mark.asyncio
    async def test_skips_already_synced(self, mock_state_manager):
        """Skips stock_basic if already synced this week."""
        mock_state_manager.is_synced.return_value = True

        mock_ref_provider = MagicMock()
        mock_db = MagicMock()
        mock_calendar_store = MagicMock()

        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=mock_ref_provider,
            db_manager=mock_db,
            calendar_store=mock_calendar_store,
        )
        job._is_stock_basic_empty = AsyncMock(return_value=False)

        await job._maybe_sync_stock_basic(date(2025, 3, 24), "EXTRA_ETF")

        mock_state_manager.mark_running.assert_not_called()

    @pytest.mark.asyncio
    async def test_marks_running_before_sync(self, mock_state_manager):
        """Marks stock_basic as running before sync."""
        mock_state_manager.is_synced.return_value = False

        mock_ref_provider = MagicMock()
        mock_db = MagicMock()
        mock_calendar_store = MagicMock()

        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=mock_ref_provider,
            db_manager=mock_db,
            calendar_store=mock_calendar_store,
        )
        job._is_stock_basic_empty = AsyncMock(return_value=False)

        with patch(
            "galaxy_core.application.scheduler.reference_data_sync_job.sync_with_retry",
            return_value=True,
        ):
            await job._maybe_sync_stock_basic(date(2025, 3, 24), "EXTRA_ETF")

        mock_state_manager.mark_running.assert_any_call(
            "refdata_stock_basic_EXTRA_ETF", "2025-W13"
        )

    @pytest.mark.asyncio
    async def test_marks_success_after_sync(self, mock_state_manager):
        """Marks stock_basic as success after successful sync."""
        mock_state_manager.is_synced.return_value = False

        mock_ref_provider = MagicMock()
        mock_db = MagicMock()
        mock_calendar_store = MagicMock()

        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=mock_ref_provider,
            db_manager=mock_db,
            calendar_store=mock_calendar_store,
        )
        job._is_stock_basic_empty = AsyncMock(return_value=False)

        with patch(
            "galaxy_core.application.scheduler.reference_data_sync_job.sync_with_retry",
            return_value=True,
        ):
            await job._maybe_sync_stock_basic(date(2025, 3, 24), "EXTRA_ETF")

        mock_state_manager.mark_success.assert_any_call(
            "refdata_stock_basic_EXTRA_ETF", "2025-W13"
        )

    @pytest.mark.asyncio
    async def test_marks_failed_after_retry_exhausted(self, mock_state_manager):
        """Marks stock_basic as failed after all retries exhausted."""
        mock_state_manager.is_synced.return_value = False

        mock_ref_provider = MagicMock()
        mock_db = MagicMock()
        mock_calendar_store = MagicMock()

        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=mock_ref_provider,
            db_manager=mock_db,
            calendar_store=mock_calendar_store,
        )
        job._is_stock_basic_empty = AsyncMock(return_value=False)

        with patch(
            "galaxy_core.application.scheduler.reference_data_sync_job.sync_with_retry",
            return_value=False,
        ):
            await job._maybe_sync_stock_basic(date(2025, 3, 24), "EXTRA_ETF")

        mock_state_manager.mark_failed.assert_called_once_with(
            "refdata_stock_basic_EXTRA_ETF", "2025-W13", "All retries exhausted"
        )


class TestMaybeSyncBackwardFactor:
    """Tests for _maybe_sync_backward_factor state management."""

    @pytest.mark.asyncio
    async def test_skips_already_synced(self, mock_state_manager):
        """Skips backward_factor if already synced this month."""
        mock_state_manager.is_synced.return_value = True

        mock_ref_provider = MagicMock()
        mock_db = MagicMock()
        mock_calendar_store = MagicMock()

        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=mock_ref_provider,
            db_manager=mock_db,
            calendar_store=mock_calendar_store,
        )

        await job._maybe_sync_backward_factor(date(2025, 3, 15), "EXTRA_ETF")

        mock_state_manager.mark_running.assert_not_called()

    @pytest.mark.asyncio
    async def test_marks_running_before_sync(self, mock_state_manager):
        """Marks backward_factor as running before sync."""
        mock_state_manager.is_synced.return_value = False

        mock_ref_provider = MagicMock()
        mock_db = MagicMock()
        mock_calendar_store = MagicMock()

        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=mock_ref_provider,
            db_manager=mock_db,
            calendar_store=mock_calendar_store,
        )

        with patch(
            "galaxy_core.application.scheduler.reference_data_sync_job.sync_with_retry",
            return_value=True,
        ):
            await job._maybe_sync_backward_factor(date(2025, 3, 15), "EXTRA_ETF")

        mock_state_manager.mark_running.assert_called_once_with(
            "refdata_backward_factor_EXTRA_ETF", "2025-03"
        )

    @pytest.mark.asyncio
    async def test_marks_success_after_sync(self, mock_state_manager):
        """Marks backward_factor as success after successful sync."""
        mock_state_manager.is_synced.return_value = False

        mock_ref_provider = MagicMock()
        mock_db = MagicMock()
        mock_calendar_store = MagicMock()

        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=mock_ref_provider,
            db_manager=mock_db,
            calendar_store=mock_calendar_store,
        )

        with patch(
            "galaxy_core.application.scheduler.reference_data_sync_job.sync_with_retry",
            return_value=True,
        ):
            await job._maybe_sync_backward_factor(date(2025, 3, 15), "EXTRA_ETF")

        mock_state_manager.mark_success.assert_called_once_with(
            "refdata_backward_factor_EXTRA_ETF", "2025-03"
        )


class TestBackwardFactorChunking:
    """Tests for backward_factor chunk-based fetching (2026-07-10 fix).

    原整组传 API 爆内存(ETF 1585 只 RSS 7GB)。改 resolve_daily_chunk_size
    分批拉取 + 每 chunk 独立 session 写入。
    """

    @pytest.mark.asyncio
    async def test_multiple_codes_split_into_chunks(self, mock_state_manager):
        """大量 code 被分成多个 chunk,每 chunk 独立调 API。"""
        # 1000 只 code, chunk_size ≈ 353 → 3 chunk
        codes = [f"{i:06d}.SH" for i in range(1000)]
        mock_ref_provider = MagicMock()
        mock_ref_provider.get_stock_list = AsyncMock(return_value=codes)
        # 每 chunk 返回小 DataFrame
        mock_ref_provider.get_backward_factor_df = AsyncMock(
            return_value=pd.DataFrame(
                {"600000.SH": [1.0]}, index=pd.to_datetime(["2025-03-20"])
            )
        )

        mock_db = MagicMock()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_db.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.session.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_calendar_store = MagicMock()

        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=mock_ref_provider,
            db_manager=mock_db,
            calendar_store=mock_calendar_store,
        )
        job._upsert_backward_factor = AsyncMock(return_value=1)

        await job._sync_backward_factor(date(2025, 3, 24), "EXTRA_STOCK_A", "2025-03")

        # 1000 只 / chunk_size 353 → ceil = 3 chunk
        assert mock_ref_provider.get_backward_factor_df.call_count == 3
        # upsert 每 chunk 调一次
        assert job._upsert_backward_factor.call_count == 3

    @pytest.mark.asyncio
    async def test_single_chunk_failure_does_not_block_others(self, mock_state_manager):
        """单 chunk API 失败 log warning,不阻断后续 chunk。"""
        # 用 >chunk_size 只 code 强制分多 chunk(chunk_size≈353)
        codes = [f"{i:06d}.SH" for i in range(400)]
        mock_ref_provider = MagicMock()
        mock_ref_provider.get_stock_list = AsyncMock(return_value=codes)
        # 第 1 次调抛异常,第 2 次正常
        mock_ref_provider.get_backward_factor_df = AsyncMock(
            side_effect=[
                RuntimeError("API timeout"),
                pd.DataFrame(
                    {"000353.SH": [1.0]}, index=pd.to_datetime(["2025-03-20"])
                ),
            ]
        )
        mock_db = MagicMock()
        mock_calendar_store = MagicMock()

        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=mock_ref_provider,
            db_manager=mock_db,
            calendar_store=mock_calendar_store,
        )
        job._upsert_backward_factor = AsyncMock(return_value=1)

        # 不应 raise
        await job._sync_backward_factor(date(2025, 3, 24), "EXTRA_ETF", "2025-03")

        # 第 2 chunk 正常处理
        assert mock_ref_provider.get_backward_factor_df.call_count == 2


class TestSyncTypePerSecurityType:
    """Tests for sync_type 按 security_type 拆分 (2026-07-10 Bug 4 fix).

    原固定 sync_type 导致空表首启时第 1 个 type success 后 week/month_id 标 done,
    第 2/3 个 type 被跳过。改 "refdata_*_{type}" 各 type 独立门控。
    """

    @pytest.mark.asyncio
    async def test_stock_basic_different_types_use_different_sync_types(
        self, mock_state_manager
    ):
        """stock_basic: 不同 security_type 用不同 sync_type,不互相门控。"""
        mock_ref_provider = MagicMock()
        mock_db = MagicMock()
        mock_calendar_store = MagicMock()

        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=mock_ref_provider,
            db_manager=mock_db,
            calendar_store=mock_calendar_store,
        )
        job._is_stock_basic_empty = AsyncMock(return_value=False)

        # is_synced 对 EXTRA_ETF 返 True,对 EXTRA_STOCK_A 返 False
        # (模拟 Bug 4 场景:ETF 已 sync,STOCK_A 未 sync)
        mock_state_manager.is_synced.side_effect = lambda sync_type, period_id: (
            sync_type == "refdata_stock_basic_EXTRA_ETF"
        )

        with patch(
            "galaxy_core.application.scheduler.reference_data_sync_job.sync_with_retry",
            return_value=True,
        ):
            # EXTRA_ETF 已 sync → 跳过
            await job._maybe_sync_stock_basic(date(2025, 3, 24), "EXTRA_ETF")
            mock_state_manager.mark_running.assert_not_called()

            # EXTRA_STOCK_A 未 sync → 执行
            await job._maybe_sync_stock_basic(date(2025, 3, 24), "EXTRA_STOCK_A")
            mock_state_manager.mark_running.assert_called_once_with(
                "refdata_stock_basic_EXTRA_STOCK_A", "2025-W13"
            )

    @pytest.mark.asyncio
    async def test_backward_factor_different_types_use_different_sync_types(
        self, mock_state_manager
    ):
        """backward_factor: 不同 security_type 用不同 sync_type。"""
        mock_ref_provider = MagicMock()
        mock_db = MagicMock()
        mock_calendar_store = MagicMock()

        job = ReferenceDataSyncJob(
            state_manager=mock_state_manager,
            reference_provider=mock_ref_provider,
            db_manager=mock_db,
            calendar_store=mock_calendar_store,
        )

        mock_state_manager.is_synced.side_effect = lambda sync_type, period_id: (
            sync_type == "refdata_backward_factor_EXTRA_ETF"
        )

        with patch(
            "galaxy_core.application.scheduler.reference_data_sync_job.sync_with_retry",
            return_value=True,
        ):
            await job._maybe_sync_backward_factor(date(2025, 3, 15), "EXTRA_ETF")
            mock_state_manager.mark_running.assert_not_called()

            await job._maybe_sync_backward_factor(date(2025, 3, 15), "EXTRA_STOCK_A")
            mock_state_manager.mark_running.assert_called_once_with(
                "refdata_backward_factor_EXTRA_STOCK_A", "2025-03"
            )


class TestNoClientAccess:
    """Tests verifying no direct _client access in reference_data_sync_job."""

    def test_no_client_attribute_access_in_source(self):
        """reference_data_sync_job.py should not access _client on reference_provider."""
        import inspect
        source = inspect.getsource(ReferenceDataSyncJob)
        # _client access should not appear in the source
        assert "._client" not in source, (
            "reference_data_sync_job.py should not access _client directly. "
            "Use port methods (get_stock_basic_df, get_backward_factor_df) instead."
        )
