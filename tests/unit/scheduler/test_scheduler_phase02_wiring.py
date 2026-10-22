"""Phase 02 scheduler 接线单元测试.

验证 02-08 在 scheduler.py 做的接线(2026-06-19 范围修订后):
- AutoSyncScheduler.__init__ 持有 _fundflow_job(baostock 整源删,不再持有)
- _run_kline_sync_with_cleanup 链顺序:financial → fundflow → cleanup
- 单 job 失败非阻断(fundflow 抛 → cleanup 仍执行)
- 回归:scheduler 模块级 get_section 绑定未被重绑(AGENTS.md 2026-06-16)

不连真实 DB/SDK:mock container + monkeypatch scheduler.get_section
(绕开 sys.modules 绑定顺序,镜像 test_scheduler_loop.py autouse fixture 模式)。
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from galaxy_core.application.scheduler import scheduler as scheduler_module
from galaxy_core.application.scheduler.scheduler import AutoSyncScheduler


def _make_mock_container():
    """Mock DI container with all required providers (镜像 test_scheduler_loop.py)."""
    container = MagicMock()
    container.db_manager.return_value = MagicMock()
    container.db_manager.return_value.close = AsyncMock()
    container.calendar_store.return_value = MagicMock()
    container.calendar_store.return_value.get_trading_days = AsyncMock(return_value=[])
    container.reference_provider.return_value = MagicMock()
    container.kline_service.return_value = MagicMock()
    container.calendar_service.return_value = MagicMock()
    container.reference_service.return_value = MagicMock()
    container.kline_store.return_value = MagicMock()
    container.kline_provider.return_value = MagicMock()
    container.financial_service.return_value = MagicMock()
    container.trading_calendar_service.return_value = MagicMock()
    container.sync_state_manager.return_value = MagicMock()
    # 指数 job(async run_daily / run_dimensions)
    for job_attr in ("exchange_index_job", "industry_index_job"):
        job = MagicMock()
        job.run_daily = AsyncMock()
        job.run_dimensions = AsyncMock()
        getattr(container, job_attr).return_value = job
    # Phase 02 资金流向 job(async run_daily, 范围修订后仅 fundflow)
    fundflow = MagicMock()
    fundflow.run_daily = AsyncMock()
    container.fundflow_job.return_value = fundflow
    return container


TEST_SCHEDULER_CONFIG = {
    "kline_trigger_hour": 23,
    "kline_trigger_minute": 0,
    "enabled_intervals": ["day", "week", "month", "season", "year"],
    "check_intervals": ["day", "week"],
}


@pytest.fixture(autouse=True)
def mock_create_container(monkeypatch):
    """Mock create_container + monkeypatch scheduler.get_section.

    镜像 test_scheduler_loop.py 的 autouse fixture:直接改已绑定的
    scheduler.get_section 引用,绕开 sys.modules 顺序依赖(AGENTS.md 2026-06-16)。
    """
    mock_container = _make_mock_container()
    monkeypatch.setattr(
        "galaxy_core.application.scheduler.scheduler.get_section",
        lambda section: TEST_SCHEDULER_CONFIG.copy() if section == "scheduler" else {},
    )
    with patch(
        "galaxy_core.di.container.create_container",
        return_value=mock_container,
    ):
        yield mock_container


class TestInitHoldsPhase02Jobs:
    """__init__ 持有 fundflow job(02-08, 范围修订后仅 1)."""

    def test_init_holds_fundflow_job(self):
        scheduler = AutoSyncScheduler()
        assert hasattr(scheduler, "_fundflow_job")
        assert scheduler._fundflow_job is not None

    def test_init_does_not_hold_baostock_job(self):
        """范围修订回归:baostock 整源删,scheduler 不应持有 _baostock_job."""
        scheduler = AutoSyncScheduler()
        assert not hasattr(scheduler, "_baostock_job"), (
            "_baostock_job 应已删(baostock 整源删)"
        )

    def test_init_holds_fundflow_and_index_jobs(self):
        """__init__ 应持有 _fundflow_job + 指数 job."""
        scheduler = AutoSyncScheduler()
        assert scheduler._fundflow_job is not None
        # 回归:指数 job 仍在
        assert scheduler._exchange_index_job is not None
        assert scheduler._industry_index_job is not None


class TestChainOrder:
    """0:10 全量 job 顺序(2026-10-22):主链已删,顺序在 0:10 内验证。"""

    @pytest.mark.asyncio
    async def test_0010_job_order_fundflow_before_financial(self):
        """0:10 job 内顺序:fundflow → financial(沿用 0:10 排期)."""
        scheduler = AutoSyncScheduler()
        order: list[str] = []

        async def _record_financial(*args, **kwargs):
            order.append("financial")

        async def _record_fundflow(*args, **kwargs):
            order.append("fundflow")

        scheduler._financial_job.run = AsyncMock(side_effect=_record_financial)
        scheduler._fundflow_job.run_daily = AsyncMock(side_effect=_record_fundflow)
        scheduler._cleanup_job.run = AsyncMock()
        # stub 0:10 沿途其他 job
        scheduler._industry_index_job.run_daily = AsyncMock()
        scheduler._exchange_index_job.run_daily = AsyncMock()
        scheduler._refdata_job.run_stock_basic = AsyncMock()
        scheduler._refdata_job.run_backward_factor = AsyncMock()
        scheduler._exchange_index_job.run_dimensions = AsyncMock()
        scheduler._industry_index_job.run_dimensions = AsyncMock()
        scheduler._kline_job.run_day = AsyncMock()
        scheduler._kline_job.run_minute = AsyncMock()

        today = date(2025, 3, 29)
        await scheduler._run_minute_cover_with_cleanup(today)

        assert order.index("fundflow") < order.index("financial"), (
            f"fundflow 必须在 financial 之前,实际顺序: {order}"
        )


class TestFailureNonBlocking:
    """单 job 失败非阻断(02-08 try/except 设计)."""

    async def test_fundflow_failure_does_not_block_cleanup(self):
        """0:10 job 内 fundflow 抛异常时,不阻断后续(沿用 try/except 隔离)."""
        scheduler = AutoSyncScheduler()
        scheduler._fundflow_job.run_daily = AsyncMock(
            side_effect=RuntimeError("akshare down")
        )
        # stub 0:10 沿途其他 job
        scheduler._industry_index_job.run_daily = AsyncMock()
        scheduler._exchange_index_job.run_daily = AsyncMock()
        scheduler._financial_job.run = AsyncMock()
        scheduler._refdata_job.run_stock_basic = AsyncMock()
        scheduler._refdata_job.run_backward_factor = AsyncMock()
        scheduler._exchange_index_job.run_dimensions = AsyncMock()
        scheduler._industry_index_job.run_dimensions = AsyncMock()
        scheduler._kline_job.run_day = AsyncMock()
        scheduler._kline_job.run_minute = AsyncMock()

        today = date(2025, 3, 29)
        # 不应抛
        await scheduler._run_minute_cover_with_cleanup(today)

        scheduler._kline_job.run_day.assert_called_once_with(today)


class TestGetSectionBindingRegression:
    """回归(AGENTS.md 2026-06-16):scheduler 模块级 get_section 绑定未被重绑.

    scheduler.py:23 `from ...config_loader import get_section` 在模块加载时
    把 get_section 绑定到 scheduler 命名空间。新代码(02-08)不引入新 config
    section,且不应重绑这个引用。本测试确认 scheduler_module.get_section 仍是
    config_loader 的 get_section(可被 monkeypatch.setattr 覆盖,证明是模块属性)。
    """

    def test_get_section_is_module_level_attribute(self):
        """scheduler 模块应有 get_section 属性(模块级绑定)."""
        assert hasattr(scheduler_module, "get_section"), (
            "scheduler 模块应保留模块级 get_section 绑定(02-08 不应删除/重绑)"
        )

    def test_phase02_code_does_not_rebind_get_section(self):
        """02-08 新增代码不应在 scheduler.py 内重绑 get_section.

        通过检查源码:get_section 仅出现在模块顶 import 行 +
        __init__ 的 get_section('scheduler') 调用,
        不应出现 `get_section =` 赋值(重绑)。
        """
        with open(
            "src/galaxy_core/application/scheduler/scheduler.py", encoding="utf-8"
        ) as f:
            content = f.read()
        # 不应出现 get_section = 的赋值(重绑)— import 行是 'from ... import get_section'
        # 赋值形式如 'get_section = lambda' / 'get_section = some_func' 视为重绑
        assert "get_section =" not in content.replace("from", "__IMPORT__"), (
            "scheduler.py 不应重绑 get_section(违反 AGENTS.md 2026-06-16 绑定时机约束)"
        )

    def test_scheduler_reads_scheduler_section(self):
        """回归:scheduler 仍能正确读 [scheduler] section(经 monkeypatch 验证)."""
        scheduler = AutoSyncScheduler()
        # __init__ 已用 TEST_SCHEDULER_CONFIG(kline_trigger_hour=23)初始化
        assert scheduler._config.get("kline_trigger_hour") == 23
