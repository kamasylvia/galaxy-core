"""FundFlowSyncJob 单元测试.

验证 5 个 sync_type(akshare 1 + amazingdata 4, 2026-06-19 范围修订后)的状态机流程、
单 code 循环、target 分派、force 模式、dict[str, DataFrame] 处理(margin_detail)、
mark_success 清 error_message 回归(AGENTS.md 2026-06-17 bug 3)。

2026-06-26 B2 重构后:编排/执行两层分离。
- 编排层 _maybe_sync_*(门控 + mark_running + sync_with_retry + mark_success/failed)
- 执行层 _sync_*(纯执行,失败 raise → sync_with_retry 重试)

重试回归(2026-06-26 新增):验证间歇性失败重试成功 + 重试耗尽 mark_failed。
"""

from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from galaxy_core.application.scheduler.jobs.fundflow_sync_job import (
    FundFlowSyncJob,
)


@pytest.fixture(autouse=True)
def _patch_retry_sleep(monkeypatch):
    """patch sync_with_retry 内的 asyncio.sleep,避免重试测试等待 60s×3.

    sync_with_retry 重试间隔走 RetryPolicy(默认 max_retries=3/retry_delay=300s),
    测试环境 patch 成 no-op,保留重试次数语义(只省掉等待时间)。
    """
    monkeypatch.setattr(
        "galaxy_core.application.scheduler.retry_handler.asyncio.sleep",
        AsyncMock(),
    )


@pytest.fixture
def akshare_provider():
    p = MagicMock()
    p.get_sector_fund_flow = AsyncMock(return_value=pd.DataFrame())
    return p


@pytest.fixture
def amazing_provider():
    p = MagicMock()
    p.get_long_hu_bang = AsyncMock(return_value=pd.DataFrame())
    p.get_block_trading = AsyncMock(return_value=pd.DataFrame())
    p.get_margin_summary = AsyncMock(return_value=pd.DataFrame())
    p.get_margin_detail = AsyncMock(return_value={})
    return p


@pytest.fixture
def akshare_store():
    s = MagicMock()
    s.save_sector_fund_flow = AsyncMock(return_value=0)
    return s


@pytest.fixture
def amazing_store():
    s = MagicMock()
    s.save_long_hu_bang = AsyncMock(return_value=0)
    s.save_block_trading = AsyncMock(return_value=0)
    s.save_margin_summary = AsyncMock(return_value=0)
    s.save_margin_detail = AsyncMock(return_value=0)
    return s


@pytest.fixture
def reference_provider():
    """reference_provider mock:get_hist_code_list 返 3 个 code(全沪深 A 股口径)."""
    provider = MagicMock()
    provider.get_stock_list = AsyncMock(
        return_value=["600000", "600001", "000001"]
    )
    provider.get_hist_code_list = AsyncMock(
        return_value=["600000.SH", "600001.SH", "000001.SZ"]
    )
    return provider


@pytest.fixture
def last_sync_store():
    """Phase 03 last_sync_store mock(get/set async)."""
    store = MagicMock()
    store.get_last_sync_date = AsyncMock(return_value=None)
    store.get_last_sync_dates_batch = AsyncMock(return_value={})
    store.set_last_sync_date = AsyncMock()
    return store


@pytest.fixture
def calendar_store():
    """交易日历 mock:默认昨日非交易日(margin_detail 空返→成功,保持旧行为).

    熔断用例显式覆盖 get_trading_days 返回 [yesterday] 模拟交易日。
    """
    store = MagicMock()
    store.get_trading_days = AsyncMock(return_value=[])
    return store


@pytest.fixture
def job(
    mock_state_manager,
    akshare_provider,
    amazing_provider,
    akshare_store,
    amazing_store,
    reference_provider,
    last_sync_store,
    calendar_store,
):
    return FundFlowSyncJob(
        state_manager=mock_state_manager,
        akshare_provider=akshare_provider,
        amazing_provider=amazing_provider,
        akshare_store=akshare_store,
        amazing_store=amazing_store,
        last_sync_store=last_sync_store,
        reference_provider=reference_provider,
        calendar_store=calendar_store,
    )


def _sector_df() -> pd.DataFrame:
    return pd.DataFrame({
        "名称": ["银行", "房地产"],
        "主力净流入-净额": [1000000.0, -500000.0],
        "主力净流入-净占比": [5.0, -3.0],
        "超大单类目-净额": [600000.0, -300000.0],
        "大单类目-净额": [400000.0, -200000.0],
        "中单类目-净额": [-200000.0, 100000.0],
        "小单类目-净额": [-800000.0, 400000.0],
    })


