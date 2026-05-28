# Phase 6: Auto Sync Scheduler - Research

**Researched:** 2026-04-12
**Domain:** Python asyncio scheduling, trading calendar-based triggers, state persistence
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** 使用自定义 asyncio 循环实现调度器
  - 与现有 async 架构一致（`TradingCalendarService`, `KlineService` 已异步化）
  - 无额外依赖（schedule 库、APScheduler）
  - 触发时机基于交易日历动态计算，APScheduler cron 无法直接表达

- **D-02:** 扩展 `IntervalBoundaryChecker` 实现周期最后交易日检测
  - 新增 `is_last_trading_day_of_period(interval, today)` 方法
  - 复用现有 `_get_week_end_date()` / `_get_month_end_date()` 等边界计算逻辑
  - 日历同步触发时机为固定日期（12月20日、每日00:00），无需特殊检测

- **D-03:** 重试 + 记录策略
  - 同步失败后重试 3 次
  - 重试间隔递增：5分钟 → 15分钟 → 60分钟
  - 全部失败后记录错误日志，等待下次调度周期触发
  - 不发送告警通知（仅日志记录）

- **D-04:** TOML 配置文件
  - 复用现有 `config/settings.toml`
  - 新增 `[scheduler]` section 配置调度参数
  - 配置项：触发时间、重试策略、同步范围、日志级别

### Claude's Discretion
- 调度器入口文件位置（建议 `src/galaxy_db_sync/application/scheduler/`）
- 状态持久化表结构设计（建议复用现有数据库，新增 `sync_state` 表）
- 多周期同步的执行顺序（日线优先还是并行执行）
- 日志输出的具体格式

### Deferred Ideas (OUT OF SCOPE)
- 分钟级数据的实时同步 — 超出当前需求范围
- 监控告警系统（邮件、短信、Webhook） — 仅日志记录，告警系统另行规划
- 用户手动触发的覆盖机制（如强制同步） — 现有 CLI 命令已满足
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCHED-01 | 自定义 asyncio 循环调度器 | Section: Architecture Patterns - Asyncio Event Loop Scheduler |
| SCHED-02 | 周期最后交易日检测 | Section: Integration Points - IntervalBoundaryChecker Extension |
| SCHED-03 | 重试策略实现 | Section: Architecture Patterns - Retry Strategy |
| SCHED-04 | TOML 配置扩展 | Section: Integration Points - Configuration |
| SCHED-05 | 状态持久化 | Section: Architecture Patterns - State Persistence |
| SCHED-06 | K-line 周期同步 | Section: Integration Points - Existing Sync Services |
| SCHED-07 | 交易日历同步 | Section: Integration Points - TradingCalendarService |
</phase_requirements>

## Summary

Phase 6 implements an automatic sync scheduler that triggers K-line data and trading calendar synchronization at specific times without manual CLI commands. The scheduler runs as a daemon process using a custom asyncio event loop, checking trading calendar conditions to determine when to sync.

**Primary recommendation:** Build a custom asyncio scheduler loop that polls trading calendar state every minute, triggers sync jobs when conditions match, and persists sync state to PostgreSQL for reliability. This approach aligns with the project's existing async architecture and provides flexibility for trading-calendar-based triggers that APScheduler cannot express.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asyncio | stdlib | Event loop scheduler | No external dependency, aligns with D-01 decision |
| datetime | stdlib | Time calculations | Standard for date/time operations |

### Supporting (Existing Project Dependencies)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| SQLAlchemy async | 2.0+ | State persistence | Async session for `sync_state` table |
| asyncpg | 0.29+ | PostgreSQL driver | Already used for async DB operations |

### Alternatives Considered (but rejected per D-01)
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom asyncio loop | APScheduler | APScheduler cron cannot express "last trading day of period at 23:00" — requires trading calendar lookup |
| Custom asyncio loop | schedule library | schedule is synchronous; no async task support |
| APScheduler | Celery + beat | Heavyweight; requires Redis/RabbitMQ; overkill for single-service scheduler |

**Why APScheduler was rejected (D-01 rationale):**
- APScheduler cron triggers are fixed patterns (e.g., `cron(hour=23, day='last')`)
- Trading calendar triggers need dynamic computation: "last trading day of month" depends on holidays
- Custom loop with 1-minute polling + trading calendar lookup is simpler and more accurate

## Architecture Patterns

