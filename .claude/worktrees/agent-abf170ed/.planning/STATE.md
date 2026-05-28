---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Auto Sync Scheduler
status: executing
last_updated: "2026-04-12T23:45:00.000Z"
last_activity: 2026-04-12
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 5
  completed_plans: 4
  percent: 80
---

# Project State

## Project Reference

See: .planning/PROJECT.md (created 2026-04-06)

**Core value:** 在不改变现有 CLI 外部行为的前提下，把 K 线同步主链路迁移到 async/await，并保持吞吐与数据正确性。
**Current focus:** Phase 06 — auto-sync-scheduler

## Current Position

Phase: 06 (auto-sync-scheduler) — EXECUTING
Plan: 5 of 5
Status: Ready to execute
Last activity: 2026-04-12

Progress: [█████████░] 80%

## Final Architecture

**同步 SDK + 异步数据库 + 自定义调度器** 混合架构：

```
CLI Entry Point (asyncio.run)
  ↓
handle_kline_command_async()
  ↓
┌─────────────────────────────────────────────────────────┐
│  SDK Layer: asyncio.to_thread(amazing_data_client.query_kline)
│             ThreadPoolExecutor for concurrent API calls
└─────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────┐
│  Database Layer: async_db_manager.session()             │
│                   await session.execute()                │
│                   AsyncSession + asyncpg driver          │
│                                                          │
│  Services (all async):                                   │
│  - kline_service.query_kline_from_db()                  │
│  - kline_service.save_kline_to_db()                     │
│  - trading_calendar_service.get_trading_days()          │
│  - kline_completeness_checker.check()                   │
│  - kline_data_sync_service.sync_kline_data()            │
└─────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────┐
│  Scheduler Layer (NEW): AutoSyncScheduler               │
│  - Custom asyncio loop (per D-01)                       │
│  - Polls every minute                                   │
│  - K-line sync at 23:00 (per D-02)                      │
│  - Calendar sync at 00:00 (Dec 20)                      │
│  - Retry policy: 3 retries, 5/15/60min (per D-03)      │
└─────────────────────────────────────────────────────────┘
```

## Key Decisions

- D-07: Restore ThreadPoolExecutor for SDK batch fetch to eliminate 30-60ms regression (02-01)
- D-08: Keep execute_kline_query_async() as async entry point for Phase 3 database layer (02-01)
- D-09: CLI command-layer verified compatible with hybrid architecture (02-02)
- D-10: CLI entry uses asyncio.run() to drive async_main() (04-01)
- D-11: Calendar command remains sync, wrapped with asyncio.to_thread (04-01)
- D-12: sync_kline_data_async wraps sync_kline_data with asyncio.to_thread (04-01)
- **D-13**: Convert ALL existing database services to async directly (not create separate async versions) (2026-04-08)
- **D-01** (Phase 6): Custom asyncio loop scheduler (no APScheduler/schedule library)
- **D-02** (Phase 6): Extend IntervalBoundaryChecker with `is_last_trading_day_of_period()`
- **D-03** (Phase 6): Retry 3 times, delays 5/15/60 minutes
- **D-04** (Phase 6): TOML config with `[scheduler]` section
- **D-14** (Phase 6): Mock AmazingData SDK in conftest.py to avoid SDK dependency chain (tgw, toml) in test fixtures (06-00)
- **D-15** (Phase 6): Load Interval enum directly via importlib to bypass package __init__.py imports (06-00)
- **D-16** (Phase 6): SyncState model uses unique index on (sync_type, period_identifier) (06-02)
- **D-17** (Phase 6): SyncStateManager uses PostgreSQL upsert (INSERT ... ON CONFLICT) for mark_running() (06-02)
- **D-18** (Phase 6): RetryPolicy loads from config with fallback defaults (06-02)
- **D-19** (Phase 6): KlineSyncJob syncs periods in order: DAY first, then ascending (06-03)
- **D-20** (Phase 6): Period identifiers use ISO week calendar format for WEEK (YYYY-WNN) (06-03)
- **D-21** (Phase 6): CalendarSyncJob uses config-driven window (Dec 20-31) with force sync on Dec 20 (06-03)

## Files Converted to Async (2026-04-08)

**Database Services (全部改为异步，无同步版本保留):**

- `database/services/kline.py` — KlineService 全异步
- `database/services/kline_query.py` — 查询函数全异步
- `database/services/kline_save.py` — 保存函数全异步
- `database/services/kline_data_sync.py` — 同步服务全异步
- `database/services/empty_query.py` — 空查询缓存全异步
- `database/services/trading_calendar.py` — 交易日历全异步
- `database/services/kline_completeness_checker.py` — 完整性检查全异步

**Application Layer:**

- `application/kline/command.py` — CLI 入口使用 asyncio.run()
- `application/kline/sync_orchestrator.py` — 编排函数全异步
- `application/cleanup/command.py` — 清理命令全异步

**Scheduler Layer (NEW - Phase 6):**

- `application/scheduler/scheduler.py` — 主调度循环
- `application/scheduler/kline_sync_job.py` — K-line 同步作业
- `application/scheduler/calendar_sync_job.py` — 日历同步作业
- `application/scheduler/state_manager.py` — 状态持久化
- `application/scheduler/retry_handler.py` — 重试策略

## Pending Todos

- Execute Phase 6 Plan 04: Main scheduler loop

## Completed

- 06-00: Test infrastructure created - tests/scheduler/ package with fixtures and stubs
- 06-01: Scheduler config + IntervalBoundaryChecker extension (TOML config, async boundary methods)
- 06-02: State persistence + retry handler (SyncState model, SyncStateManager, RetryPolicy)
- 06-03: K-line and calendar sync jobs (KlineSyncJob, CalendarSyncJob with 22 passing tests)

## Blockers / Concerns

- `AmazingData` SDK 仍是同步黑盒，所有 async 收益都来自包装、编排和数据库层

## Next Step

- Run `/gsd:execute-phase 6` to continue with Plan 04 (Main scheduler loop)

---
**Resume point:** Phase 6 Plan 03 complete — continue with `/gsd:execute-phase 6`
**Updated on:** 2026-04-12