def _longhu_df() -> pd.DataFrame:
    """单龙虎榜记录(真实 AmazingData 大写字段)."""
    return pd.DataFrame({
        "MARKET_CODE": ["600000.SH"],
        "TRADE_DATE": ["2024-01-15"],
        "SECURITY_NAME": ["浦发银行"],
        "REASON_TYPE": ["1"],
        "REASON_TYPE_NAME": ["日涨幅偏离值"],
        "CHANGE_RANGE": [1.2],
        "TRADER_NAME": ["某席位"],
        "FLOW_MARK": [1],
        "BUY_AMOUNT": [1000000.0],
        "SELL_AMOUNT": [500000.0],
        "TOTAL_AMOUNT": [1500000.0],
        "TOTAL_VOLUME": [100000.0],
    })


def _block_trading_df() -> pd.DataFrame:
    """单大宗交易记录(真实 AmazingData b_ 前缀字段)."""
    return pd.DataFrame({
        "MARKET_CODE": ["600000.SH"],
        "TRADE_DATE": ["2024-01-15"],
        "B_SHARE_PRICE": [10.5],
        "B_SHARE_VOLUME": [100000.0],
        "B_FREQUENCY": [1],
        "BLOCK_AVG_VOLUME": [100000.0],
        "B_SHARE_AMOUNT": [1050000.0],
        "B_BUYER_NAME": ["买方席位"],
        "B_SELLER_NAME": ["卖方席位"],
    })


def _margin_summary_df() -> pd.DataFrame:
    return pd.DataFrame({
        "TRADE_DATE": ["2024-01-15"],
        "SUM_BORROW_MONEY_BALANCE": [1500000000.0],
        "SUM_PURCH_WITH_BORROW_MONEY": [800000000.0],
        "SUM_SEC_LENDING_BALANCE": [900000000.0],
    })


def _margin_detail_df(market_code: str) -> pd.DataFrame:
    return pd.DataFrame({
        "TRADE_DATE": ["2024-01-15"],
        "MARKET_CODE": [market_code],
        "SECURITY_NAME": ["浦发银行"],
        "BORROW_MONEY_BALANCE": [50000000.0],
        "SEC_LENDING_BALANCE": [30000000.0],
    })


class TestRunDailyDispatch:
    async def test_run_daily_all_triggers_5_sync_types(
        self, job, mock_state_manager
    ):
        """target='all' 触发全部 5 sync_type(margin 含 summary+detail).

        编排层 _maybe_sync_* 仍调 mark_running,断言不变。
        """
        await job.run_daily(date(2024, 1, 15), target="all")
        running = [c[0][0] for c in job._state.mark_running.call_args_list]
        # akshare 1
        assert "akshare_sector_fund_flow" in running
        # amazingdata 4 (margin = summary + detail)
        assert "long_hu_bang" in running
        assert "block_trading" in running
        assert "margin_summary" in running
        assert "margin_detail" in running

    async def test_target_sector_only(self, job, mock_state_manager):
        """target='sector' 只跑 akshare_sector_fund_flow."""
        await job.run_daily(date(2024, 1, 15), target="sector")
        running = [c[0][0] for c in job._state.mark_running.call_args_list]
        assert "akshare_sector_fund_flow" in running
        assert "long_hu_bang" not in running

    async def test_target_margin_runs_summary_and_detail(
        self, job, mock_state_manager
    ):
        """target='margin' 跑 summary + detail(2 个 _sync)."""
        await job.run_daily(date(2024, 1, 15), target="margin")
        running = [c[0][0] for c in job._state.mark_running.call_args_list]
        assert "margin_summary" in running
        assert "margin_detail" in running
        assert "long_hu_bang" not in running