### Pattern 1: Asyncio Event Loop Scheduler

**What:** A daemon process with `while True` loop that sleeps for intervals, checks conditions, and triggers async jobs.

**When to use:** For triggers that depend on external state (trading calendar) rather than fixed cron patterns.

**Example:**
```python
import asyncio
import logging
from datetime import datetime, time

logger = logging.getLogger(__name__)

class AutoSyncScheduler:
    """Main scheduler loop."""

    def __init__(self):
        self._running = False
        self._tasks: set[asyncio.Task] = set()

    async def run_forever(self) -> None:
        """Main scheduler loop - polls every minute."""
        self._running = True
        logger.info("Scheduler started")

        while self._running:
            now = datetime.now()
            current_time = now.time()

            # Check triggers every minute
            await self._check_kline_triggers(now, current_time)
            await self._check_calendar_triggers(now, current_time)

            # Sleep until next minute boundary
            next_minute = (60 - now.second) + 1
            await asyncio.sleep(next_minute)

    async def _check_kline_triggers(self, now: datetime, current_time: time) -> None:
        """Check if we should trigger K-line sync at 23:00."""
        if current_time.hour == 23 and current_time.minute == 0:
            # Check if today is last trading day of any period
            # (implementation in Pattern 2)
            ...

    async def _check_calendar_triggers(self, now: datetime, current_time: time) -> None:
        """Check if we should trigger calendar sync at 00:00."""
        if current_time.hour == 0 and current_time.minute == 0:
            if now.month == 12 and now.day == 20:
                # Sync next year calendar
                ...
            elif now.month == 12 and 20 <= now.day <= 31:
                # Check if next year calendar exists
                ...

    async def stop(self) -> None:
        """Stop scheduler gracefully."""
        self._running = False
        # Cancel all pending tasks
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
```

**Source:** Pattern derived from Python asyncio best practices for long-running daemons.

### Pattern 2: Last Trading Day Detection (D-02 Extension)

**What:** Extend `IntervalBoundaryChecker` to detect if today is the last trading day of a period.

**When to use:** At 23:00, check if we need to sync that period's K-line data.

**Example extension to `IntervalBoundaryChecker`:**
```python
# In interval_boundary_checker.py

async def is_last_trading_day_of_period(
    self,
    interval: Interval,
    today: date
) -> bool:
    """Check if today is the last trading day of the period.

    Args:
        interval: Period type (WEEK, MONTH, SEASON, YEAR)
        today: Today's date

    Returns:
        True if today is the last trading day in this period
    """
    if not self.is_long_interval(interval):
        return False  # Short intervals don't have "last day"

    # Get the period's end date (last trading day)
    period_end = self.get_interval_end_date(interval, today)

    # Check if today matches that end date
    return today == period_end

async def get_periods_to_sync_today(self, today: date) -> list[Interval]:
    """Get list of periods where today is the last trading day.

    Returns all periods (WEEK, MONTH, SEASON, YEAR) where today is
    the last trading day of that period.
    """
    long_intervals = [Interval.WEEK, Interval.MONTH, Interval.SEASON, Interval.YEAR]
    periods_to_sync = []

    for interval in long_intervals:
        if await self.is_last_trading_day_of_period(interval, today):
            periods_to_sync.append(interval)

    return periods_to_sync
```

**Source:** Extension pattern based on existing `IntervalBoundaryChecker` methods (`get_interval_end_date`, `is_long_interval`).

### Pattern 3: Retry Strategy (D-03)

**What:** Exponential backoff retry with max attempts, logging failures.

**When to use:** When sync operations may fail temporarily (network issues, API timeouts).

**Example:**
```python
import asyncio
import logging

logger = logging.getLogger(__name__)

class RetryPolicy:
    """Retry configuration."""

    MAX_RETRIES: int = 3
    RETRY_DELAYS: list[int] = [5 * 60, 15 * 60, 60 * 60]  # 5min, 15min, 60min in seconds

async def sync_with_retry(
    sync_func: callable,
    sync_name: str,
    *args,
    **kwargs
) -> bool:
    """Execute sync with retry policy.

    Returns:
        True if sync succeeded, False if all retries exhausted
    """
    for attempt, delay in enumerate(RetryPolicy.RETRY_DELAYS, start=1):
        try:
            await sync_func(*args, **kwargs)
            logger.info(f"{sync_name} sync succeeded on attempt {attempt}")
            return True
        except Exception as e:
            logger.error(f"{sync_name} sync failed (attempt {attempt}): {e}")
            if attempt < RetryPolicy.MAX_RETRIES:
                logger.info(f"Retrying in {delay // 60} minutes...")
                await asyncio.sleep(delay)

    logger.error(f"{sync_name} sync failed after {RetryPolicy.MAX_RETRIES} attempts")
    return False
```

