# Requirements: Galaxy DB Bridge Async Migration

**Defined:** 2026-04-06
**Core Value:** 在不改变现有 CLI 外部行为的前提下，把 K 线同步主链路迁移到 async/await，并保持吞吐与数据正确性。

**Architecture Decision (2026-04-07)**：
- SDK 调用：ThreadPoolExecutor 同步调用，不包装成 async
- 数据库交互：SQLAlchemy async engine，真正的异步 I/O

## v1 Requirements

### Async Foundation

- [x] **ASYNC-01**: AmazingData client 提供 async 包装接口（可选，热路径不使用）
- [x] **ASYNC-02**: 编排层提供 `execute_kline_query_async()` 入口，SDK 用线程池，DB 用 async
- [ ] **ASYNC-03**: 数据库层使用 SQLAlchemy async engine / async session
- [ ] **ASYNC-04**: 异步热路径使用显式数据库依赖注入，替代全局同步 `db_manager`
- [ ] **ASYNC-05**: CLI 入口通过 `asyncio.run()` 驱动异步命令处理

### Compatibility / Reliability

- [x] **COMPAT-01**: 保持现有 CLI 参数、输出摘要和调用方式兼容
- [x] **DATA-01**: 改造后不出现重复写入、丢数据、错误合并或事务一致性回退
- [x] **PERF-01**: 异步实现吞吐不低于当前实现（SDK 线程池 + async 数据库）

### Testing

- [x] **TEST-01**: 为新增 async API / service / orchestrator / CLI 路径补齐单元测试
- [ ] **TEST-02**: 为 async 数据库与端到端同步路径补齐集成测试或验证步骤

## Requirement Entries

### ASYNC-01: Async AmazingData wrappers (optional)
**Source**: `.planning/async-refactoring-plan.md` — Phase 1
**Phase**: 1
**Status**: Complete (可选接口，热路径不使用)
**Description**: 为 `query_kline`、`get_stock_list`、`get_listing_dates` 等同步接口提供 async 对等方法。热路径将使用 ThreadPoolExecutor 直接调用同步方法。

### ASYNC-02: Hybrid orchestrator (threadpool SDK + async DB)
**Source**: Architecture revision 2026-04-07
**Phase**: 2
**Status**: Complete
**Description**: 提供 `execute_kline_query_async()` 编排入口。SDK 批量抓取使用 `ThreadPoolExecutor` 保持性能；数据库查询/保存使用 async 接口。编排层协调两者。
**Resolution**: ThreadPoolExecutor restored for SDK batch fetch (commit 31d350e). Benchmark shows performance within 10ms of baseline. Async entry point provides orchestration capability for Phase 3 database layer.

### ASYNC-03: Async database layer
**Source**: `.planning/async-refactoring-plan.md` — Phase 3
**Phase**: 3
**Status**: Pending
**Description**: 使用 `create_async_engine`、`async_sessionmaker` 与 `AsyncSession` 提供数据库访问能力，并迁移核心服务到 async 版本。

### ASYNC-04: Database dependency injection
**Source**: `.planning/async-refactoring-plan.md` — Eng Review decision
**Phase**: 3
**Status**: Pending
**Description**: 异步路径不再依赖同步全局单例 `db_manager`；通过显式注入数据库管理器，明确连接/会话边界。

### ASYNC-05: Async CLI boundary
**Source**: `.planning/async-refactoring-plan.md` — Phase 4
**Phase**: 4
**Status**: Pending
**Description**: CLI 入口使用 `asyncio.run()` 启动异步命令处理，同时保证外部使用方式与退出码行为不变。

### COMPAT-01: Backward-compatible command behavior
**Source**: `.planning/async-refactoring-plan.md` — Not in Scope / Success Criteria
**Phase**: 1, 4
**Status**: Complete (Phase 1)
**Description**: 保持现有 CLI 参数、输出摘要、错误语义与对外接口兼容，不因为 async 改造引入行为漂移。

### DATA-01: Data integrity parity
**Source**: `.planning/async-refactoring-plan.md` — Success Criteria / Risk Assessment
**Phase**: 2, 3
**Status**: Complete (Phase 2)
**Description**: 保证数据库查询、合并、去重、UPSERT、事务提交/回滚在异步改造后仍与当前行为等价。

### PERF-01: Throughput parity or better
**Source**: `.planning/async-refactoring-plan.md` — Performance Benchmarks
**Phase**: 2, 4
**Status**: Complete (Phase 2)
**Description**: SDK 层使用 ThreadPoolExecutor（恢复 baseline 性能），数据库层使用 async（可能更快）。总体吞吐不低于当前实现。
**Resolution**: Benchmark shows ThreadPoolExecutor restored performance within 10ms of baseline. Phase 2 portion satisfied.

### TEST-01: Async unit coverage
**Source**: `.planning/async-refactoring-plan.md` — Testing Strategy
**Phase**: 1, 2, 3, 4
**Status**: Complete (Phase 1, 2)
**Description**: 为 async 编排、异步服务方法和异步命令入口补齐单元测试。

### TEST-02: Async integration verification
**Source**: `.planning/async-refactoring-plan.md` — Testing Strategy
**Phase**: 3, 4
**Status**: Pending
**Description**: 为 async 数据库驱动和端到端同步链路提供集成测试或等价验证步骤，覆盖真实数据库和主要批量场景。

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ASYNC-01 | Phase 1: Async API Client Wrapper | Complete (optional) |
| ASYNC-02 | Phase 2: Hybrid Orchestrator | Complete (ThreadPoolExecutor SDK + async entry) |
| ASYNC-03 | Phase 3: Async Database Layer | Pending |
| ASYNC-04 | Phase 3: Async Database Layer | Pending |
| ASYNC-05 | Phase 4: Async CLI Entry Point | Pending |
| COMPAT-01 | Phase 1, 4 | Complete (Phase 1) |
| DATA-01 | Phase 2, 3 | Complete (Phase 2) |
| PERF-01 | Phase 2, 4 | Complete (Phase 2) |
| TEST-01 | Phase 1, 2, 3, 4 | Complete (Phase 1, 2) |
| TEST-02 | Phase 3, 4 | Pending |

---
*Requirements defined: 2026-04-06*
*Last updated: 2026-04-07*
*Architecture revised: sync SDK + async DB*
*Phase 2 verified: 2026-04-07*