class TestStateMachine:
    async def test_is_synced_short_circuits(
        self, job, mock_state_manager, akshare_provider
    ):
        """is_synced=True → provider 不被调(编排层门控)."""
        mock_state_manager.is_synced = AsyncMock(return_value=True)
        await job.run_daily(date(2024, 1, 15), target="sector")
        akshare_provider.get_sector_fund_flow.assert_not_called()
        mock_state_manager.mark_running.assert_not_called()

    async def test_force_bypasses_is_synced(
        self, job, mock_state_manager, akshare_provider
    ):
        """run_daily_force 即使 is_synced=True 也调 provider(编排层跳过门控)."""
        mock_state_manager.is_synced = AsyncMock(return_value=True)
        akshare_provider.get_sector_fund_flow = AsyncMock(return_value=_sector_df())
        await job.run_daily_force(date(2024, 1, 15), target="sector")
        akshare_provider.get_sector_fund_flow.assert_called()

    async def test_mark_running_then_success_sector(
        self, job, mock_state_manager, akshare_provider, akshare_store
    ):
        """happy path: mark_running → mark_success(B2 编排层调 mark,不带 records_synced)."""
        akshare_provider.get_sector_fund_flow = AsyncMock(
            return_value=_sector_df()
        )
        akshare_store.save_sector_fund_flow = AsyncMock(return_value=2)
        await job.run_daily(date(2024, 1, 15), target="sector")
        job._state.mark_running.assert_any_call(
            "akshare_sector_fund_flow", "20240115"
        )
        success = [
            c for c in job._state.mark_success.call_args_list
            if c[0][0] == "akshare_sector_fund_flow"
        ]
        assert len(success) == 1
        # B2:编排层 mark_success(sync_type, period),records_synced 走默认 0
        assert success[0].args == ("akshare_sector_fund_flow", "20240115")

    async def test_mark_success_clears_error_message(self, job):
        """回归 AGENTS.md 2026-06-17 bug 3:job 不自写 UPDATE error_message=None,
        统一走 state_manager.mark_success 内置."""
        await job.run_daily(date(2024, 1, 15), target="sector")
        src = Path(
            "data/src/galaxy_core/application/scheduler/jobs/fundflow_sync_job.py"
        ).read_text()
        assert "UPDATE sync_state" not in src
        assert "error_message=None" not in src

    async def test_provider_exception_marks_failed_after_retries(
        self, job, mock_state_manager, akshare_provider, monkeypatch
    ):
        """B2 重试回归:provider 持续抛异常 → 重试耗尽 → mark_failed.

        验证 sync_with_retry 重试 3 次后编排层 mark_failed。
        """
        akshare_provider.get_sector_fund_flow = AsyncMock(
            side_effect=RuntimeError("API 异常")
        )
        await job.run_daily(date(2024, 1, 15), target="sector")
        # 重试耗尽后编排层调 mark_failed
        failed = [
            c for c in job._state.mark_failed.call_args_list
            if c[0][0] == "akshare_sector_fund_flow"
        ]
        assert len(failed) == 1
        assert "retries exhausted" in failed[0].args[2].lower()
        # 不应调 mark_success
        success = [
            c for c in job._state.mark_success.call_args_list
            if c[0][0] == "akshare_sector_fund_flow"
        ]
        assert len(success) == 0
        # 初始 1 次 + 重试 3 次 = 4 次 provider 调用
        assert akshare_provider.get_sector_fund_flow.call_count == 4


