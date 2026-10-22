"""自动同步调度器主实现。

按照 SCHED-01：自定义 asyncio 循环，不依赖 APScheduler 或 schedule 库。
每分钟轮询一次，在配置的时间触发同步任务。

支持 auto_sync_interval_minutes 用于周期性同步（测试环境）。
"""

import asyncio
import logging
import os
import signal
import sys
import time as _time
from datetime import date, datetime, time, timedelta
from pathlib import Path

from galaxy_core.application.scheduler.calendar_sync_job import CalendarSyncJob
from galaxy_core.application.scheduler.cleanup_job import CleanupJob
from galaxy_core.application.scheduler.jobs.financial_sync_job import FinancialSyncJob
from galaxy_core.application.scheduler.kline_sync_job import KlineSyncJob
from galaxy_core.application.scheduler.reference_data_sync_job import ReferenceDataSyncJob
from galaxy_core.shared_kernel.utils.config_loader import get_section
from galaxy_core.shared_kernel.utils.constants import now_cst

logger = logging.getLogger(__name__)

# 调度时区基准:北京时间(CST)。统一用 _now_cst() 取当前北京时间做触发判断,
# 配置文件不改——代码把配置中的触发时刻(如 00:10)理解为北京时间而非服务器本地
# 时间(UTC)。CST / now_cst 定义在 shared_kernel/utils/constants.py(AGENTS.md
# 2026-06-25 审计)。
_now_cst = now_cst


