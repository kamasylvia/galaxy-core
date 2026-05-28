# Roadmap: Galaxy DB Bridge Async Migration

## Milestones

- **v1.2 Auto Sync Scheduler** — Phase 6 (in progress)

## Architecture Decision

**核心原则**：
- **SDK 调用**：使用 `ThreadPoolExecutor` 同步调用，不包装成 async
- **数据库交互**：使用 SQLAlchemy async engine，真正的异步 I/O
- **调度器**：使用自定义 asyncio 循环，无外部依赖（APScheduler/schedule）

**原因**：
- AmazingData SDK 是同步黑盒，`asyncio.to_thread` 包装会增加调度开销
- 数据库 I/O 是真正的网络/磁盘操作，async 能带来实际收益
- 交易日历触发基于动态计算，APScheduler cron 无法直接表达

```
execute_kline_query_async()
  |
  +- SDK 层：ThreadPoolExecutor.submit(batch_fetch_kline)
  |           +- 直接同步调用 query_kline()
  |
  +- 数据库层：await kline_service.query_kline_from_db_async()
               await kline_service.save_async()
               +- SQLAlchemy AsyncSession
```

## Phases

### v1.2 Auto Sync Scheduler (Phase 6)

### Phase 6: Auto Sync Scheduler
**Goal**: 创建自动同步调度服务，在特定时间自动触发 K 线数据和交易日历的同步

**Depends on**: Phase 4 (async architecture complete)

**Requirements**: SCHED-01, SCHED-02, SCHED-03, SCHED-04, SCHED-05, SCHED-06, SCHED-07

**Plans:** 5 plans (Wave 0 + 4 implementation waves)

Plans:
- [x] 06-00-PLAN.md — Test infrastructure (Wave 0)
- [x] 06-01-PLAN.md — Configuration + IntervalBoundaryChecker extension (Wave 1) — SCHED-02, SCHED-04
- [x] 06-02-PLAN.md — State persistence + retry handler (Wave 2) — SCHED-03, SCHED-05
- [x] 06-03-PLAN.md — K-line and calendar sync jobs (Wave 3) — SCHED-06, SCHED-07
- [ ] 06-04-PLAN.md — Main scheduler loop (Wave 4) — SCHED-01

**Success Criteria**:
- 自定义 asyncio 循环调度器运行（SCHED-01）
- 周期最后交易日检测功能（SCHED-02）
- 重试策略：3次，5/15/60分钟间隔（SCHED-03）
- TOML 配置文件 `[scheduler]` section（SCHED-04）
- 状态持久化防止重复同步（SCHED-05）
- K-line 同步任务（SCHED-06）
- 日历同步任务（SCHED-07）
- 23:00 触发 K-line 同步
- 00:00 触发日历同步（Dec 20）和检查（Dec 20-31）

**Status**: In Progress (4 of 5 plans complete)

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Async API Client Wrapper | v1.0 | 2/2 | Completed | 2026-04-07 |
| 2. Hybrid Orchestrator | v1.0 | 2/2 | Completed | 2026-04-07 |
| 3. Async Database Layer | v1.0 | 3/3 | Completed | 2026-04-08 |
| 4. Async CLI Entry Point | v1.0 | 1/1 | Completed | 2026-04-08 |
| 6. Auto Sync Scheduler | v1.2 | 4/5 | In Progress | 2026-04-12 |

## Rework Resolution (Phase 2)

Phase 2 rework completed successfully:
- **Initial implementation**: `asyncio.to_thread` wrapper over SDK caused 30-60ms performance regression
- **Rework implementation**: ThreadPoolExecutor restored for SDK batch fetch (commit 31d350e)
- **Benchmark result**: Performance within 10ms of baseline -- PERF-01 satisfied
- **Architecture achieved**: SDK uses ThreadPoolExecutor, async entry point for orchestration

---
*Roadmap created: 2026-04-06*
*Last updated: 2026-04-12*
*Phase 6 revised: 2026-04-12 — Added Wave 0, fixed requirement coverage*