class TestMarginDetailEmptyGuard:
    """margin_detail 空结果熔断(2026-09-09):昨日交易日且 0 条 → raise 进重试,
    昨日非交易日 → 0 条属正常成功。背景:AM 端 T+1 发布时刻不稳定且数据窗口
    仅当日有效,false-success 会永久错过当日数据(见 .work/HISTORY.md 2026-09-09)。"""

    def _make_job(self, calendar_store, **shared):
        return FundFlowSyncJob(
            state_manager=shared["mock_state_manager"],
            akshare_provider=shared["akshare_provider"],
            amazing_provider=shared["amazing_provider"],
            akshare_store=shared["akshare_store"],
            amazing_store=shared["amazing_store"],
            last_sync_store=shared["last_sync_store"],
            reference_provider=shared["reference_provider"],
            calendar_store=calendar_store,
        )

    async def test_empty_raises_when_yesterday_trading(
        self,
        mock_state_manager,
        akshare_provider,
        amazing_provider,
        akshare_store,
        amazing_store,
        reference_provider,
        last_sync_store,
        calendar_store,
    ):
        """昨日是交易日 + get_margin_detail 返空 → 重试耗尽 mark_failed."""
        calendar_store.get_trading_days = AsyncMock(
            return_value=[date(2024, 1, 14)]
        )
        job = self._make_job(
            calendar_store,
            mock_state_manager=mock_state_manager,
            akshare_provider=akshare_provider,
            amazing_provider=amazing_provider,
            akshare_store=akshare_store,
            amazing_store=amazing_store,
            last_sync_store=last_sync_store,
            reference_provider=reference_provider,
        )
        await job.run_daily(date(2024, 1, 15), target="margin")
        failed = [
            c for c in job._state.mark_failed.call_args_list
            if c[0][0] == "margin_detail"
        ]
        assert len(failed) == 1
        # 重试耗尽(初始 1 + 重试 3)
        assert amazing_provider.get_margin_detail.call_count == 4
        success = [
            c for c in job._state.mark_success.call_args_list
            if c[0][0] == "margin_detail"
        ]
        assert len(success) == 0

    async def test_empty_ok_when_yesterday_not_trading(
        self,
        mock_state_manager,
        akshare_provider,
        amazing_provider,
        akshare_store,
        amazing_store,
        reference_provider,
        last_sync_store,
        calendar_store,
    ):
        """昨日非交易日 + 返空 → 不熔断,mark_success(周末无新数据属正常)."""
        calendar_store.get_trading_days = AsyncMock(return_value=[])
        job = self._make_job(
            calendar_store,
            mock_state_manager=mock_state_manager,
            akshare_provider=akshare_provider,
            amazing_provider=amazing_provider,
            akshare_store=akshare_store,
            amazing_store=amazing_store,
            last_sync_store=last_sync_store,
            reference_provider=reference_provider,
        )
        await job.run_daily(date(2024, 1, 15), target="margin")
        success = [
            c for c in job._state.mark_success.call_args_list
            if c[0][0] == "margin_detail"
        ]
        assert len(success) == 1
        # 无熔断 → 单次调用即成功
        assert amazing_provider.get_margin_detail.call_count == 1


class TestSingleCodeLoop:
    async def test_no_asyncio_gather_serial(self):
        """源码无 asyncio.gather(严格串行)."""
        src = Path(
            "data/src/galaxy_core/application/scheduler/jobs/fundflow_sync_job.py"
        ).read_text()
        assert "asyncio.gather" not in src

    async def test_long_hu_bang_single_code_loop_with_lookback(
        self, job, amazing_provider, amazing_store
    ):
        """long_hu_bang 同窗口批量 + 7 天回补窗口.

        3 个 code 空表首启(last_sync=None)→同窗口合并为 1 次批量调用。
        详见 AGENTS.md 2026-07-04 fundflow 批量优化。
        """
        amazing_provider.get_long_hu_bang = AsyncMock(
            return_value=_longhu_df()
        )
        amazing_store.save_long_hu_bang = AsyncMock(return_value=3)
        await job.run_daily(date(2024, 1, 15), target="longhu")
        # 分段拉取:20130101~20240115 按 3 月分段 → 多次调用(非 1 次)
        assert amazing_provider.get_long_hu_bang.call_count >= 1
        call = amazing_provider.get_long_hu_bang.call_args_list[0]
        # code_list 含全部 3 只 + begin/end 窗口
        assert call.kwargs.get("code_list") is not None
        assert len(call.kwargs["code_list"]) == 3
        assert "begin_date" in call.kwargs
        assert "end_date" in call.kwargs

    async def test_block_trading_single_code_loop(
        self, job, amazing_provider, amazing_store, reference_provider
    ):
        """block_trading 同窗口批量回归(universe 注入后应执行批量调用).

        回归 2026-06-25 bug:DI 漏注 universe provider 导致 per-symbol 三表
        永远 0 条。此测试验证 block_trading 走批量(3 code 同窗口→1 次批量调用)。
        """
        amazing_provider.get_block_trading = AsyncMock(
            return_value=_block_trading_df()
        )
        amazing_store.save_block_trading = AsyncMock(return_value=3)
        await job.run_daily(date(2024, 1, 15), target="block")
        # 同窗口 3 只合并为 1 次批量调用
        assert amazing_provider.get_block_trading.call_count >= 1
        call = amazing_provider.get_block_trading.call_args_list[0]
        assert len(call.kwargs["code_list"]) == 3
        assert "begin_date" in call.kwargs
        assert "end_date" in call.kwargs
        # 验证 universe 确实来自 reference_provider.get_stock_list
        reference_provider.get_hist_code_list.assert_called()


