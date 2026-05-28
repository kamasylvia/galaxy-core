---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: K-line Primary Key Refactoring
status: Phase 08 executing — 重构 K 线表主键
last_updated: "2026-04-24T00:17:00.000Z"
last_activity: 2026-04-24
progress:
  total_phases: 3
  completed_phases: 2
  total_plans: 3
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (created 2026-04-06)

**Core value:** 在不改变现有 CLI 外部行为的前提下，把 K 线同步主链路迁移到 async/await，并保持吞吐与数据正确性。
**Current focus:** Milestone v1.3 完成 — 数据库全异步改造

## Current Position

Phase: 08 (Executing)
Plan: Wave 3 — 08-03 创建单元测试和集成测试
Status: 重构 K 线表主键：将自增 id 改为 (symbol, trade_time) 组合主键
Last activity: 2026-04-24

Progress: [████████░░░░] 67% (Waves 1-2 complete, Wave 3 executing)

## Final Architecture

**同步 SDK + 异步数据库 + 自定义调度器 + 完整性检查** 混合架构：

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
│  Scheduler Layer: AutoSyncScheduler                      │
│  - Custom asyncio loop (per D-01)                       │
│  - Polls every minute                                   │
│  - K-line sync at 23:00 (per D-02)                      │
│  - Calendar sync at 00:00 (Dec 20)                      │
│  - Retry policy: 3 retries, 5/15/60min (per D-03)      │
│  - Completeness check at 17:00 (trading days, D-19)    │
│  - Post-sync verification (D-19)                        │
└─────────────────────────────────────────────────────────┘
```

## K-line Query Workflow

K线查询的完整流程（7 步）：

1. **用户发起查询或自动查询触发** — CLI 命令或 Scheduler 定时任务
2. **从数据库获取K线数据** — `KlineService.query_kline_from_db()`
3. **数据连续性检查** — 因为数据库只有交易日数据，需验证连续性
4. **交易日历比对** — 获取交易日历，按周期计算应参照的连续交易周期日期，与数据库数据比对，确认数据完整性
5. **空查询缓存检查** — 如有数据缺失，检查 `empty_query_result` 表：
   - 已登记 → 之前 API 查询返回空，不再重复调用
   - 未登记 → 标记为需要 API 查询
6. **API 查询真正缺失数据** — 只对通过步骤 3+5 检查的缺失区间调用 API：
   - 返回空 → 登记到空查询缓存表
   - 有数据 → 合并到同步列表
7. **数据同步到数据库** — `KlineService.save_kline_to_db()`

## Accumulated Context

### Roadmap Evolution

- Phase 8 added: 重构 K 线表主键：将自增 id 改为 (symbol, trade_time) 组合主键 (2026-04-23)

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
- **D-14** (Phase 6): Mock AmazingData SDK in conftest.py to avoid SDK dependency chain (06-00)
- **D-15** (Phase 6): Load Interval enum directly via importlib to bypass package __init__.py imports (06-00)
- **D-16** (Phase 6): SyncState model uses unique index on (sync_type, period_identifier) (06-02)
- **D-17** (Phase 6): SyncStateManager uses PostgreSQL upsert for mark_running() (06-02)
- **D-18** (Phase 6): RetryPolicy loads from config with fallback defaults (06-02)
- **D-19** (Phase 6): KlineSyncJob syncs periods in order: DAY first, then ascending (06-03)
- **D-20** (Phase 6): Period identifiers use ISO week calendar format for WEEK (06-03)
- **D-21** (Phase 6): CalendarSyncJob uses config-driven window (Dec 20-31) with force sync on Dec 20 (06-03)
- **D-22** (Phase 6): Custom asyncio loop without APScheduler/schedule library per SCHED-01 (06-04)
- **D-23** (Phase 6): Sleep to next minute boundary prevents clock drift (06-04)
- **D-24** (Phase 6): K-line sync at 23:00, calendar sync at 00:00 via config-driven triggers (06-04)
- **D-25** (Phase 6): Task naming pattern: kline_sync_{date}, calendar_sync_{date} (06-04)
- **D-26** (Phase 6): stop() cancels pending tasks and closes database connection (06-04)
- **D-27** (Phase 6 扩展): 双触发机制 — 交易日 17:00 + 同步完成后验证 (06-05)
- **D-28** (Phase 6 扩展): 检查范围由 `[scheduler.check_intervals]` 配置指定 (06-05)
- **D-29** (Phase 6 扩展): 发现缺失后自动触发补同步，复用 KlineSyncJob 逻辑 (06-05)
- **D-30** (Phase 6 扩展): 新建 `completeness_check_log` 表记录检查详情 (06-05)
- **D-31** (2026-04-16): 月线/季线/周线完整性检查改用周期标识比较而非具体日期，避免因 trade_time 存储格式不匹配导致的误判
- **D-32** (2026-04-16): 日志精简 — `missing_data_tracker` INFO 改为 DEBUG，避免批量同步时日志泛滥
- **D-33** (2026-04-17): API 调用次数优化 — 使用完整日期范围分组而非精确缺失区间，减少调用次数（~200 → ~3）
- **D-34** (2026-04-17): 日志目录清理 — enable_separate_log_files 模式下按 backup_count 天数清理旧目录
- **D-35** (2026-04-17): 开发环境配置 — GALAXY_CONFIG_ENV=dev 加载 settings.dev.toml，支持 30 分钟自动同步
- **D-36** (2026-04-17): 移除 SYNCED 标记 — 同步成功后不标记整个范围为 SYNCED，因为 API 可能只返回部分数据，需让完整性检查每次重新计算

## Files Converted to Async

### Phase 07 异步化完成：

**Database Services:**

- `database/services/kline.py` — KlineService 全异步 ✓
- `database/services/kline_data_sync.py` — 批量同步服务全异步 ✓
- `database/services/kline_completeness_checker.py` — 完整性检查全异步 ✓
- `database/services/completeness_check_log_manager.py` — 检查日志管理全异步 ✓
- `database/services/missing_data_tracker.py` — 缺失数据追踪异步化 ✓ (Phase 07-01)
- `database/services/empty_query.py` — 空查询缓存异步化 ✓ (Phase 07-02)

**Application Layer:**

- `application/kline/command.py` — CLI 入口使用 asyncio.run() ✓
- `application/kline/sync_orchestrator.py` — 编排函数全异步 ✓

**Scheduler Layer:**

- `application/scheduler/scheduler.py` — 主调度循环 ✓
- `application/scheduler/kline_sync_job.py` — K-line 同步作业 ✓
- `application/scheduler/calendar_sync_job.py` — 日历同步作业 ✓
- `application/scheduler/state_manager.py` — 状态持久化全异步 ✓
- `application/scheduler/completeness_check_job.py` — 完整性检查作业 ✓

## Completed

- 06-00: Test infrastructure created - tests/scheduler/ package with fixtures and stubs
- 06-01: Scheduler config + IntervalBoundaryChecker extension (TOML config, async boundary methods)
- 06-02: State persistence + retry handler (SyncState model, SyncStateManager, RetryPolicy)
- 06-03: K-line and calendar sync jobs (KlineSyncJob, CalendarSyncJob)
- 06-04: Main scheduler loop (AutoSyncScheduler, run_scheduler)
- **06-05 (扩展):** CompletenessCheckJob + completeness_check_log 数据库表
- **06-06 (扩展):** Scheduler config extension + 集成完整性检查到调度器循环
- **07-01:** MissingDataTracker 异步化 — 6 个异步方法 ✓
- **07-02:** EmptyQuery 异步化 + kline_data_sync 调用链修正 ✓
- **07-03:** 清理同步方法 + 测试覆盖 ✓

## Phase 08 In Progress

**08-k-id-symbol-trade-time:** 重构 K 线表主键：将自增 id 改为 (symbol, trade_time) 组合主键

- [x] **08-01:** 修改 ORM 模型定义，使用组合主键 (Wave 1) — Complete
- [x] **08-02:** 创建迁移脚本和回滚脚本 (Wave 2) — Complete
- [ ] **08-03:** 创建单元测试和集成测试 (Wave 3) — Executing

## Blockers / Concerns

- `AmazingData` SDK 仍是同步黑盒，所有 async 收益都来自包装、编排和数据库层

---
**Resume point:** Milestone v1.3 complete — Full Async Database Layer
**Updated on:** 2026-04-17
