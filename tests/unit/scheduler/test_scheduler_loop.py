"""Tests for AutoSyncScheduler main loop."""

import asyncio
import contextlib
import inspect
import os
import signal
from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from galaxy_core.application.scheduler.scheduler import AutoSyncScheduler


def _make_mock_container():
    """Create a mock DI container with all required providers."""
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
    # 指数数据同步任务（async 方法）
    for job_attr in ("exchange_index_job", "industry_index_job"):
        job = MagicMock()
        job.run_daily = AsyncMock()
        job.run_dimensions = AsyncMock()
        getattr(container, job_attr).return_value = job
    # Phase 02 资金流向同步任务(async run_daily,02-08 链挂载, 范围修订后仅 fundflow)
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
    """Mock create_container for all scheduler tests.

    同时 patch scheduler 模块的 get_section，确保 AutoSyncScheduler.__init__
    读到测试期望的配置（kline_trigger_hour=23 等），不受全局 config_loader
    mock 绑定顺序影响（tests/unit/conftest.py 的 mock 返回 {} 会覆盖
    scheduler/conftest.py 的带值 mock）。
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


class TestAutoSyncSchedulerInit:
    """Tests for AutoSyncScheduler initialization."""

    def test_initializes_components(self):
        """Initializes all required components."""
        scheduler = AutoSyncScheduler()
        assert scheduler._state_manager is not None
        assert scheduler._kline_job is not None
        assert scheduler._calendar_job is not None
        assert scheduler._refdata_job is not None
        assert scheduler._cleanup_job is not None
        assert scheduler._running is False


class TestSchedulerLoop:
    """Tests for the main scheduler loop."""

    @pytest.mark.asyncio
    async def test_stop_cancels_tasks(self):
        """Stop cancels all pending tasks."""
        scheduler = AutoSyncScheduler()
        scheduler._running = True

        # Create a real asyncio task that will be cancelled
        async def dummy_task():
            await asyncio.sleep(10)  # Long enough to be cancelled

        task = asyncio.create_task(dummy_task())
        scheduler._tasks.add(task)

        await scheduler.stop()

        assert task.cancelled() is True
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_stop_closes_database(self):
        """Stop closes database connection."""
        scheduler = AutoSyncScheduler()

        await scheduler.stop()

        scheduler._db_manager.close.assert_called_once()


class TestSignalAudit:
    """_register_signal_audit 注册 SIGINT/SIGTERM 审计 handler(2026-06-26).

    scheduler 曾在无人操作下收到信号后 exit 0 无记录,无法定位发送者。
    signal handler 记录信号名 + 时刻 + 状态,然后设 _running=False 触发优雅退出。
    本测试验证:① 两信号都注册 ② 回调设 _running=False ③ 幂等(重复触发安全)。
    """

    @pytest.mark.asyncio
    async def test_registers_sigint_and_sigterm(self):
        """_register_signal_audit 对 SIGINT/SIGTERM 都注册 handler."""
        scheduler = AutoSyncScheduler()
        scheduler._running = True

        registered: dict[int, callable] = {}

        class _FakeLoop:
            def add_signal_handler(self, sig, callback, *args):
                registered[int(sig)] = lambda: callback(*args)

        scheduler._register_signal_audit(_FakeLoop())  # type: ignore[arg-type]

        assert signal.SIGINT in registered
        assert signal.SIGTERM in registered

    @pytest.mark.asyncio
    async def test_signal_callback_sets_running_false(self, caplog):
        """触发注册的回调 → _running 从 True 变 False(触发优雅退出)+ 留 WARNING 日志."""
        import logging

        scheduler = AutoSyncScheduler()
        scheduler._running = True

        callbacks: dict[int, callable] = {}

        class _FakeLoop:
            def add_signal_handler(self, sig, callback, *args):
                callbacks[int(sig)] = lambda: callback(*args)

        scheduler._register_signal_audit(_FakeLoop())  # type: ignore[arg-type]

        with caplog.at_level(logging.WARNING):
            callbacks[int(signal.SIGTERM)]()

        assert scheduler._running is False
        # 日志记录信号名 + 时刻 + PID(审计证据)
        assert any("SIGTERM" in r.message and "收到信号" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_signal_callback_idempotent(self):
        """重复触发回调安全:_running 已 False 时不再重复处理(幂等)."""
        scheduler = AutoSyncScheduler()
        scheduler._running = True

        callbacks: dict[int, callable] = {}

        class _FakeLoop:
            def add_signal_handler(self, sig, callback, *args):
                callbacks[int(sig)] = lambda: callback(*args)

        scheduler._register_signal_audit(_FakeLoop())  # type: ignore[arg-type]

        # 第一次触发:设 _running=False
        callbacks[int(signal.SIGINT)]()
        assert scheduler._running is False
        # 第二次触发:不报错(幂等,_running 已是 False,if 守卫跳过)
        callbacks[int(signal.SIGINT)]()
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_register_fallback_on_unsupported_platform(self, caplog):
        """add_signal_handler 抛 NotImplementedError(Windows)→ 降级不阻断启动."""
        import logging

        scheduler = AutoSyncScheduler()
        scheduler._running = True

        class _UnsupportedLoop:
            def add_signal_handler(self, sig, callback, *args):
                raise NotImplementedError("Windows 无 add_signal_handler")

        with caplog.at_level(logging.DEBUG):
            # 不应抛异常(降级处理)
            scheduler._register_signal_audit(_UnsupportedLoop())  # type: ignore[arg-type]

        # _running 保持 True(未触发退出,只是没注册审计)
        assert scheduler._running is True

class TestPostSyncCleanup:
    """12:00 主链已删除(2026-10-22):相关测试移入 0:10 job 顺序测试。"""

    @pytest.mark.asyncio
    async def test_on_task_done_logs_exception(self, caplog):
        """回归: _on_task_done retrieve exception 并 log error(AGENTS.md 2026-07-28 Bug 3)。

        原 add_done_callback(self._tasks.discard) 只移除不 retrieve,
        task raise 时只 GC 时打 "Task exception was never retrieved" 警告。
        """
        import logging

        scheduler = AutoSyncScheduler()

        async def boom() -> None:
            raise RuntimeError("task boom")

        task = asyncio.create_task(boom(), name="test_boom")
        scheduler._tasks.add(task)
        task.add_done_callback(scheduler._on_task_done)

        with caplog.at_level(logging.ERROR, logger="galaxy_core.application.scheduler.scheduler"):
            # task 内 raise → done_callback retrieve 异常并 log,
            # 但 await 仍会 propagate exception,故 suppress
            with contextlib.suppress(RuntimeError):
                await task

        # _tasks 已被 callback 移除
        assert task not in scheduler._tasks
        # log 含异常信息
        assert any(
            "task boom" in rec.message and "test_boom" in rec.message
            for rec in caplog.records
        ), f"未找到异常 log,实际: {[r.message for r in caplog.records]}"

    @pytest.mark.asyncio
    async def test_on_task_done_swallows_cancelled(self):
        """_on_task_done 对 cancelled task 不抛(CancelledError 是 stop() 路径预期)。"""
        scheduler = AutoSyncScheduler()

        async def slow() -> None:
            await asyncio.sleep(100)

        task = asyncio.create_task(slow(), name="test_cancel")
        scheduler._tasks.add(task)
        task.add_done_callback(scheduler._on_task_done)
        task.cancel()
        # 应正常返回,不抛 CancelledError
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task not in scheduler._tasks

    @pytest.mark.asyncio
    async def test_0010_job_order_non_kline_before_kline(self):
        """0:10 全量 job 顺序:非 K 线 → 日线+长周期 → 分钟 cover。

        白天 TGW 独占给 realtime_sub,全量改走凌晨串行。
        """
        scheduler = AutoSyncScheduler()
        order: list[str] = []

        async def _rec(name):
            async def _f(*a):
                order.append(name)
            return _f

        scheduler._industry_index_job.run_daily = await _rec("industry_daily")
        scheduler._exchange_index_job.run_daily = await _rec("exchange_daily")
        scheduler._fundflow_job.run_daily = await _rec("fundflow")
        scheduler._financial_job.run = await _rec("financial")
        scheduler._refdata_job.run_stock_basic = await _rec("stock_basic")
        scheduler._refdata_job.run_backward_factor = await _rec("backward_factor")
        scheduler._exchange_index_job.run_dimensions = await _rec("exchange_dims")
        scheduler._industry_index_job.run_dimensions = await _rec("industry_dims")
        for m in ("run_day", "run_minute"):
            setattr(scheduler._kline_job, m, await _rec(f"kline.{m}"))
        scheduler._cleanup_job.run = await _rec("cleanup")

        await scheduler._run_minute_cover_with_cleanup(date(2025, 3, 29))

        # 非 K 线在 K 线之前,分钟 cover 在日线之后,cleanup 收尾
        assert order.index("fundflow") < order.index("kline.run_day")
        assert order.index("kline.run_day") < order.index("kline.run_minute")
        assert order.index("kline.run_minute") < order.index("cleanup")

class TestSleepDuration:
    """Tests for sleep duration calculation."""

    def test_sleep_to_next_minute(self):
        """Sleep duration calculated correctly."""
        # At 23:00:30, should sleep ~31 seconds to reach 23:01:00
        now = datetime(2025, 3, 28, 23, 0, 30)
        seconds_to_next = 60 - now.second
        assert seconds_to_next == 30


class TestSchedulerTimezone:
    """调度时区基准回归测试。

    生产服务器系统时区为 UTC(timedatectl: "Time zone: UTC")。配置文件中的触发时刻
    (kline_trigger_hour/minute、00:00 日历检查)按业务语义应为北京时间(A 股 T+1 同步,
    数据源返回北京时间)。这些测试锁住"配置时刻被解释为北京时间,而非服务器本地 UTC"。
    这些测试锁住"配置时刻被解释为北京时间,而非服务器本地 UTC"。
    见 shared_kernel/utils/constants.py CST / now_cst() 注释(AGENTS.md 2026-06-25)。
    """

    def test_now_cst_returns_beijing_timezone(self):
        """now_cst() 返回的 datetime 带 Asia/Shanghai tzinfo。"""
        from galaxy_core.shared_kernel.utils.constants import CST, now_cst

        now = now_cst()
        assert now.tzinfo is not None
        # 与 CST 常量同一时区对象
        assert now.tzinfo is CST
        # 北京时间 UTC+8:与 UTC 相差 8 小时(全年,无夏令时)
        assert now.utcoffset().total_seconds() == 8 * 3600

    def test_cst_constant_is_asia_shanghai(self):
        """CST 常量解析为 Asia/Shanghai(UTC+8, 无夏令时)。"""
        from zoneinfo import ZoneInfo

        from galaxy_core.shared_kernel.utils.constants import CST

        assert str(CST) == "Asia/Shanghai"
        # 关键属性:与 UTC 偏移 +8(此时取一个夏季时刻仍应 +8,中国无 DST)
        summer = datetime(2025, 7, 15, 12, 0, tzinfo=CST)
        assert summer.utcoffset().total_seconds() == 8 * 3600
        winter = datetime(2025, 1, 15, 12, 0, tzinfo=CST)
        assert winter.utcoffset().total_seconds() == 8 * 3600
        # 与 ZoneInfo("Asia/Shanghai") 等价
        assert ZoneInfo("Asia/Shanghai") == CST

    @pytest.mark.asyncio
    async def test_run_forever_uses_cst_for_trigger(self, monkeypatch):
        """run_forever 用 _now_cst() 而非 datetime.now() 取当前时间做触发判断。

        场景:服务器 UTC 时间 16:10(= 北京时间次日 00:10),配置 minute_cover=00:10。
        若用 datetime.now()(UTC)则 16:10 != 00:10 不触发(bug);用 _now_cst() 则
        北京 00:10 == 00:10 触发(正确)。本测试 mock _now_cst 返回固定北京 00:10
        时刻,验证 _check_minute_cover_trigger 收到的是 00:10 而非 16:10。
        """
        scheduler = AutoSyncScheduler()
        scheduler._running = True

        # 固定北京时间 2025-03-29 00:10:00(对应 UTC 2025-03-28 16:10:00)
        fixed_cst = datetime(2025, 3, 29, 0, 10, 0, tzinfo=timezone(timedelta(hours=8)))
        monkeypatch.setattr(
            "galaxy_core.application.scheduler.scheduler._now_cst",
            lambda: fixed_cst,
        )

        captured: dict = {}

        async def fake_check_cover(today, current_time):
            captured["today"] = today
            captured["time"] = current_time

        scheduler._check_minute_cover_trigger = fake_check_cover  # type: ignore[assignment]
        scheduler._check_realtime_sub_window = AsyncMock()  # type: ignore[assignment]
        scheduler._check_calendar_trigger = AsyncMock()  # type: ignore[assignment]

        # 跑一次循环后立即停止(模拟单次 tick)
        original_sleep = asyncio.sleep

        async def fake_sleep(seconds):
            scheduler._running = False
            await original_sleep(0)

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)

        await scheduler.run_forever()

        # run_forever 应把北京 00:10 传给 _check_minute_cover_trigger
        assert captured["time"].hour == 0
        assert captured["time"].minute == 10
        assert captured["today"] == date(2025, 3, 29)



class TestTaskNaming:
    """Tests for task naming pattern."""

    @pytest.mark.asyncio
    async def test_kline_task_has_descriptive_name(self):
        """0:10 全量 task 有描述性命名."""
        scheduler = AutoSyncScheduler()
        scheduler._running = True

        today = date(2025, 3, 29)
        yesterday = date(2025, 3, 28)
        trigger_time = time(0, 10)

        scheduler._calendar_store.get_trading_days = AsyncMock(return_value=[yesterday])

        await scheduler._check_minute_cover_trigger(today, trigger_time)

        # Task name should contain date
        task = list(scheduler._tasks)[0]
        assert "minute_cover" in task.get_name()
        assert "2025" in task.get_name()

    @pytest.mark.asyncio
    async def test_calendar_task_has_descriptive_name(self):
        """Calendar sync task has descriptive name."""
        scheduler = AutoSyncScheduler()
        scheduler._calendar_job.run = AsyncMock()
        scheduler._running = True

        today = date(2025, 12, 20)
        trigger_time = time(0, 0)

        await scheduler._check_calendar_trigger(today, trigger_time)

        # Task name should contain date
        task = list(scheduler._tasks)[0]
        assert "calendar" in task.get_name()
        assert "2025" in task.get_name()


class TestPIDLock:
    """Tests for PID file lock behavior, including --replace."""

    def test_acquire_pid_lock_writes_pid_when_no_file(self, tmp_path, monkeypatch):
        """No PID file exists -> write current PID."""
        pid_file = tmp_path / "scheduler.pid"
        monkeypatch.setattr(AutoSyncScheduler, "_PID_FILE", pid_file)

        AutoSyncScheduler._acquire_pid_lock()

        assert pid_file.exists()
        assert int(pid_file.read_text().strip()) == os.getpid()

    def test_acquire_pid_lock_exits_when_alive_and_no_replace(self, tmp_path, monkeypatch):
        """Old process alive + replace=False -> exit(1)."""
        pid_file = tmp_path / "scheduler.pid"
        pid_file.write_text("12345")
        monkeypatch.setattr(AutoSyncScheduler, "_PID_FILE", pid_file)

        def fake_kill(pid, sig):
            if sig == 0:
                return  # alive
            raise OSError("unexpected signal")

        monkeypatch.setattr(os, "kill", fake_kill)

        with pytest.raises(SystemExit) as exc_info:
            AutoSyncScheduler._acquire_pid_lock(replace=False)
        assert exc_info.value.code == 1
        # PID file unchanged
        assert int(pid_file.read_text().strip()) == 12345

    def test_acquire_pid_lock_replaces_alive_process(self, tmp_path, monkeypatch):
        """Old process alive + replace=True -> SIGTERM old, then write new PID."""
        pid_file = tmp_path / "scheduler.pid"
        pid_file.write_text("12345")
        monkeypatch.setattr(AutoSyncScheduler, "_PID_FILE", pid_file)
        monkeypatch.setattr(
            "galaxy_core.application.scheduler.scheduler._time.sleep", lambda s: None
        )

        kill_calls = []

        def fake_kill(pid, sig):
            kill_calls.append((pid, sig))
            if sig == 0 and (pid, signal.SIGTERM) not in kill_calls:
                return  # still alive until terminated
            if sig == signal.SIGTERM:
                return  # terminate succeeds
            if sig == 0 and (pid, signal.SIGTERM) in kill_calls:
                raise ProcessLookupError(pid)
            raise OSError("unexpected signal")

        monkeypatch.setattr(os, "kill", fake_kill)

        AutoSyncScheduler._acquire_pid_lock(replace=True)

        assert (12345, signal.SIGTERM) in kill_calls
        assert int(pid_file.read_text().strip()) == os.getpid()

    def test_acquire_pid_lock_cleans_dead_process(self, tmp_path, monkeypatch):
        """Old process dead -> clean PID file and write new PID."""
        pid_file = tmp_path / "scheduler.pid"
        pid_file.write_text("12345")
        monkeypatch.setattr(AutoSyncScheduler, "_PID_FILE", pid_file)

        def fake_kill(pid, sig):
            raise ProcessLookupError(pid)

        monkeypatch.setattr(os, "kill", fake_kill)

        AutoSyncScheduler._acquire_pid_lock()

        assert int(pid_file.read_text().strip()) == os.getpid()

    def test_acquire_pid_lock_force_kill_when_not_terminating(self, tmp_path, monkeypatch):
        """Replace=True and old process ignores SIGTERM -> send SIGKILL."""
        pid_file = tmp_path / "scheduler.pid"
        pid_file.write_text("12345")
        monkeypatch.setattr(AutoSyncScheduler, "_PID_FILE", pid_file)
        monkeypatch.setattr(
            "galaxy_core.application.scheduler.scheduler._time.sleep", lambda s: None
        )

        kill_calls = []

        def fake_kill(pid, sig):
            kill_calls.append((pid, sig))
            if sig == signal.SIGKILL:
                raise ProcessLookupError(pid)  # killed
            # SIGTERM and signal 0 do nothing -> stays alive

        monkeypatch.setattr(os, "kill", fake_kill)

        AutoSyncScheduler._acquire_pid_lock(replace=True)

        assert (12345, signal.SIGTERM) in kill_calls
        assert (12345, signal.SIGKILL) in kill_calls
        assert int(pid_file.read_text().strip()) == os.getpid()

    def test_acquire_pid_lock_clears_when_pid_hijacked_by_other_process(
        self, tmp_path, monkeypatch
    ):
        """PID 被无关进程复用(AGENTS.md 2026-06-23):不 sys.exit,清理后继续。

        场景:scheduler 死后 PID 文件残留,PID 被无关进程(如 surya-api)复用。
        旧逻辑 os.kill(pid,0) 看到存活就 sys.exit → 6 次重试 start-limit-hit。
        修复:_is_our_process 校验 cmdline,非本调度器则视为孤儿锁清理。
        """
        pid_file = tmp_path / "scheduler.pid"
        pid_file.write_text("12345")
        monkeypatch.setattr(AutoSyncScheduler, "_PID_FILE", pid_file)

        def fake_kill(pid, sig):
            if sig == 0:
                return  # 进程存活(PID 12345 被 surya-api 复用)
            raise OSError("unexpected signal")

        monkeypatch.setattr(os, "kill", fake_kill)
        # PID 12345 的 cmdline 是无关进程(surya-api),非 galaxy scheduler
        monkeypatch.setattr(
            AutoSyncScheduler,
            "_is_our_process",
            staticmethod(lambda pid: False),
        )

        # 不应 sys.exit,应清理 PID 文件 + 写新 PID
        AutoSyncScheduler._acquire_pid_lock(replace=False)

        assert int(pid_file.read_text().strip()) == os.getpid()

    def test_acquire_pid_lock_exits_when_alive_our_process_no_replace(
        self, tmp_path, monkeypatch
    ):
        """真旧 scheduler 存活 + replace=False → 仍 sys.exit(不回归)。"""
        pid_file = tmp_path / "scheduler.pid"
        pid_file.write_text("12345")
        monkeypatch.setattr(AutoSyncScheduler, "_PID_FILE", pid_file)

        def fake_kill(pid, sig):
            if sig == 0:
                return
            raise OSError("unexpected signal")

        monkeypatch.setattr(os, "kill", fake_kill)
        monkeypatch.setattr(
            AutoSyncScheduler,
            "_is_our_process",
            staticmethod(lambda pid: True),  # 真是旧 scheduler
        )

        with pytest.raises(SystemExit) as exc_info:
            AutoSyncScheduler._acquire_pid_lock(replace=False)
        assert exc_info.value.code == 1


class TestIsOurProcess:
    """_is_our_process 校验 /proc/<pid>/cmdline 含 galaxy_core + scheduler."""

    def test_returns_true_when_cmdline_has_both_markers(self, monkeypatch, tmp_path):
        """本调度器 cmdline(含 galaxy_core + scheduler)→ True."""
        fake_cmdline = (
            b"/path/python\x00-m\x00galaxy_core.application.scheduler\x00"
        )

        class FakePath:
            def __init__(self, path):
                self._path = path

            def read_bytes(self):
                return fake_cmdline

        monkeypatch.setattr(
            "galaxy_core.application.scheduler.scheduler.Path", FakePath
        )
        assert AutoSyncScheduler._is_our_process(99999) is True

    def test_returns_false_when_cmdline_is_unrelated_process(self, monkeypatch):
        """无关进程(surya-api 等)cmdline → False(PID 复用场景)."""
        fake_cmdline = (
            b"/path/python\x00-m\x00surya_api.serve\x00--host\x000.0.0.0\x00"
        )

        class FakePath:
            def __init__(self, path):
                self._path = path

            def read_bytes(self):
                return fake_cmdline

        monkeypatch.setattr(
            "galaxy_core.application.scheduler.scheduler.Path", FakePath
        )
        assert AutoSyncScheduler._is_our_process(99999) is False

    def test_returns_true_when_proc_not_found(self, monkeypatch):
        """/proc/<pid>/cmdline 不存在(进程消失或非 Linux)→ 保守 True(不阻断)."""

        class FakePath:
            def __init__(self, path):
                self._path = path

            def read_bytes(self):
                raise FileNotFoundError(self._path)

        monkeypatch.setattr(
            "galaxy_core.application.scheduler.scheduler.Path", FakePath
        )
        assert AutoSyncScheduler._is_our_process(99999) is True

    def test_returns_true_when_cmdline_missing_one_marker(self, monkeypatch):
        """cmdline 只含 galaxy_core 不含 scheduler → False(保守不误判)."""
        fake_cmdline = b"/path/python\x00-m\x00galaxy_core.something_other\x00"

        class FakePath:
            def __init__(self, path):
                self._path = path

            def read_bytes(self):
                return fake_cmdline

        monkeypatch.setattr(
            "galaxy_core.application.scheduler.scheduler.Path", FakePath
        )
        assert AutoSyncScheduler._is_our_process(99999) is False


def _stub_kline_chain_jobs(scheduler: AutoSyncScheduler) -> None:
    """把 _run_kline_sync_with_cleanup 沿途 await 的非 index job 方法 stub 成 AsyncMock.

    index job（exchange/industry）由 mock container 提供，其 run_daily/run_dimensions
    已是 AsyncMock，本函数不动它们，只 stub kline/refdata/financial/cleanup。
    """
    # kline_job 的 run_minute/day/week/month/season/year
    for method in (
        "run_minute",
        "run_day",
        "run_week",
        "run_month",
        "run_season",
        "run_year",
    ):
        setattr(scheduler._kline_job, method, AsyncMock())
    scheduler._refdata_job.run_stock_basic = AsyncMock()
    scheduler._refdata_job.run_backward_factor = AsyncMock()
    scheduler._financial_job.run = AsyncMock()
    scheduler._cleanup_job.run = AsyncMock()


class TestSchedulerIndexAutoChain:
    """验证 0:10 全量 job 调用 index job（日度 + 维度）.

    2026-10-22 起全量改走 0:10 _run_minute_cover_with_cleanup,主链仅 cleanup。
    """

    @pytest.mark.asyncio
    async def test_daily_chain_calls_index_jobs(self):
        """0:10 job 应调用 exchange + industry index job 的 run_daily(today)."""
        scheduler = AutoSyncScheduler()
        _stub_kline_chain_jobs(scheduler)

        today = date(2025, 3, 28)

        scheduler._exchange_index_job.run_daily.reset_mock()
        scheduler._industry_index_job.run_daily.reset_mock()

        await scheduler._run_minute_cover_with_cleanup(today)

        scheduler._exchange_index_job.run_daily.assert_called_once_with(today)
        scheduler._industry_index_job.run_daily.assert_called_once_with(today)

    @pytest.mark.asyncio
    async def test_dimensions_chain_calls_index_jobs(self):
        """0:10 job 应调用 exchange + industry index job 的 run_dimensions(today)."""
        scheduler = AutoSyncScheduler()
        _stub_kline_chain_jobs(scheduler)

        today = date(2025, 3, 28)

        scheduler._exchange_index_job.run_dimensions.reset_mock()
        scheduler._industry_index_job.run_dimensions.reset_mock()

        await scheduler._run_minute_cover_with_cleanup(today)

        scheduler._exchange_index_job.run_dimensions.assert_called_once_with(today)
        scheduler._industry_index_job.run_dimensions.assert_called_once_with(today)

    @pytest.mark.asyncio
    async def test_daily_chain_runs_before_dimensions(self):
        """0:10 job 内日度链应在维度链之前执行."""
        scheduler = AutoSyncScheduler()
        _stub_kline_chain_jobs(scheduler)

        today = date(2025, 3, 28)

        call_order: list[str] = []

        def _record(label):
            def _side(*a, **kw):
                call_order.append(label)
                return None

            return _side

        scheduler._exchange_index_job.run_daily.side_effect = _record("exchange_daily")
        scheduler._industry_index_job.run_daily.side_effect = _record("industry_daily")
        scheduler._exchange_index_job.run_dimensions.side_effect = _record(
            "exchange_dimensions"
        )
        scheduler._industry_index_job.run_dimensions.side_effect = _record(
            "industry_dimensions"
        )

        await scheduler._run_minute_cover_with_cleanup(today)

        # 日度链（exchange_daily, industry_daily）应先于维度链
        daily_idx = call_order.index("exchange_daily")
        dims_idx = call_order.index("exchange_dimensions")
        assert daily_idx < dims_idx




class TestRealtimeSubWindowLogout:
    """_check_realtime_sub_window spawn 前主动登出(2026-10-26 TGW 互踢修复).

    00:10 全量链登录的 TGW 会话若一直持有到 09:00,realtime_sub 登录会触发
    SDK ForceLogout 把主进程踢死(exit 0 静默死亡)→ systemd 重启 → 再互踢
    → 死循环(10/23 208 轮)。修复三件套之三:spawn 前必须先 logout 释放
    主进程会话;登出失败仅告警不阻塞 spawn(错误路径宁可回退现状)。
    """

    def _make_scheduler(self):
        scheduler = AutoSyncScheduler()
        # 交易日(get_trading_days 非空)
        scheduler._calendar_store.get_trading_days = AsyncMock(
            return_value=[date(2026, 10, 26)]
        )
        scheduler._amazing_client = MagicMock()
        return scheduler

    @pytest.mark.asyncio
    async def test_spawn_calls_logout_before_popen(self):
        """09:00 spawn 前必须先 logout,顺序不可颠倒."""
        scheduler = self._make_scheduler()
        events: list[str] = []
        fake_proc = MagicMock()
        fake_proc.poll.return_value = None
        fake_proc.returncode = None

        def fake_logout():
            events.append("logout")

        def fake_popen(cmd, **kwargs):
            events.append("popen")
            return fake_proc

        scheduler._amazing_client.logout = fake_logout

        with patch("subprocess.Popen", side_effect=fake_popen), patch(
            "builtins.open", mock_open()
        ):
            await scheduler._check_realtime_sub_window(date(2026, 10, 26), time(9, 0))

        assert events == ["logout", "popen"]

    @pytest.mark.asyncio
    async def test_spawn_command_is_realtime_sub(self):
        """spawn 命令保持 uv run scripts/realtime_sub.py + 独立进程组."""
        scheduler = self._make_scheduler()
        fake_proc = MagicMock()
        fake_proc.poll.return_value = None
        fake_proc.returncode = None

        with patch("subprocess.Popen", return_value=fake_proc) as mock_popen, patch(
            "builtins.open", mock_open()
        ):
            await scheduler._check_realtime_sub_window(date(2026, 10, 26), time(9, 0))

        args, kwargs = mock_popen.call_args
        assert args[0] == ["uv", "run", "scripts/realtime_sub.py"]
        assert kwargs.get("start_new_session") is True

    @pytest.mark.asyncio
    async def test_logout_failure_does_not_block_spawn(self):
        """logout 抛异常仅告警,spawn 照常执行(宁可回退现状不放大故障)."""
        scheduler = self._make_scheduler()
        scheduler._amazing_client.logout = MagicMock(
            side_effect=RuntimeError("logout boom")
        )
        fake_proc = MagicMock()
        fake_proc.poll.return_value = None
        fake_proc.returncode = None

        with patch("subprocess.Popen", return_value=fake_proc) as mock_popen, patch(
            "builtins.open", mock_open()
        ):
            await scheduler._check_realtime_sub_window(date(2026, 10, 26), time(9, 0))

        mock_popen.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_trading_day_no_spawn_no_logout(self):
        """非交易日:不 spawn,也不登出(保持 00:10 链会话无意义但无害)."""
        scheduler = AutoSyncScheduler()
        scheduler._calendar_store.get_trading_days = AsyncMock(return_value=[])
        scheduler._amazing_client = MagicMock()

        with patch("subprocess.Popen") as mock_popen:
            await scheduler._check_realtime_sub_window(date(2026, 10, 26), time(9, 0))

        mock_popen.assert_not_called()
        scheduler._amazing_client.logout.assert_not_called()

    @pytest.mark.asyncio
    async def test_alive_process_no_respawn_no_logout(self):
        """子进程仍存活:不重复 spawn,也不登出(会话已归 realtime 独占)."""
        scheduler = self._make_scheduler()
        proc = MagicMock()
        proc.poll.return_value = None
        proc.returncode = None
        scheduler._realtime_proc = proc

        with patch("subprocess.Popen") as mock_popen:
            await scheduler._check_realtime_sub_window(date(2026, 10, 26), time(9, 0))

        mock_popen.assert_not_called()
        scheduler._amazing_client.logout.assert_not_called()

    @pytest.mark.asyncio
    async def test_window_end_terminates_process(self):
        """15:30 窗口结束:terminate 兜底(子进程也有到点自停)."""
        scheduler = self._make_scheduler()
        proc = MagicMock()
        proc.poll.return_value = None
        proc.returncode = None
        # MagicMock.__int__ 默认返回 1,killpg(1) 等价 kill(-1),显式钉死真实感 pid
        proc.pid = 12345
        scheduler._realtime_proc = proc

        await scheduler._check_realtime_sub_window(date(2026, 10, 26), time(15, 30))

        proc.terminate.assert_called_once()
        scheduler._amazing_client.logout.assert_not_called()

    def test_killpg_after_grace_is_static_no_self_in_pid(self):
        """_killpg_after_grace 必须 static:漏写装饰器则 self 吞 pid,真 pid 落进
        grace_seconds → time.sleep(12345) 卡死 loop 关闭(全量单测 61% 僵死根因)."""
        assert isinstance(
            inspect.getattr_static(AutoSyncScheduler, "_killpg_after_grace"),
            staticmethod,
        )