class TestIncrementalWindowJudgment:
    """非空表增量窗口判断测试(2026-07-14 修复)。

    背景: _fetch_per_symbol_batched 原用 get_last_sync_date(sync_type, None) 判空,
    但 per-symbol 表(long_hu_bang 等)的 scope_key 是 code,scope=None 恒返回 None
    → 误判空表首启 → begin=20130101 的 13 年全窗口 → API 处理海量数据挂起。
    修复: 改用 universe[0] 的 per-code 记录判断是否空表。
    """

    async def test_non_empty_table_uses_per_code_windows_not_full_history(
        self, job, amazing_provider, amazing_store, last_sync_store
    ):
        """非空表(per-code 有 last_sync_date)→ 月桶对齐窄窗口,不用 13 年全窗口。

        2026-08-01 更新:窗口改为月桶对齐。last=7/10 → begin 对齐到 8/1(月初),
        而非精确 last+1=7/11。月桶对齐减少分组数(几千 → ~42 月桶),
        多查几天数据无副作用(UPSERT 幂等)。
        """
        from datetime import date as date_cls

        amazing_provider.get_long_hu_bang = AsyncMock(return_value=_longhu_df())
        amazing_store.save_long_hu_bang = AsyncMock(return_value=1)

        # per-code 返回近期日期(如 7/10),simulate 非空表增量场景
        # probe 判空用 get_last_sync_date(universe[0])
        last_sync_store.get_last_sync_date = AsyncMock(
            return_value=date(2026, 7, 10)
        )
        # 批量查用 get_last_sync_dates_batch,返 universe 中 code 的 last=7/10
        # job fixture 的 universe 是 ["600000.SH", "600001.SH", "000001.SZ"]
        last_sync_store.get_last_sync_dates_batch = AsyncMock(
            return_value={
                "600000.SH": date(2026, 7, 10),
                "600001.SH": date(2026, 7, 10),
                "000001.SZ": date(2026, 7, 10),
            }
        )
        await job.run_daily(date(2026, 7, 13), target="longhu")

        # 验证 API 调用的 begin_date 是 20260801(月桶对齐:last 7/10 → 8/1 月初),
        # 不是 20130101(全窗口)也不是 20260711(精确 last+1)
        assert amazing_provider.get_long_hu_bang.call_count >= 1
        call = amazing_provider.get_long_hu_bang.call_args_list[0]
        begin = call.kwargs.get("begin_date")
        assert begin == 20260801, (
            f"非空表应用月桶窗口 begin=20260801, 实际 begin={begin}"
            "(应月桶对齐 last=7/10 → 8/1,非 13 年全窗口也非精确 last+1)"
        )

    async def test_empty_table_uses_full_history_window(
        self, job, amazing_provider, amazing_store, last_sync_store
    ):
        """空表首启(per-code 无记录)→ 默认全窗口(回归保护)。"""
        amazing_provider.get_long_hu_bang = AsyncMock(return_value=_longhu_df())
        amazing_store.save_long_hu_bang = AsyncMock(return_value=1)
        # universe[0] 的 per-code 记录为 None = 真空表首启
        last_sync_store.get_last_sync_date = AsyncMock(return_value=None)
        await job.run_daily(date(2026, 7, 13), target="longhu")

        call = amazing_provider.get_long_hu_bang.call_args_list[0]
        # 空表首启用 DEFAULT_FIRST_SYNC_DATE
        from galaxy_core.shared_kernel.utils.constants import DEFAULT_FIRST_SYNC_DATE

        assert call.kwargs.get("begin_date") == DEFAULT_FIRST_SYNC_DATE


