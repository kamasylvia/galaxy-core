# Roadmap: Galaxy DB Bridge Async Migration

## Milestones

- **v1.3 Full Async Database Layer** — Phase 7 (completed)

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
  +- 数据库层：await kline_service.query_kline_from_db()
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
- [x] 06-04-PLAN.md — Main scheduler loop (Wave 4) — SCHED-01

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

**Status**: Complete (all 5 plans executed)

### v1.3 Full Async Database Layer (Phase 7)

### Phase 7: Full Async Database Layer
**Goal**: 完成数据库全异步改造，消除异步调用链中的同步阻塞点

**Depends on**: Phase 6 (scheduler complete)

**Requirements**: ASYNC-06

**Problem**: 异步路径中仍存在同步 `db_manager` 调用，阻塞并发：

```
CLI (async) → handle_kline_command_async → batch_sync_kline_data_async
  → _group_by_missing_ranges → missing_data_tracker (同步阻塞!)
```

**Blockers**:
| 服务文件 | 当前状态 | 问题 | 优先级 |
|---------|---------|-----|--------|
| `missing_data_tracker.py` | 全同步 | `_group_by_missing_ranges` 在异步 batch_sync 中调用 | HIGH |
| `empty_query.py` | 全同步 | 空查询缓存检查和记录 | MEDIUM |
| `trading_calendar.py` | 混合 | 同步方法仍在使用 | LOW |
| `kline_completeness_checker.py` sync check() | 混合 | 同步版本使用 `db_manager.get_session()` | LOW |

**Plans:** 3 plans (3 implementation waves)

Plans:
/- [x] 07-01-PLAN.md — MissingDataTracker async methods (Wave 1) — HIGH priority blocker ✓
/- [x] 07-02-PLAN.md — EmptyQuery async + kline_data_sync call chain fix (Wave 2) — MEDIUM priority ✓
- [x] 07-03-PLAN.md — Cleanup sync usage + test coverage (Wave 3) — LOW priority ✓
- [ ] 07-03-PLAN.md — Cleanup sync usage + test coverage (Wave 3) — LOW priority

**Success Criteria**:
- `missing_data_tracker.py` 全异步化（6 个异步方法）
- `empty_query.py` 全异步化（2 个异步方法）
- `kline_data_sync.py` 调用链修正（无同步阻塞）
- 清理所有同步 `db_manager` 在异步路径的使用
- 异步路径测试覆盖
- API 调用次数优化（完整日期范围分组）
- 日志目录清理（按天数保留）
- 开发环境配置（GALAXY_CONFIG_ENV）

**Status**: Completed (2026-04-17)

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Async API Client Wrapper | v1.0 | 2/2 | Completed | 2026-04-07 |
| 2. Hybrid Orchestrator | v1.0 | 2/2 | Completed | 2026-04-07 |
| 3. Async Database Layer | v1.0 | 3/3 | Completed | 2026-04-08 |
| 4. Async CLI Entry Point | v1.0 | 1/1 | Completed | 2026-04-08 |
| 6. Auto Sync Scheduler | v1.2 | 5/5 | Completed | 2026-04-12 |
| 7. Full Async Database Layer | v1.3 | 3/3 | Completed | 2026-04-17 |

## Rework Resolution (Phase 2)

Phase 2 rework completed successfully:
- **Initial implementation**: `asyncio.to_thread` wrapper over SDK caused 30-60ms performance regression
- **Rework implementation**: ThreadPoolExecutor restored for SDK batch fetch (commit 31d350e)
- **Benchmark result**: Performance within 10ms of baseline -- PERF-01 satisfied
- **Architecture achieved**: SDK uses ThreadPoolExecutor, async entry point for orchestration

### Phase 8: 重构 K 线表主键：将自增 id 改为 (symbol, trade_time) 组合主键

**Goal:** 将 13 个 K 线表的主键从自增 id 改为 (symbol, trade_time) 组合主键，移除冗余索引
**Requirements**: PK-01, PK-02, PK-03, PK-04, PK-05, PK-06, PK-07, PK-08
**Depends on:** Phase 7
**Plans:** 3 plans

Plans:
- [ ] 08-01-PLAN.md — 修改 ORM 模型定义，使用组合主键
- [ ] 08-02-PLAN.md — 创建迁移脚本和回滚脚本
- [ ] 08-03-PLAN.md — 创建单元测试和集成测试

**Success Criteria**:
- BaseKline 使用 (symbol, trade_time) 组合主键
- 13 个 K 线表子类继承组合主键结构
- 移除冗余的 UniqueConstraint 和 Index
- kline.py 中 model.id 引用已修复
- 迁移脚本支持备份-删除-重建-恢复流程
- 回滚脚本可从备份恢复原始表结构
- 迁移后数据完整性验证通过
- 迁移后 hypertable 功能正常
- UPSERT 行为不变

**Status**: Planned (ready for execution)

---
*Roadmap created: 2026-04-06*
*Last updated: 2026-04-16*
*Phase 7 plans added: 2026-04-16 — Full Async Database Layer (ASYNC-06)*