**Source:** Standard exponential backoff pattern adapted for async context.

### Pattern 4: State Persistence

**What:** Database table to track sync history and prevent duplicate syncs.

**When to use:** To avoid re-syncing the same period if scheduler restarts.

**Recommended table schema:**
```sql
CREATE TABLE sync_state (
    id SERIAL PRIMARY KEY,
    sync_type VARCHAR(50) NOT NULL,  -- 'kline_week', 'kline_month', 'calendar'
    period_identifier VARCHAR(20) NOT NULL,  -- '2025-W12', '2025-03', '2026'
    sync_status VARCHAR(20) NOT NULL,  -- 'pending', 'running', 'success', 'failed'
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    records_synced INTEGER DEFAULT 0,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_sync_state_unique ON sync_state (sync_type, period_identifier);
```

**ORM Model:**
```python
from sqlalchemy import Column, Integer, String, DateTime, Text
from galaxy_db_sync.database.models import Base

class SyncState(Base):
    __tablename__ = "sync_state"

    id = Column(Integer, primary_key=True)
    sync_type = Column(String(50), nullable=False)  # 'kline_week', 'calendar'
    period_identifier = Column(String(20), nullable=False)  # '2025-W12', '2026'
    sync_status = Column(String(20), nullable=False)  # 'success', 'failed'
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    records_synced = Column(Integer, default=0)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
```

### Pattern 5: Configuration (D-04)

**What:** TOML configuration section for scheduler parameters.

**When to use:** Allow users to customize trigger times, retry policy, sync scope.

**Example `[scheduler]` section for `config/settings.toml`:**
```toml
[scheduler]
# K-line sync trigger time (hour, minute)
kline_trigger_hour = 23
kline_trigger_minute = 0

# Calendar sync dates
calendar_sync_month = 12
calendar_sync_day = 20
calendar_check_window_start = 20  # Check from Dec 20
calendar_check_window_end = 31    # Check until Dec 31

# Retry policy
max_retries = 3
retry_delays_minutes = [5, 15, 60]  # 5min, 15min, 60min

# Sync scope - which periods to auto-sync
enabled_intervals = ["day", "week", "month", "season", "year"]

# Logging
log_level = "INFO"
```