class TestMarginDictBranch:
    async def test_margin_detail_dict_iteration(
        self, job, amazing_provider, amazing_store, reference_provider
    ):
        """margin_detail: get_margin_detail 返 dict[str, DataFrame],
        迭代 items() 每 df 转 VO 累积."""
        amazing_provider.get_margin_detail = AsyncMock(
            return_value={
                "600000": _margin_detail_df("600000"),
                "600001": _margin_detail_df("600001"),
            }
        )
        amazing_store.save_margin_detail = AsyncMock(return_value=6)
        await job.run_daily(date(2024, 1, 15), target="margin")
        # 同窗口 3 只合并为 1 次批量调用(dict 返回)
        assert amazing_provider.get_margin_detail.call_count >= 1
        # B2:编排层 mark_success(margin_detail, period),执行层日志打印 6 条
        success = [
            c for c in job._state.mark_success.call_args_list
            if c[0][0] == "margin_detail"
        ]
        assert len(success) == 1
        assert success[0].args == ("margin_detail", "20240115")

    async def test_margin_detail_empty_dict_skips(
        self, job, amazing_provider, amazing_store, reference_provider
    ):
        """空 dict → 执行层正常返回(空数据),编排层 mark_success."""
        amazing_provider.get_margin_detail = AsyncMock(return_value={})
        await job.run_daily(date(2024, 1, 15), target="margin")
        success = [
            c for c in job._state.mark_success.call_args_list
            if c[0][0] == "margin_detail"
        ]
        assert len(success) == 1

    async def test_margin_summary_no_code_list(
        self, job, amazing_provider, amazing_store
    ):
        """margin_summary 全市场汇总,无 code_list 参数(单次)."""
        amazing_provider.get_margin_summary = AsyncMock(
            return_value=_margin_summary_df()
        )
        amazing_store.save_margin_summary = AsyncMock(return_value=1)
        await job.run_daily(date(2024, 1, 15), target="margin")
        # 只调 1 次(无 code 循环)
        assert amazing_provider.get_margin_summary.call_count == 1
        # 不带 code_list 参数
        call = amazing_provider.get_margin_summary.call_args
        assert "code_list" not in call.kwargs


class TestDfToRecords:
    def test_sector_records_maps_chinese_columns(self):
        """akshare 中文列 → snake_case VO."""
        records = FundFlowSyncJob._df_to_sector_records(
            _sector_df(), "20240115"
        )
        assert len(records) == 2
        rec = records[0]
        assert rec.trade_date == "20240115"
        assert rec.sector_name in ("银行", "房地产")
        assert rec.main_net_amount in (1000000.0, -500000.0)

    def test_margin_summary_records_maps_uppercase_columns(self):
        """amazingdata 大写列 → snake(SUM_BORROW_MONEY_BALANCE→sum_borrow_money_balance)."""
        records = FundFlowSyncJob._df_to_margin_summary_records(
            _margin_summary_df()
        )
        assert len(records) == 1
        rec = records[0]
        # 2026-10-28:trade_date 归一为 YYYYMMDD(store 前缀解析要求)
        assert rec.trade_date == "20240115"
        assert rec.sum_borrow_money_balance == 1500000000.0

    def test_margin_detail_records_maps_with_market_code(self):
        """margin_detail 列映射 + market_code 注入."""
        records = FundFlowSyncJob._df_to_margin_detail_records(
            _margin_detail_df("600000"), "fallback_code"
        )
        assert len(records) == 1
        rec = records[0]
        # market_code 优先取 df 列值
        assert rec.market_code == "600000"
        assert rec.borrow_money_balance == 50000000.0
        assert rec.security_name == "浦发银行"


# =============================================================================
# Phase 03(03-05)增量回归:last_sync_date 推进
# =============================================================================