class AutoSyncScheduler:
    """按照 SCHED-01 的自动同步调度器，使用自定义 asyncio 循环。

    持续运行，每分钟检查触发条件：
    - kline_trigger_hour/minute 配置的时间触发 K 线同步（生产默认 00:10）
    - 00:00：日历检查（仅 12/20-12/31 真同步下一年交易日历，非 12 月 CalendarSyncJob.run
      立即 return 空转；见 calendar_sync_job.py:45）
    - 00:10：K线同步（kline_trigger_hour/minute 配置，生产默认 00:10，仅交易日后一天）

    所有触发时刻按北京时间解释（`_now_cst()`，服务器系统时区为 UTC 但业务语义时间
    为北京时间；见模块级 CST 注释）。

    测试模式：auto_sync_interval_minutes 启用周期性同步。

    使用 PID 文件锁防止多实例同时运行。
    """

    _PID_FILE = Path("data/logs/scheduler.pid")

    def __init__(self) -> None:
        self._running = False
        self._stopped = False
        self._tasks: set[asyncio.Task] = set()
        self._config = get_section("scheduler")

        # 从 DI 容器获取所有依赖（延迟导入避免循环依赖）
        from galaxy_core.di.container import create_container

        container = create_container()
        self._db_manager = container.db_manager()
        self._calendar_store = container.calendar_store()
        self._reference_provider = container.reference_provider()
        self._kline_service = container.kline_service()
        self._calendar_service = container.calendar_service()
        self._ref_service = container.reference_service()
        self._kline_store = container.kline_store()
        self._kline_provider = container.kline_provider()
        self._financial_service = container.financial_service()
        self._trading_calendar_service = container.trading_calendar_service()

        # 初始化组件，注入依赖
        self._state_manager = container.sync_state_manager()
        self._kline_job = KlineSyncJob(
            self._state_manager,
            kline_service=self._kline_service,
            reference_provider=self._reference_provider,
            calendar_store=self._calendar_store,
            trading_calendar=self._trading_calendar_service,
            db_manager=self._db_manager,
        )
        self._calendar_job = CalendarSyncJob(
            self._state_manager,
            calendar_service=self._calendar_service,
            calendar_store=self._calendar_store,
        )
        self._refdata_job = ReferenceDataSyncJob(
            self._state_manager,
            reference_provider=self._reference_provider,
            db_manager=self._db_manager,
            calendar_store=self._calendar_store,
        )
        self._cleanup_job = CleanupJob(
            state_manager=self._state_manager,
        )
        self._financial_job = FinancialSyncJob(
            self._state_manager,
            financial_service=self._financial_service,
            reference_provider=self._reference_provider,
        )

        # 指数数据同步任务（交易所指数 + 行业指数）
        self._exchange_index_job = container.exchange_index_job()
        self._industry_index_job = container.industry_index_job()

        # Phase 02 资金流向同步任务(02-08, 2026-06-19 范围修订后仅 fundflow)
        self._fundflow_job = container.fundflow_job()

        # 跟踪上次同步时间（用于周期性同步）
        self._last_sync_time: datetime | None = None

        # 检查是否配置了周期性同步
        self._auto_sync_interval = self._config.get("auto_sync_interval_minutes", None)
        if self._auto_sync_interval:
            logger.debug(f"已配置自动同步间隔: 每 {self._auto_sync_interval} 分钟")

    @classmethod
    def _acquire_pid_lock(cls, replace: bool = False) -> None:
        """获取 PID 文件锁。

        检查 PID 文件中记录的进程是否仍存活 + 是否为本调度器进程：
        - 进程不存在（残留 PID 文件）→ 清理后继续
        - 进程存活但非本调度器（PID 被无关进程复用，AGENTS.md 2026-06-23 事件）
          → 视为孤儿锁，清理后继续（不误判，不 sys.exit）
        - 进程存活且为本调度器 + replace=False → 拒绝启动，sys.exit(1)
        - 进程存活且为本调度器 + replace=True → SIGTERM，等待退出，必要时 SIGKILL
        """
        pid_file = cls._PID_FILE
        if pid_file.exists():
            try:
                old_pid = int(pid_file.read_text().strip())
            except (ValueError, OSError):
                # 损坏的 PID 文件，清理后继续
                pid_file.unlink(missing_ok=True)
            else:
                try:
                    os.kill(old_pid, 0)  # 检查进程是否存活（不发信号）
                except ProcessLookupError:
                    # 旧进程已死，清理残留 PID 文件
                    logger.info(f"清理残留 PID 文件（旧进程 {old_pid} 已不存在）")
                    pid_file.unlink(missing_ok=True)
                except PermissionError:
                    # 进程存在但无权发信号
                    logger.error(
                        f"调度器已在运行（PID {old_pid}），无权发送信号，无法启动新实例"
                    )
                    sys.exit(1)
                else:
                    # 进程存活 — 校验身份（防 PID 复用误判，AGENTS.md 2026-06-23）
                    if not cls._is_our_process(old_pid):
                        logger.warning(
                            f"PID 文件记录 {old_pid} 已被无关进程占用"
                            f"（非本调度器），视为孤儿锁清理后继续"
                        )
                        pid_file.unlink(missing_ok=True)
                    elif not replace:
                        logger.error(
                            f"调度器已在运行（PID {old_pid}），无法启动新实例；"
                            f"使用 --replace 强制替换"
                        )
                        sys.exit(1)
                    else:
                        cls._terminate_old_scheduler(old_pid)
                        pid_file.unlink(missing_ok=True)

        # 写入当前 PID
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(str(os.getpid()))
        logger.debug(f"PID 文件锁已获取: {pid_file} (PID {os.getpid()})")

    @staticmethod
    def _is_our_process(pid: int) -> bool:
        """校验 PID 对应进程是否为本调度器进程。

        防 PID 复用误判(AGENTS.md 2026-06-23:scheduler 死后 PID 被 surya-api
        等无关进程复用,旧 PID 锁逻辑只查 ps 活否 → 误拒启动 → start-limit-hit)。

        Linux: 读 /proc/<pid>/cmdline,检查含 'galaxy_core' 且 'scheduler'。
        非 Linux 或读取失败:保守返回 True(不阻断,保持旧行为)。

        Args:
            pid: 待校验的进程 ID

        Returns:
            True = 是本调度器进程(继续走 replace 逻辑);
            False = 无关进程占用该 PID(视为孤儿锁,清理)
        """
        try:
            # /proc/<pid>/cmdline 是 NUL 分隔的 argv;读为 bytes
            cmdline_bytes = Path(f"/proc/{pid}/cmdline").read_bytes()
        except (FileNotFoundError, PermissionError, OSError):
            # 非 Linux 或进程消失或无权读 → 保守返回 True(不阻断)
            return True
        if not cmdline_bytes:
            return True  # 空 cmdline(如内核线程),保守
        cmdline = cmdline_bytes.replace(b"\x00", b" ").decode("utf-8", errors="replace")
        # 双标识:含 galaxy_core 包名 + scheduler 模块名
        return "galaxy_core" in cmdline and "scheduler" in cmdline

    @classmethod
    def _terminate_old_scheduler(cls, old_pid: int) -> None:
        """SIGTERM 旧调度器实例,等待退出,必要时 SIGKILL(replace=True 路径)."""
        logger.info(f"--replace 生效，正在终止旧调度器（PID {old_pid}）...")
        try:
            os.kill(old_pid, signal.SIGTERM)
        except PermissionError:
            logger.error(
                f"无权限终止旧调度器（PID {old_pid}），无法启动新实例"
            )
            sys.exit(1)

        # 等待旧进程退出，最多 5 秒
        for _ in range(50):
            try:
                os.kill(old_pid, 0)
            except ProcessLookupError:
                logger.info(f"旧调度器（PID {old_pid}）已终止")
                return
            except PermissionError:
                logger.error(
                    f"等待旧调度器（PID {old_pid}）时权限丢失，无法启动新实例"
                )
                sys.exit(1)
            _time.sleep(0.1)
        # 仍未退出，强制 SIGKILL
        logger.warning(
            f"旧调度器（PID {old_pid}）未在 5 秒内退出，发送 SIGKILL"
        )
        try:
            os.kill(old_pid, signal.SIGKILL)
        except ProcessLookupError:
            logger.info(f"旧调度器（PID {old_pid}）已终止")
        except PermissionError:
            logger.error(
                f"无权限终止旧调度器（PID {old_pid}），无法启动新实例"
            )
            sys.exit(1)

    @classmethod
    def _release_pid_lock(cls) -> None:
        """释放 PID 文件锁。"""
        pid_file = cls._PID_FILE
        if pid_file.exists():
            try:
                stored_pid = int(pid_file.read_text().strip())
                if stored_pid == os.getpid():
                    pid_file.unlink(missing_ok=True)
                    logger.debug("PID 文件锁已释放")
            except (ValueError, OSError):
                pass

    async def run_forever(self) -> None:
        """按照 SCHED-01 的主调度器循环。

        每分钟轮询，条件匹配时触发同步任务。
        睡眠到下一分钟边界以避免时钟漂移。
        """
        self._running = True
        logger.info("自动同步调度器已启动")

        # 信号审计(2026-06-26):scheduler 曾在无人操作下收到信号后 exit 0 无记录,
        # 导致无法定位发送者。注册 handler 记录信号名+精确时刻+当时状态,至少留下
        # 「确实是信号终止的 + 哪种信号」的证据(sender pid 需内核级 auditd,见 AGENTS.md)。
        # SIGTERM:默认直接终止进程不留日志,此处转优雅退出并记录。
        # SIGINT:asyncio 默认转 KeyboardInterrupt,此处先记录再走原有退出路径。
        loop = asyncio.get_running_loop()
        self._register_signal_audit(loop)

        # 启动验证
        await self._verify_trading_calendar()

        while self._running:
            now = _now_cst()
            current_time = now.time()
            today = now.date()

            # 心跳日志(每小时整点一次,避免每分钟刷屏;2026-07-29 观测盲区修复:
            # 原主循环无 INFO 级日志,scheduler 活着但静默不跑时无任何告警线索)
            if current_time.minute == 0:
                logger.info(
                    f"心跳: 北京 {now.strftime('%Y-%m-%d %H:%M')} "
                    f"活跃task={len(self._tasks)} _running={self._running}"
                )

            # 轮询触发条件
            await self._check_kline_trigger(today, current_time)
            await self._check_kline_catchup_trigger(today, current_time)
            await self._check_margin_catchup_trigger(today, current_time)
            await self._check_minute_cover_trigger(today, current_time)
            await self._check_calendar_trigger(today, current_time)

            # 检查周期性同步（测试模式）
            if self._auto_sync_interval:
                await self._check_interval_sync(today, now)

            # 睡眠到下一分钟边界（避免漂移，参见 RESEARCH.md Pitfall 2）
            seconds_to_next_minute = 60 - now.second
            await asyncio.sleep(seconds_to_next_minute + 1)

        # 循环正常退出(_running 被信号 handler 或 stop() 设 False):确保清理。
        # 信号 handler(_register_signal_audit)设 _running=False 后走此路径,
        # 必须调用 stop() 关闭 DB 连接 + 释放 PID 锁(stop 幂等,重复调用安全)。
        if not self._stopped:
            await self.stop()

    def _register_signal_audit(self, loop: asyncio.AbstractEventLoop) -> None:
        """注册 SIGINT/SIGTERM 审计 handler(2026-06-26).

        scheduler 曾在无人操作下收到信号后 exit 0 无任何记录,无法定位发送者。
        此 handler 记录信号名 + 精确时刻(北京/UTC 双时区)+ 当时状态,然后触发
        优雅退出(设 _running=False 让主循环自然结束)。

        限制:POSIX 信号机制不向接收进程传递发送者 PID,纯用户态拿不到 sender
        (需内核级 auditd/BPF,见 AGENTS.md 2026-06-26)。本 handler 的价值是
        确认「确实是信号终止的 + 哪种信号 + 何时」,排除其他退出可能。
        """
        def _on_signal(signum: int) -> None:
            sig_name = signal.Signals(signum).name
            now_beijing = _now_cst()
            active_tasks = len(self._tasks)
            logger.warning(
                f"收到信号 {sig_name}({signum})——时刻 北京{now_beijing.isoformat()} "
                f"PID={os.getpid()} _running={self._running} 活跃task={active_tasks}。"
                f"触发优雅退出(sender pid 需内核 auditd 追溯)"
            )
            # 触发优雅退出:主循环 while self._running 自然结束 → run_scheduler 走
            # 正常 return 0(非 KeyboardInterrupt 路径,避免 asyncio 默认 SIGINT 行为
            # 把信号转成未捕获异常)。信号幂等:重复信号不再处理。
            if self._running:
                self._running = False

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _on_signal, sig)
            except (NotImplementedError, RuntimeError):
                # Windows 无 add_signal_handler;非主线程会 RuntimeError——降级
                # 到无审计(保持原行为,不阻断启动)。
                logger.debug(f"无法注册 {sig.name} 审计 handler(平台/线程限制)")

    async def _verify_trading_calendar(self) -> None:
        """确保当前年和下一年的交易日历存在。"""
        current_year = _now_cst().year
        logger.debug(f"交易日历验证: {current_year} 年")
        # TradingCalendarService 按需处理缺失的日历

    async def _is_first_non_trading_day_of_month(self, today: date) -> bool:
        """检查今天是否是本月第一个非交易日。

        返回 True 的条件：
        - 今天不是交易日
        - 昨天是交易日（即今天是紧接的休息日）
        - 从月初到昨天的所有天都是交易日（之前没有休息日）
        """
        # 首先检查今天是否是非交易日
        trading_days_today = await self._calendar_store.get_trading_days(today, today)
        if trading_days_today:
            # 今天是交易日，不符合条件
            return False

        # 获取月初日期
        month_start = today.replace(day=1)

        # 如果今天是月初且是非交易日，则是第一个非交易日
        if today == month_start:
            return True

        # 检查昨天是否是交易日
        yesterday = today - timedelta(days=1)
        yesterday_trading = await self._calendar_store.get_trading_days(yesterday, yesterday)
        if not yesterday_trading:
            # 昨天也是非交易日，所以今天不是第一个非交易日
            return False

        # 检查从月初到昨天是否都是交易日
        prev_days = await self._calendar_store.get_trading_days(month_start, yesterday)
        expected_calendar_days = (yesterday - month_start).days + 1  # inclusive count

        if len(prev_days) == expected_calendar_days:
            return True

        # 今天之前有其他非交易日（周末/节假日）
        return False

    async def _check_kline_trigger(self, today: date, current_time: time) -> None:
        """检查并在配置的时间触发K线同步（生产默认 00:10，仅交易日后一天）。

        只在昨天是交易日时触发（T+1 模式）。非交易日无新数据，无需同步。
        K线同步完成后触发同步后验证（D-19）和日志清理。
        """
        trigger_hour = self._config.get("kline_trigger_hour", 0)
        trigger_minute = self._config.get("kline_trigger_minute", 10)

        if current_time.hour == trigger_hour and current_time.minute == trigger_minute:
            yesterday = today - timedelta(days=1)
            trading_days = await self._calendar_store.get_trading_days(yesterday, yesterday)
            if not trading_days:
                # 提级 debug→info(2026-07-29 观测盲区):非交易日跳过应可见,
                # 否则 scheduler 静默不跑时无任何线索(calendar instant 错位 bug
                # 就是因为跳过日志全 debug,INFO 级看不到)
                logger.info(f"跳过K线同步: {yesterday} 不是交易日，无新数据")
                return

            logger.info(f"触发K线同步: {current_time} (同步日期 {yesterday})")

            task = asyncio.create_task(
                self._run_kline_sync_with_cleanup(today),
                name=f"kline_sync_{today}"
            )
            self._tasks.add(task)
            task.add_done_callback(self._on_task_done)

    async def _check_kline_catchup_trigger(
        self, today: date, current_time: time
    ) -> None:
        """K线补同步(catch-up,2026-08-20 AM 数据发布延迟根治)。

        AM 服务端 T-1 K线数据发布时刻不稳定(实测约半数交易日凌晨未发布,
        整夜 7 次重试全空,SDK 把查询 date_range 上界截到 T-2;次日才可用,
        见 AGENTS.md 2026-08-20)。此触发在白天(默认 07:10)检查昨日
        kline_day 是否已同步,未同步则重跑同步链:
        - 链内各 job 由 is_synced 门控,已同步的自动跳过(幂等);
        - kline_day 重跑时若数据已发布则当天闭环,不再等次日凌晨。
        防并发:00:10 的同步链可能仍在重试中(kline 重试跨 6h),此时不得
        再起第二条链(API 不支持并发,SDK 单例)。
        """
        trigger_hour = self._config.get("kline_catchup_hour", 7)
        trigger_minute = self._config.get("kline_catchup_minute", 10)

        if current_time.hour == trigger_hour and current_time.minute == trigger_minute:
            yesterday = today - timedelta(days=1)
            trading_days = await self._calendar_store.get_trading_days(
                yesterday, yesterday
            )
            if not trading_days:
                logger.info(f"跳过K线补同步: {yesterday} 不是交易日，无新数据")
                return

            # 防并发:00:10 同步链仍在运行(如 kline 重试中)则不再起链
            active = [
                t
                for t in self._tasks
                if not t.done()
                and t.get_name() in (f"kline_sync_{today}", f"kline_catchup_{today}")
            ]
            if active:
                logger.info(
                    f"跳过K线补同步: 同步链仍在运行 "
                    f"({[t.get_name() for t in active]})"
                )
                return

            period_id = yesterday.strftime("%Y%m%d")
            if await self._state_manager.is_synced("kline_day", period_id):
                logger.info(f"跳过K线补同步: kline_day {period_id} 已同步")
                return

            logger.info(
                f"触发K线补同步(catch-up): {current_time} (同步日期 {yesterday})"
            )

            task = asyncio.create_task(
                self._run_kline_sync_with_cleanup(today),
                name=f"kline_catchup_{today}"
            )
            self._tasks.add(task)
            task.add_done_callback(self._on_task_done)
    async def _check_minute_cover_trigger(
        self, today: date, current_time: time
    ) -> None:
        """分钟线 T+1 定稿覆盖(2026-10-22 引入,次日 0:10).

        盘中 realtime_sub 已实时写当日分钟线(is_final=false);此处用
        query_kline 同窗拉取定稿覆盖(is_final=true,残缺尾巴修正)。
        仅昨天是交易日时触发。防并发:与 kline 主链同名任务互斥
        (API 不支持并发,SDK 单例)。
        """
        trigger_hour = self._config.get("minute_cover_hour", 0)
        trigger_minute = self._config.get("minute_cover_minute", 10)

        if current_time.hour == trigger_hour and current_time.minute == trigger_minute:
            yesterday = today - timedelta(days=1)
            trading_days = await self._calendar_store.get_trading_days(
                yesterday, yesterday
            )
            if not trading_days:
                logger.info(f"跳过分钟线覆盖: {yesterday} 不是交易日")
                return

            active = [
                t
                for t in self._tasks
                if not t.done()
                and t.get_name()
                in (f"kline_sync_{today}", f"kline_catchup_{today}", f"minute_cover_{today}")
            ]
            if active:
                logger.info(
                    f"跳过分钟线覆盖: 同步任务仍在运行 "
                    f"({[t.get_name() for t in active]})"
                )
                return

            logger.info(f"触发分钟线定稿覆盖: {current_time} (覆盖日期 {yesterday})")

            task = asyncio.create_task(
                self._run_minute_cover_with_cleanup(today),
                name=f"minute_cover_{today}",
            )
            self._tasks.add(task)
            task.add_done_callback(self._on_task_done)

    async def _check_margin_catchup_trigger(
        self, today: date, current_time: time
    ) -> None:
        """晚间补同步触发(2026-09-09 引入,2026-09-11 扩展为 margin+industry)。

        T+1 数据 AM 端发布时刻不稳(实证:margin_detail 15:27 仍空、
        industry_daily 跨小时涓流),12:00 链重试(5min×3,~16:00 结束)
        仍不足时,默认 19:50(北京)最后补拉一次。两个目标串行(API 不支持
        并发),各自 is_synced 门控:已成功跳过、失败/未达覆盖率则重跑。
        防并发:当日同步链任务仍在运行则跳过。
        """
        trigger_hour = self._config.get("margin_catchup_hour", 19)
        trigger_minute = self._config.get("margin_catchup_minute", 50)

        if current_time.hour == trigger_hour and current_time.minute == trigger_minute:
            yesterday = today - timedelta(days=1)
            trading_days = await self._calendar_store.get_trading_days(
                yesterday, yesterday
            )
            if not trading_days:
                logger.info(
                    f"跳过晚间补同步: {yesterday} 不是交易日,无新数据"
                )
                return

            active = [t for t in self._tasks if not t.done()]
            if active:
                logger.info(
                    f"跳过晚间补同步: 同步链仍在运行 "
                    f"({[t.get_name() for t in active]})"
                )
                return

            logger.info(f"触发晚间补同步: {current_time}")

            task = asyncio.create_task(
                self._run_evening_catchup(today),
                name=f"margin_catchup_{today}",
            )
            self._tasks.add(task)
            task.add_done_callback(self._on_task_done)

    async def _run_minute_cover_with_cleanup(self, today: date) -> None:
        """分钟线 T+1 定稿覆盖执行体:run_minute 拉昨日全 8 周期覆盖。

        run_minute 同步昨日窗口,upsert 按 (symbol, trade_time) 覆盖
        realtime_sub 的 is_final=false 行 → is_final=true 定稿。
        AM 常 T+2 才发布(昨日 0:10 覆盖后仍有 is_final=false 残留):
        残留追扫往回 N 天(today-2..today-8),残留>0 即重跑该日覆盖,
        直到全定稿。满 8 天仍有残留记 error 待人工(AM 侧缺数)。
        覆盖后应用 retention policy(minute_retention_days,滚动删超期 chunk)。
        """
        logger.info("运行分钟线定稿覆盖")
        try:
            await self._kline_job.run_minute(today)
        except Exception as e:
            logger.error(f"分钟线定稿覆盖失败: {e}", exc_info=True)
        try:
            await self._rescan_unfinalized(today)
        except Exception as e:
            logger.error(f"分钟线残留追扫失败: {e}", exc_info=True)
        try:
            await self._apply_minute_retention()
        except Exception as e:
            logger.error(f"分钟线 retention 应用失败: {e}", exc_info=True)

    async def _rescan_unfinalized(self, today: date) -> None:
        """残留追扫:往回 8 天查 is_final=false,有残留即重跑该日覆盖。"""
        from datetime import timedelta

        minute_tables = (
            "kline_min1", "kline_min3", "kline_min5", "kline_min10",
            "kline_min15", "kline_min30", "kline_min60", "kline_min120",
        )
        async with self._db_manager.session() as session:
            from sqlalchemy import text as _text

            for back in range(2, 9):
                day = today - timedelta(days=back)
                try:
                    days = await session.execute(
                        _text("SELECT 1 FROM trading_calendar WHERE trade_date = :d LIMIT 1"),
                        {"d": day},
                    )
                    if days.first() is None:
                        continue
                except Exception:
                    continue
                residual = 0
                for table in minute_tables:
                    try:
                        r = await session.execute(
                            _text(
                                f"SELECT count(*) FROM {table} "
                                "WHERE trade_time::date = :d AND is_final = false"
                            ),
                            {"d": day},
                        )
                        residual += r.scalar() or 0
                    except Exception:
                        continue
                if residual:
                    logger.info(f"分钟线残留追扫: {day} 残留 {residual} 行,重跑覆盖")
                    try:
                        await self._reset_minute_marks(day)
                        await self._kline_job.run_minute(day + timedelta(days=1))
                    except Exception as e:
                        logger.error(f"残留追扫 {day} 重跑失败: {e}", exc_info=True)

    async def _reset_minute_marks(self, day: date) -> None:
        """重置某日 8 分钟表的 success 标记 → pending,允许重跑覆盖。"""
        period_id = day.strftime("%Y%m%d")
        for iv in ("min1", "min3", "min5", "min10", "min15", "min30", "min60", "min120"):
            try:
                async with self._db_manager.session() as session:
                    from sqlalchemy import update as _update

                    from galaxy_core.database.models.sync_state import SyncState

                    await session.execute(
                        _update(SyncState)
                        .where(
                            SyncState.sync_type == f"kline_{iv}",
                            SyncState.period_identifier == period_id,
                            SyncState.sync_status == "success",
                        )
                        .values(sync_status="pending")
                    )
                    await session.commit()
            except Exception as e:
                logger.warning(f"重置标记失败 kline_{iv} {period_id}: {e}")
    async def _apply_minute_retention(self) -> None:
        """8 分钟表应用滚动 retention(幂等,interval 取 config)。"""
        from galaxy_core.database.core.timescale import apply_retention_policy

        days = self._config.get("minute_retention_days", 22)
        async with self._db_manager.session() as session:
            for table in (
                "kline_min1", "kline_min3", "kline_min5", "kline_min10",
                "kline_min15", "kline_min30", "kline_min60", "kline_min120",
            ):
                ok = await apply_retention_policy(session, table, days)
                if ok:
                    logger.info(f"retention 已应用: {table} = {days} 天")

    async def _run_evening_catchup(self, today: date) -> None:
        """晚间补同步执行体:两融(margin)→ 行业指数(daily+weight)串行.

        各自编排层门控已成功的 sync_type 自动跳过;失败/未达覆盖率的
        (industry_daily 覆盖率熔断、margin_detail 空结果熔断)重跑。
        单 job 失败仅记日志,不阻断另一个(对齐日度链隔离模式)。
        """
        try:
            await self._fundflow_job.run_daily(today, target="margin")
        except Exception as e:
            logger.error(f"晚间补同步 fundflow margin 失败: {e}", exc_info=True)
        try:
            await self._industry_index_job.run_daily(today)
        except Exception as e:
            logger.error(f"晚间补同步 industry 指数失败: {e}", exc_info=True)

    async def _run_kline_sync_with_cleanup(self, today: date) -> None:
        """K-line 周期调用链。

        MIN → DAY → [指数日度行情/权重] → (sleep) → WEEK → MONTH → SEASON → YEAR
        → refdata → [指数维度数据] → financial → cleanup.
        按顺序执行，复用已初始化的基础设施（API 登录、DB 连接）。
        各步独立 try/except 隔离(2026-07-28 Bug 3: 单步 raise 不阻断后续,
        对齐 fundflow 既有模式)。
        参考数据同步在所有 K 线之后运行（API 不支持并发）。
        指数日度数据（industry_daily/index_weight/industry_weight）紧跟 K线 day，
        维度数据（成分股/基本信息）紧跟 refdata，财务数据同步最后运行。
        """
        # 1. 分钟线同步已移出主链(2026-10-22):盘中由 realtime_sub 实时写,
        # 次日 0:10 独立 minute cover job 用 query_kline 覆盖定稿。白天 TGW 留给实时订阅。

        # 2. 日线同步
        logger.debug("运行日线同步")
        try:
            await self._kline_job.run_day(today)
        except Exception as e:
            logger.error(f"日线同步失败: {e}", exc_info=True)

        # 2.5 指数日度数据（industry_daily + index_weight + industry_weight）
        logger.debug("运行指数日度数据同步")
        try:
            await self._exchange_index_job.run_daily(today)
        except Exception as e:
            logger.error(f"交易所指数日度同步失败: {e}", exc_info=True)
        try:
            await self._industry_index_job.run_daily(today)
        except Exception as e:
            logger.error(f"行业指数日度同步失败: {e}", exc_info=True)

        # 等待同步稳定
        await asyncio.sleep(5)

        # 3. 周线同步（按需）
        logger.debug("运行周线同步")
        try:
            await self._kline_job.run_week(today)
        except Exception as e:
            logger.error(f"周线同步失败: {e}", exc_info=True)

        # 4. 月线同步（按需）
        logger.debug("运行月线同步")
        try:
            await self._kline_job.run_month(today)
        except Exception as e:
            logger.error(f"月线同步失败: {e}", exc_info=True)

        # 5. 季线同步（按需）
        logger.debug("运行季线同步")
        try:
            await self._kline_job.run_season(today)
        except Exception as e:
            logger.error(f"季线同步失败: {e}", exc_info=True)

        # 6. 年线同步（按需）
        logger.debug("运行年线同步")
        try:
            await self._kline_job.run_year(today)
        except Exception as e:
            logger.error(f"年线同步失败: {e}", exc_info=True)

        # 7. 参考数据 stock_basic 同步(P0: 每周,快)
        # 2026-08-04 拆分:原 refdata_job.run(today) 含 stock_basic + backward_factor,
        # backward_factor 月度全量(9000万条,2h+)阻塞后续 fundflow → long_hu_bang
        # 拖到凌晨 SDK 不稳定时段全失败。拆出 stock_basic(快)先跑,
        # backward_factor 移到 chain 末尾(第 8.8 步)不阻塞 fundflow。
        logger.debug("运行参考数据 stock_basic 同步")
        try:
            await self._refdata_job.run_stock_basic(today)
        except Exception as e:
            logger.error(f"参考数据 stock_basic 同步失败: {e}", exc_info=True)

        # 7.5 指数维度数据（成分股/基本信息，周度/月度）
        logger.debug("运行指数维度数据同步")
        try:
            await self._exchange_index_job.run_dimensions(today)
        except Exception as e:
            logger.error(f"交易所指数维度同步失败: {e}", exc_info=True)
        try:
            await self._industry_index_job.run_dimensions(today)
        except Exception as e:
            logger.error(f"行业指数维度同步失败: {e}", exc_info=True)

        # 8. 财务数据月度同步（内部按 period_id=YYYY-MM 去重）
        try:
            await self._financial_job.run(today)
        except Exception as e:
            logger.error(f"财务数据同步失败: {e}", exc_info=True)

        # 8.5 资金流向同步 (akshare 1 + amazingdata 4 = 5 表) — Phase 02
        # 非阻断:单 job 失败仅记日志,不影响后续 cleanup
        logger.debug("运行资金流向同步")
        try:
            await self._fundflow_job.run_daily(today)
        except Exception as e:
            logger.error(f"资金流向同步失败: {e}", exc_info=True)

        # 8.8 参考数据 backward_factor 同步(月度,慢,全量 ~2h+)
        # 2026-08-04 移到 chain 末尾(fundflow 之后):月度全量耗时长,放末尾不阻塞
        # 已完成的 fundflow。backward_factor 月度门控(is_synced month_id),非月度
        # 日秒过;月初触发全量时即使 2h+ 也只影响 cleanup(非关键)。
        logger.debug("运行参考数据 backward_factor 同步")
        try:
            await self._refdata_job.run_backward_factor(today)
        except Exception as e:
            logger.error(f"参考数据 backward_factor 同步失败: {e}", exc_info=True)

        # 9. 日志清理（复用基础设施）
        logger.debug("运行日志清理")
        try:
            await self._cleanup_job.run()
        except Exception as e:
            logger.error(f"日志清理失败: {e}", exc_info=True)

    def _on_task_done(self, task: asyncio.Task) -> None:
        """task 完成 callback:从 _tasks 移除 + retrieve exception(2026-07-28 Bug 3)。

        原先 add_done_callback(self._tasks.discard) 只移除,不 retrieve 异常,
        导致 task 内 raise 时只 GC 时打 "Task exception was never retrieved" 警告,
        scheduler 主循环完全无感知。现在显式 retrieve + log error。
        CancelledError 是 stop() 路径预期,不视为异常。
        """
        self._tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error(
                f"任务 {task.get_name()} 异常退出: {exc}",
                exc_info=exc,
            )

    async def _check_calendar_trigger(self, today: date, current_time: time) -> None:
        """检查并在 00:00 触发日历同步。"""
        if current_time.hour == 0 and current_time.minute == 0:
            logger.debug(f"触发日历检查: {current_time}")
            task = asyncio.create_task(
                self._calendar_job.run(today),
                name=f"calendar_sync_{today}"
            )
            self._tasks.add(task)
            task.add_done_callback(self._on_task_done)

    async def _check_interval_sync(self, today: date, now: datetime) -> None:
        """检查并触发周期性同步（测试模式）。

        如果配置了 auto_sync_interval_minutes，则每隔该间隔触发K线同步。
        首次同步等待 auto_sync_first_delay_minutes 后才触发（默认等于间隔）。
        """
        if not self._auto_sync_interval:
            return

        # 首次检查时初始化
        if self._last_sync_time is None:
            self._last_sync_time = now
            self._first_sync_delay = self._config.get(
                "auto_sync_first_delay_minutes", self._auto_sync_interval
            )
            logger.debug(
                f"周期性同步初始化，间隔 {self._auto_sync_interval} 分钟，"
                f"首次同步将在 {self._first_sync_delay} 分钟后"
            )
            return

        elapsed_minutes = (now - self._last_sync_time).total_seconds() / 60

        # 首次同步使用独立延迟
        if hasattr(self, "_first_sync_delay"):
            if elapsed_minutes >= self._first_sync_delay:
                logger.debug(
                    f"触发首次周期性同步（已过去: {elapsed_minutes:.1f} 分钟）"
                )
                task = asyncio.create_task(
                    self._run_kline_sync_with_cleanup(today),
                    name=f"interval_sync_{today}_{now.strftime('%H%M')}"
                )
                self._tasks.add(task)
                task.add_done_callback(self._on_task_done)
                self._last_sync_time = now
                delattr(self, "_first_sync_delay")
            return

        # 后续同步使用正常间隔
        if elapsed_minutes >= self._auto_sync_interval:
            logger.debug(f"触发周期性同步（已过去: {elapsed_minutes:.1f} 分钟）")
            task = asyncio.create_task(
                self._run_kline_sync_with_cleanup(today),
                name=f"interval_sync_{today}_{now.strftime('%H%M')}"
            )
            self._tasks.add(task)
            task.add_done_callback(self._on_task_done)
            self._last_sync_time = now

    async def stop(self) -> None:
        """优雅地停止调度器。

        取消所有待处理任务并关闭数据库连接。
        幂等：多次调用仅执行一次清理。
        """
        if self._stopped:
            return
        self._stopped = True

        logger.info("正在停止调度器...")
        self._running = False

        # 取消所有待处理任务
        for task in self._tasks:
            task.cancel()

        # 等待任务完成（异常已处理）
        await asyncio.gather(*self._tasks, return_exceptions=True)

        # 关闭数据库
        await self._db_manager.close()

        # 释放 PID 文件锁
        self._release_pid_lock()

        logger.info("调度器已停止")


async def run_scheduler(replace: bool = False) -> int:
    """运行调度器的入口点。

    Usage:
        python -m galaxy_core.scheduler
        python -m galaxy_core.scheduler --replace
        或: asyncio.run(run_scheduler())

    Returns:
        0 正常退出（含 KeyboardInterrupt），异常时 raise 不返回。
    """
    # 在创建实例之前检查 PID 锁，避免并发 API 登录
    AutoSyncScheduler._acquire_pid_lock(replace=replace)

    scheduler = AutoSyncScheduler()
    try:
        await scheduler.run_forever()
    except KeyboardInterrupt:
        logger.info("收到键盘中断信号")
        await scheduler.stop()
    except Exception as e:
        logger.error(f"调度器错误: {e}")
        await scheduler.stop()
        raise
    return 0