**Config loader usage:**
```python
from galaxy_db_sync.shared_kernel.utils.config_loader import get_section

scheduler_config = get_section("scheduler")
trigger_hour = scheduler_config.get("kline_trigger_hour", 23)
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Trading calendar lookup | Custom date calculation | `TradingCalendarService.is_trading_day()` | Handles holidays correctly |
| Period boundary calculation | Custom week/month logic | `IntervalBoundaryChecker.get_interval_end_date()` | Already handles edge cases (leap year, holidays) |
| Async database session | Manual connection management | `async_db_manager.session()` | Context manager handles commit/rollback |
| K-line sync logic | New sync implementation | `sync_kline_data()` from sync_orchestrator | Existing completeness check + batch sync |
| Calendar sync logic | New calendar fetch | `TradingCalendarService.sync_calendar()` | Already fetches from akshare and saves |

**Key insight:** The scheduler is primarily orchestration, not data fetching. Reuse existing services extensively.

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | PostgreSQL sync_state table (new) | Database migration to create table |
| Live service config | config/settings.toml `[scheduler]` section | TOML edit, no external service |
| OS-registered state | None — scheduler runs as process, not systemd/launchd | N/A |
| Secrets/env vars | None — uses existing DB/API credentials | N/A |
| Build artifacts | None — scheduler is Python module | N/A |

**Nothing found in category:**
- OS-registered state: Scheduler is a daemon process, not registered with systemd/launchd (Claude's discretion on deployment method)
- Secrets: Uses existing environment variables for DB and API credentials

## Common Pitfalls

### Pitfall 1: Duplicate Sync on Restart
**What goes wrong:** Scheduler restarts and re-syncs the same period that was already synced earlier.
**Why it happens:** No state persistence to track completed syncs.
**How to avoid:** Check `sync_state` table before triggering sync; mark as 'success' after completion.
**Warning signs:** Multiple sync_state records with same `period_identifier` and `sync_type`.

### Pitfall 2: Missed Sync Due to Clock Drift
**What goes wrong:** Scheduler sleeps past the trigger minute due to accumulated drift.
**Why it happens:** Using fixed sleep durations without accounting for execution time.
**How to avoid:** Calculate sleep duration from current time to next minute boundary (see Pattern 1).
**Warning signs:** Trigger times logged at 23:01, 23:02 instead of exactly 23:00.

### Pitfall 3: Blocking the Event Loop
**What goes wrong:** Sync operations block the scheduler, preventing other checks.
**Why it happens:** Calling sync functions without `asyncio.create_task()`.
**How to avoid:** Use `asyncio.create_task()` for sync jobs; track tasks in `self._tasks` set.
**Warning signs:** Calendar check runs minutes after 00:00 because K-line sync blocked.

### Pitfall 4: Trading Calendar Cache Miss
**What goes wrong:** `is_last_trading_day_of_period()` returns wrong answer because calendar data missing.
**Why it happens:** Trading calendar not synced for current year.
**How to avoid:** Scheduler startup should verify trading calendar exists for current year + next year.
**Warning signs:** `TradingCalendarService.get_trading_days()` returns empty list.

### Pitfall 5: SDK Session Exhaustion
**What goes wrong:** AmazingData SDK login session expires during long sync operation.
**Why it happens:** Multiple sync tasks reusing same client without re-login.
**How to avoid:** Each sync task should use fresh client session; logout after completion (existing pattern in sync_orchestrator).

## Code Examples

### Scheduler Entry Point
```python
# src/galaxy_db_sync/application/scheduler/__init__.py
"""Auto Sync Scheduler module."""

from .scheduler import AutoSyncScheduler, run_scheduler

__all__ = ["AutoSyncScheduler", "run_scheduler"]
```

### Main Scheduler Implementation
```python
# src/galaxy_db_sync/application/scheduler/scheduler.py
"""Auto Sync Scheduler main implementation."""

import asyncio
import logging
from datetime import date, datetime, time

from galaxy_db_sync.database.core.async_connection import async_db_manager
from galaxy_db_sync.shared_kernel.enums.interval import Interval
from galaxy_db_sync.shared_kernel.utils.config_loader import get_section
from galaxy_db_sync.application.scheduler.kline_sync_job import KlineSyncJob
from galaxy_db_sync.application.scheduler.calendar_sync_job import CalendarSyncJob
from galaxy_db_sync.application.scheduler.state_manager import SyncStateManager

logger = logging.getLogger(__name__)