class TestIncrementalLastSyncDate:
    """Phase 03 增量回归 — last_sync_date 推进语义."""

    async def test_sector_advances_last_sync_date_today(
        self, job, last_sync_store, akshare_provider
    ):
        """akshare sector(当日快照):成功后 set_last_sync_date(today)."""
        akshare_provider.get_sector_fund_flow = AsyncMock(return_value=_sector_df())
        await job.run_daily(date(2024, 1, 15), target="sector")
        last_sync_store.set_last_sync_date.assert_any_call(
            "akshare_sector_fund_flow", None, date(2024, 1, 15)
        )

    async def test_long_hu_bang_advances_per_symbol(
        self, job, last_sync_store, amazing_provider, amazing_store
    ):
        """long_hu_bang per-symbol:按 market_code 分组 set_last_sync_date。

        注:records 按 market_code 分组,3 个 code 循环但 df 都返同一
        market_code(600000.SH)→ 合并为 1 个 scope 的 set call。
        验证 scope_key 是 market_code(非 None)。
        """
        amazing_provider.get_long_hu_bang = AsyncMock(return_value=_longhu_df())
        amazing_store.save_long_hu_bang = AsyncMock(return_value=1)
        await job.run_daily(date(2024, 1, 15), target="longhu")
        # long_hu_bang 的 set 调用,scope_key 是 market_code(600000.SH)
        set_calls = [
            c for c in last_sync_store.set_last_sync_date.call_args_list
            if c.args[0] == "long_hu_bang"
        ]
        assert len(set_calls) >= 1
        assert all(c.args[1] is not None for c in set_calls)  # scope_key 非 None
        # trade_date 是 2024-01-15 → date
        assert set_calls[0].args[2] == date(2024, 1, 15)

    async def test_margin_summary_advances_global_null_scope(
        self, job, last_sync_store, amazing_provider, amazing_store
    ):
        """margin_summary 全局:scope_key=None 单条 set."""
        amazing_provider.get_margin_summary = AsyncMock(
            return_value=_margin_summary_df()
        )
        amazing_store.save_margin_summary = AsyncMock(return_value=1)
        await job.run_daily(date(2024, 1, 15), target="margin")
        # margin_summary 用 scope_key=None
        summary_calls = [
            c for c in last_sync_store.set_last_sync_date.call_args_list
            if c.args[0] == "margin_summary"
        ]
        assert len(summary_calls) == 1
        assert summary_calls[0].args[1] is None  # 全局 None

    async def test_empty_api_does_not_advance(
        self, job, last_sync_store, akshare_provider
    ):
        """D-08:API 返空 → 不调 set_last_sync_date(空响应不推进)."""
        akshare_provider.get_sector_fund_flow = AsyncMock(return_value=pd.DataFrame())
        await job.run_daily(date(2024, 1, 15), target="sector")
        last_sync_store.set_last_sync_date.assert_not_called()

    async def test_first_sync_uses_default_20130101(
        self, job, last_sync_store, amazing_provider
    ):
        """空表首次:last_sync_store.get 返 None → begin=20130101.

        验证 _resolve_incremental_range 在 last=None 时传给 provider 的
        begin_date 是 20130101(DEFAULT_FIRST_SYNC_DATE)。
        """
        last_sync_store.get_last_sync_date = AsyncMock(return_value=None)
        amazing_provider.get_long_hu_bang = AsyncMock(return_value=pd.DataFrame())
        await job.run_daily(date(2024, 1, 15), target="longhu")
        # 每个 code 调用 get_long_hu_bang 时 begin_date 应是 20130101
        # 首段 begin_date 应是 20130101
        first_call = amazing_provider.get_long_hu_bang.call_args_list[0]

    async def test_incremental_uses_month_bucket_window(
        self, job, last_sync_store, amazing_provider
    ):
        """有数据:last=2024-01-10 → begin=20240201(月桶对齐:1月→2月初).

        2026-08-01 更新:窗口改为月桶对齐(原精确 last+1)。
        last 在某月 → begin 对齐到次月 1 号,减少分组数(几千→~42 月桶)。
        """
        last_sync_store.get_last_sync_date = AsyncMock(
            return_value=date(2024, 1, 10)
        )
        # 批量查返 universe 中 code 的 last
        last_sync_store.get_last_sync_dates_batch = AsyncMock(
            return_value={
                "600000.SH": date(2024, 1, 10),
                "600001.SH": date(2024, 1, 10),
                "000001.SZ": date(2024, 1, 10),
            }
        )
        amazing_provider.get_long_hu_bang = AsyncMock(return_value=pd.DataFrame())
        await job.run_daily(date(2024, 1, 15), target="longhu")
        for call in amazing_provider.get_long_hu_bang.call_args_list:
            # 月桶对齐:1月 → 2月初(20240201)
            assert call.kwargs.get("begin_date") == 20240201, (
                f"应月桶对齐 begin=20240201, 实际 {call.kwargs.get('begin_date')}"
            )


# =============================================================================
# B2 重试回归(2026-06-26 新增)
# =============================================================================