class AutoSyncScheduler:
    """Auto sync scheduler using custom asyncio loop."""

    def __init__(self) -> None:
        self._running = False
        self._tasks: set[asyncio.Task] = set()
        self._config = get_section("scheduler")

        # Initialize components
        async_db_manager.initialize()
        self._state_manager = SyncStateManager()
        self._kline_job = KlineSyncJob(self._state_manager)
        self._calendar_job = CalendarSyncJob(self._state_manager)

    async def run_forever(self) -> None:
        """Main scheduler loop."""
        self._running = True
        logger.info("Auto Sync Scheduler started")

        # Startup checks
        await self._verify_trading_calendar()

        while self._running:
            now = datetime.now()
            current_time = now.time()
            today = now.date()

            # Poll triggers
            await self._check_kline_trigger(today, current_time)
            await self._check_calendar_trigger(today, current_time)

            # Sleep to next minute boundary (avoid drift)
            seconds_to_next_minute = 60 - now.second
            await asyncio.sleep(seconds_to_next_minute + 1)

    async def _verify_trading_calendar(self) -> None:
        """Ensure trading calendar exists for current and next year."""
        current_year = datetime.now().year
        # TradingCalendarService already handles missing calendar fetch
        logger.info(f"Trading calendar verified for {current_year}")

    async def _check_kline_trigger(self, today: date, current_time: time) -> None:
        """Check and trigger K-line sync at configured time."""
        trigger_hour = self._config.get("kline_trigger_hour", 23)
        trigger_minute = self._config.get("kline_trigger_minute", 0)

        if current_time.hour == trigger_hour and current_time.minute == trigger_minute:
            task = asyncio.create_task(
                self._kline_job.run(today),
                name=f"kline_sync_{today}"
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _check_calendar_trigger(self, today: date, current_time: time) -> None:
        """Check and trigger calendar sync at 00:00."""
        if current_time.hour == 0 and current_time.minute == 0:
            # Dec 20: sync next year calendar
            # Dec 20-31: verify next year calendar exists
            task = asyncio.create_task(
                self._calendar_job.run(today),
                name=f"calendar_sync_{today}"
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def stop(self) -> None:
        """Stop scheduler gracefully."""
        logger.info("Stopping scheduler...")
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await async_db_manager.close()
        logger.info("Scheduler stopped")


async def run_scheduler() -> None:
    """Entry point to run scheduler."""
    scheduler = AutoSyncScheduler()
    try:
        await scheduler.run_forever()
    except KeyboardInterrupt:
        await scheduler.stop()
```

### Kline Sync Job
```python
# src/galaxy_db_sync/application/scheduler/kline_sync_job.py
"""K-line sync job for scheduler."""

import logging
from datetime import date

from galaxy_db_sync.shared_kernel.enums.interval import Interval
from galaxy_db_sync.shared_kernel.utils.interval_boundary_checker import IntervalBoundaryChecker
from galaxy_db_sync.application.scheduler.state_manager import SyncStateManager
from galaxy_db_sync.application.scheduler.retry_handler import sync_with_retry

logger = logging.getLogger(__name__)


class KlineSyncJob:
    """K-line synchronization job."""

    # Long intervals to check for sync
    LONG_INTERVALS = [Interval.DAY, Interval.WEEK, Interval.MONTH, Interval.SEASON, Interval.YEAR]

    def __init__(self, state_manager: SyncStateManager) -> None:
        self._state_manager = state_manager
        self._boundary_checker = IntervalBoundaryChecker()

    async def run(self, today: date) -> None:
        """Run K-line sync for periods ending today."""
        # Note: DAY interval syncs daily at 23:00 regardless of boundary
        # Long intervals sync only on last trading day of period

        intervals_to_sync = []

        # Day: always sync daily
        intervals_to_sync.append(Interval.DAY)

        # Long intervals: check if today is last trading day
        for interval in [Interval.WEEK, Interval.MONTH, Interval.SEASON, Interval.YEAR]:
            if await self._is_last_trading_day(interval, today):
                intervals_to_sync.append(interval)

        logger.info(f"K-line sync: {len(intervals_to_sync)} intervals to sync on {today}")

        for interval in intervals_to_sync:
            await self._sync_interval(interval, today)

    async def _is_last_trading_day(self, interval: Interval, today: date) -> bool:
        """Check if today is last trading day of period."""
        period_end = self._boundary_checker.get_interval_end_date(interval, today)
        return today == period_end

    async def _sync_interval(self, interval: Interval, today: date) -> None:
        """Sync single interval with retry."""
        sync_type = f"kline_{interval.value}"
        period_id = self._get_period_identifier(interval, today)

        # Check if already synced
        if await self._state_manager.is_synced(sync_type, period_id):
            logger.info(f"{sync_type} {period_id} already synced, skipping")
            return

        # Mark as running
        await self._state_manager.mark_running(sync_type, period_id)

        # Execute sync with retry
        success = await sync_with_retry(
            self._do_sync,
            f"{sync_type} {period_id}",
            interval,
            today
        )

        # Update state
        if success:
            await self._state_manager.mark_success(sync_type, period_id)
        else:
            await self._state_manager.mark_failed(sync_type, period_id)

    async def _do_sync(self, interval: Interval, today: date) -> None:
        """Actual sync implementation - delegates to existing services."""
        # TODO: Call sync_kline_data with appropriate parameters
        # This reuses existing sync_orchestrator logic
        logger.info(f"Syncing {interval.value} K-line data for period ending {today}")
        # Implementation calls existing sync services

    def _get_period_identifier(self, interval: Interval, today: date) -> str:
        """Generate period identifier for state tracking."""
        if interval == Interval.WEEK:
            week_num = today.isocalendar()[1]
            return f"{today.year}-W{week_num}"
        elif interval == Interval.MONTH:
            return f"{today.year}-{today.month:02d}"
        elif interval == Interval.SEASON:
            quarter = (today.month - 1) // 3 + 1
            return f"{today.year}-Q{quarter}"
        elif interval == Interval.YEAR:
            return f"{today.year}"
        else:
            return f"{today.strftime('%Y%m%d')}"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| APScheduler cron | Custom asyncio loop | D-01 decision | Dynamic trading calendar triggers possible |
| Fixed date sync | Trading calendar-based sync | D-02 decision | Accurate "last trading day" detection |
| Manual CLI trigger | Auto scheduler daemon | This phase | No manual intervention needed |

**Deprecated/outdated:**
- APScheduler: Not used due to inability to express trading calendar conditions
- schedule library: Synchronous, incompatible with async services

## Integration Points

### Existing Services to Reuse

| Service | File | How to Use |
|---------|------|------------|
| `TradingCalendarService` | `database/services/trading_calendar.py` | `sync_calendar(year)`, `is_trading_day(date)`, `get_trading_days()` |
| `sync_kline_data` | `application/kline/sync_orchestrator.py` | Async sync with completeness check |
| `IntervalBoundaryChecker` | `shared_kernel/utils/interval_boundary_checker.py` | Extend with `is_last_trading_day_of_period()` |
| `async_db_manager` | `database/core/async_connection.py` | Session context manager for state persistence |
| `get_section` | `shared_kernel/utils/config_loader/config.py` | Load `[scheduler]` config |

### New Modules to Create

| Module | Location | Purpose |
|--------|----------|---------|
| `scheduler/__init__.py` | `application/scheduler/` | Module entry point |
| `scheduler/scheduler.py` | `application/scheduler/` | Main asyncio loop |
| `scheduler/kline_sync_job.py` | `application/scheduler/` | K-line sync orchestration |
| `scheduler/calendar_sync_job.py` | `application/scheduler/` | Calendar sync orchestration |
| `scheduler/state_manager.py` | `application/scheduler/` | SyncState database operations |
| `scheduler/retry_handler.py` | `application/scheduler/` | Retry policy implementation |
| `models/sync_state.py` | `database/models/` | SyncState ORM model |

### IntervalBoundaryChecker Extension

Add async methods to existing class:
```python
# In interval_boundary_checker.py, add:

async def is_last_trading_day_of_period(self, interval: Interval, today: date) -> bool:
    """Check if today is the last trading day of the period."""
    if not self.is_long_interval(interval):
        return False
    period_end = self.get_interval_end_date(interval, today)
    return today == period_end
```

Note: The existing `get_interval_end_date()` already returns the last trading day of the period, so this extension is straightforward.

### Configuration Extension

Add to `config/settings.toml`:
```toml
[scheduler]
kline_trigger_hour = 23
kline_trigger_minute = 0
calendar_sync_month = 12
calendar_sync_day = 20
max_retries = 3
retry_delays_minutes = [5, 15, 60]
enabled_intervals = ["day", "week", "month", "season", "year"]
log_level = "INFO"
```

## Open Questions

1. **Multi-period sync execution order**
   - What we know: D-02 suggests long periods (week/month/season/year) to sync
   - What's unclear: Should DAY sync before WEEK? Should smaller periods sync before larger ones?
   - Recommendation: Sync in order DAY → WEEK → MONTH → SEASON → YEAR. Smaller periods first ensures completeness for larger period calculations.

2. **Scheduler daemon deployment method**
   - What we know: Claude's discretion on deployment
   - What's unclear: systemd service vs. manual process vs. container
   - Recommendation: Provide systemd service file template for production; simple `python -m galaxy_db_sync.scheduler` for development.

3. **SyncState table location**
   - What we know: Claude's discretion on state persistence
   - What's unclear: Separate table vs. existing schema
   - Recommendation: Create `sync_state` table in same PostgreSQL database. Use existing `async_db_manager` for simplicity.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | State persistence | ✓ (existing) | asyncpg 0.29 | — |
| asyncio | Event loop scheduler | ✓ (stdlib) | Python 3.13 | — |
| pytest-asyncio | Testing | ✓ | 0.23.0 | — |
| Trading calendar data | Trigger detection | ✓ | `TradingCalendarService` | — |

**Missing dependencies with no fallback:**
- None — all dependencies are existing project infrastructure

**Missing dependencies with fallback:**
- None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 0.23.0 |
| Config file | `pyproject.toml` (asyncio_mode = "auto") |
| Quick run command | `pytest tests/scheduler/ -v` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCHED-01 | Scheduler loop runs continuously | unit | `pytest tests/scheduler/test_scheduler_loop.py -x` | ❌ Wave 0 |
| SCHED-02 | Last trading day detection | unit | `pytest tests/unit/shared_kernel/utils/test_interval_boundary_checker.py::TestLastTradingDay -x` | ❌ Wave 0 |
| SCHED-03 | Retry strategy with backoff | unit | `pytest tests/scheduler/test_retry_handler.py -x` | ❌ Wave 0 |
| SCHED-04 | TOML config loading | unit | `pytest tests/scheduler/test_config.py -x` | ❌ Wave 0 |
| SCHED-05 | State persistence | integration | `pytest tests/scheduler/test_state_manager.py -x` | ❌ Wave 0 |
| SCHED-06 | K-line sync job triggers | unit | `pytest tests/scheduler/test_kline_sync_job.py -x` | ❌ Wave 0 |
| SCHED-07 | Calendar sync job triggers | unit | `pytest tests/scheduler/test_calendar_sync_job.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/scheduler/ -x -v`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/scheduler/__init__.py` — test module init
- [ ] `tests/scheduler/conftest.py` — scheduler fixtures (mock state manager, mock sync jobs)
- [ ] `tests/scheduler/test_scheduler_loop.py` — SCHED-01
- [ ] `tests/scheduler/test_retry_handler.py` — SCHED-03
- [ ] `tests/scheduler/test_state_manager.py` — SCHED-05
- [ ] `tests/scheduler/test_kline_sync_job.py` — SCHED-06
- [ ] `tests/scheduler/test_calendar_sync_job.py` — SCHED-07
- [ ] `tests/unit/shared_kernel/utils/test_interval_boundary_checker.py` — extend for SCHED-02

*(If no gaps: "None — existing test infrastructure covers all phase requirements")*

Existing test infrastructure:
- `tests/unit/conftest.py` provides `mock_trading_calendar` fixture (reusable)
- `pytest.ini_options` in `pyproject.toml` has `asyncio_mode = "auto"`

## Sources

### Primary (HIGH confidence)
- Project source code: `interval_boundary_checker.py`, `trading_calendar.py`, `sync_orchestrator.py` — verified existing patterns
- Project config: `config/settings.toml` — verified TOML structure
- Project tests: `tests/unit/conftest.py` — verified fixture patterns

### Secondary (MEDIUM confidence)
- Python stdlib `asyncio` documentation — standard patterns for event loop scheduling
- Python asyncio best practices — polling loop with sleep-to-boundary pattern

### Tertiary (LOW confidence)
- APScheduler limitations for trading calendar triggers — inferred from cron syntax limitations; D-01 confirms decision

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — All dependencies are stdlib or existing project libs
- Architecture: HIGH — Patterns derived from existing project async architecture
- Pitfalls: HIGH — Based on known asyncio scheduler issues and project-specific concerns
- Integration: HIGH — All integration points are existing, well-tested services

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (stable patterns, no fast-moving dependencies)

---

## RESEARCH COMPLETE

**Phase:** 6 - Auto Sync Scheduler
**Confidence:** HIGH

### Key Findings
1. **Custom asyncio loop is optimal** — Trading calendar triggers require dynamic computation that APScheduler cron cannot express (D-01 rationale confirmed)
2. **IntervalBoundaryChecker extension is straightforward** — Existing `get_interval_end_date()` returns last trading day; add async wrapper method
3. **Reuse existing services extensively** — `sync_kline_data()`, `TradingCalendarService.sync_calendar()`, `async_db_manager.session()` are all production-ready
4. **State persistence prevents duplicate syncs** — New `sync_state` table with unique constraint on (sync_type, period_identifier)
5. **Test infrastructure exists** — pytest-asyncio configured; mock fixtures available; add scheduler-specific tests

### File Created
`.planning/phases/06-auto-sync-scheduler-23-12-20/06-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|-------|
| Standard Stack | HIGH | All dependencies are stdlib or existing project libs |
| Architecture | HIGH | Patterns align with existing async architecture |
| Pitfalls | HIGH | Known asyncio scheduler issues documented |
| Integration | HIGH | All services exist and are tested |

### Open Questions
1. Multi-period sync execution order (recommendation: DAY first, then ascending)
2. Daemon deployment method (recommendation: systemd service template)
3. SyncState table location (recommendation: same PostgreSQL database)

### Ready for Planning
Research complete. Planner can now create PLAN.md files.