class TestRetryBehavior:
    """B2 重试回归 — sync_with_retry 间歇性失败覆盖 + 重试耗尽 mark_failed."""

    async def test_retry_succeeds_on_second_attempt(
        self, job, mock_state_manager, amazing_provider, amazing_store
    ):
        """间歇性失败重试成功:第 1 次抛异常、第 2 次成功 → mark_success.

        模拟 margin_summary 间歇性 API 异常场景(白天正常、凌晨偶发)。
        验证重试后最终 mark_success(不被首次失败永久标记 failed)。
        """
        amazing_provider.get_margin_summary = AsyncMock(
            side_effect=[RuntimeError("间歇性 API 异常"), _margin_summary_df()]
        )
        amazing_store.save_margin_summary = AsyncMock(return_value=1)
        await job.run_daily(date(2024, 1, 15), target="margin")
        # 重试后成功 → mark_success
        success = [
            c for c in mock_state_manager.mark_success.call_args_list
            if c[0][0] == "margin_summary"
        ]
        assert len(success) == 1
        # 不应 mark_failed
        failed = [
            c for c in mock_state_manager.mark_failed.call_args_list
            if c[0][0] == "margin_summary"
        ]
        assert len(failed) == 0
        # provider 调 2 次(初始失败 + 第 1 次重试成功)
        assert amazing_provider.get_margin_summary.call_count == 2

    async def test_retry_exhausted_marks_failed(
        self, job, mock_state_manager, amazing_provider
    ):
        """持续失败 → 重试耗尽 → mark_failed(error_message 含 'retries exhausted')."""
        amazing_provider.get_margin_summary = AsyncMock(
            side_effect=RuntimeError("API 持续异常")
        )
        await job.run_daily(date(2024, 1, 15), target="margin")
        failed = [
            c for c in mock_state_manager.mark_failed.call_args_list
            if c[0][0] == "margin_summary"
        ]
        assert len(failed) == 1
        assert "retries exhausted" in failed[0].args[2].lower()
        # 初始 1 次 + 重试 3 次 = 4 次
        assert amazing_provider.get_margin_summary.call_count == 4

    async def test_single_sync_failure_does_not_block_others(
        self, job, mock_state_manager, amazing_provider, amazing_store
    ):
        """B2 编排层隔离:margin_summary 重试耗尽失败不阻断 margin_detail.

        验证 run_daily 的「单 sync 失败不阻断其余」契约(B2 编排层无异常上抛)。
        """
        # margin_summary 持续失败,margin_detail 正常
        amazing_provider.get_margin_summary = AsyncMock(
            side_effect=RuntimeError("summary 异常")
        )
        amazing_provider.get_margin_detail = AsyncMock(return_value={})
        await job.run_daily(date(2024, 1, 15), target="margin")
        # summary 失败
        summary_failed = [
            c for c in mock_state_manager.mark_failed.call_args_list
            if c[0][0] == "margin_summary"
        ]
        assert len(summary_failed) == 1
        # detail 仍被尝试(隔离生效)
        detail_running = [
            c for c in mock_state_manager.mark_running.call_args_list
            if c[0][0] == "margin_detail"
        ]
        assert len(detail_running) == 1


class TestMarginSummaryFullPullFilter:
    """margin_summary 无参全量 + 客户端窗口过滤(2026-10-28).

    SDK 带 begin/end 参数对空窗口崩溃('NoneType' not subscriptable,
    AM 侧 10/22 起断供期间天天崩 ×4 重试);无参全量拉取正常。
    """

    @staticmethod
    def _full_df() -> pd.DataFrame:
        return pd.DataFrame(
            {
                "TRADE_DATE": [20240120, 20240110, 20240101],
                "SUM_BORROW_MONEY_BALANCE": [3e9, 2e9, 1e9],
            }
        )

    async def test_filters_to_incremental_window(
        self, job, amazing_provider, amazing_store
    ):
        """全量 df 按增量窗 [begin, end] 客户端过滤后入库."""
        job._last_sync_store.get_last_sync_date = AsyncMock(
            return_value=date(2024, 1, 5)
        )  # 窗口 20240106~20240115
        amazing_provider.get_margin_summary = AsyncMock(
            return_value=self._full_df()
        )
        amazing_store.save_margin_summary = AsyncMock(return_value=1)
        await job.run_daily(date(2024, 1, 15), target="margin")
        call = amazing_provider.get_margin_summary.call_args
        # 不再传日期参数(全量拉取)
        assert call.kwargs.get("begin_date") is None
        assert call.kwargs.get("end_date") is None
        saved_arg = amazing_store.save_margin_summary.call_args[0][0]
        assert [r.trade_date for r in saved_arg] == ["20240110"]

    async def test_empty_window_no_save_no_raise(
        self, job, amazing_provider, amazing_store
    ):
        """窗口无数据(上游断供)→ 不入库不 raise,不推进 last_sync."""
        job._last_sync_store.get_last_sync_date = AsyncMock(
            return_value=date(2024, 1, 12)
        )  # 窗口 20240113~20240115
        df = self._full_df()[self._full_df()["TRADE_DATE"] != 20240110]
        amazing_provider.get_margin_summary = AsyncMock(return_value=df)
        amazing_store.save_margin_summary = AsyncMock()
        await job.run_daily(date(2024, 1, 15), target="margin")
        amazing_store.save_margin_summary.assert_not_called()
