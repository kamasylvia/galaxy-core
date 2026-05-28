# Phase 1: Async API Client Wrapper - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

重做 `AmazingDataClient` 的 async client 面，把它定义为后续异步改造的主边界。Phase 1 聚焦 client 层本身：统一 async 包装风格、覆盖公开读取接口、锁定测试边界，并为后续 orchestrator / database / CLI phase 提供稳定依赖。

不在本 phase 内推进 orchestrator、数据库层或 CLI 主链路改造。

</domain>

<decisions>
## Implementation Decisions

### Phase boundary
- **D-01:** 本 phase 按“重做 client 面”规划，不把当前已有 async 方法仅视为补洞对象。
- **D-02:** Phase 1 只处理 `AmazingDataClient` 这一层，不把 orchestrator / DB / CLI 异步化混入本 phase。

### Async surface coverage
- **D-03:** Phase 1 的目标是收敛 `AmazingDataClient` 的**全公开读取面**，而不只覆盖 K 线当前主链路。
- **D-04:** 所有公开读取接口都应具备统一风格的 async 对等方法，避免后续 phase 再回头补 client 面。
- **D-05:** `AmazingDataClient` 是调用 AmazingData 同步 SDK 的唯一 async 包装边界；上层不应各自重复 `to_thread` 包装 SDK。

### Testing standard
- **D-06:** 测试按“边界级强化”执行，不满足于仅验证 async 方法能调用成功。
- **D-07:** Phase 1 测试必须明确覆盖 `asyncio.to_thread` 使用、参数透传、可选参数桥接、异常传播和并发不阻塞语义。
- **D-08:** 测试优先锁定 client wrapper 边界，不把本 phase 扩成 orchestrator / CLI 集成测试。

### Compatibility strategy
- **D-09:** Phase 1 采用 **async 优先切换** 策略，而不是长期保持 sync/async 并行对等地位。
- **D-10:** planner 应把同步接口视为过渡兼容层，而不是长期主接口；后续 phase 可以围绕 async client 面直接规划调用方迁移。

### Claude's Discretion
- 哪些公开方法属于“读取面”可在规划时结合 `AmazingDataClient` 现有 public API 精确归类
- async 方法命名保持 `<sync_name>_async` 还是做更激进重整，只要不破坏 Phase 1 已锁定目标
- 测试中对 `asyncio.to_thread` 的断言方式可按 pytest/mock 最稳妥方案决定

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase definition
- `.planning/ROADMAP.md` — 定义 Phase 1 目标、依赖和成功标准
- `.planning/REQUIREMENTS.md` — 定义 ASYNC-01 / COMPAT-01 / TEST-01 等 requirement 映射
- `.planning/PROJECT.md` — 定义整个 async migration 的约束、关键决策和 out-of-scope
- `.planning/async-refactoring-plan.md` — 原始异步改造草案与 phase 分解来源

### Existing implementation
- `src/galaxy_db_sync/amazing_data/api/client.py` — 当前 AmazingData client 的 sync/async API 现状与异常语义
- `tests/amazing_data/test_async_client.py` — 当前 async client 测试覆盖现状

### Project-level instructions
- `CLAUDE.md` — 项目架构、命名约定、测试命令与开发约束

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/galaxy_db_sync/amazing_data/api/client.py`: 已存在 `get_hist_code_list_async`、`get_stock_list_async`、`get_listing_dates_async`、`query_kline_async`，可作为重做 client 面时的起点
- `tests/amazing_data/test_async_client.py`: 已有 async wrapper 测试框架和 pytest-asyncio 用法，可直接扩展
- `src/galaxy_db_sync/shared_kernel/exceptions/*`: 已建立较具体的异常类型体系，Phase 1 可直接复用

### Established Patterns
- client 层已经承担 SDK 包装职责，符合“SDK 边界集中管理”的方向
- 项目内部命名约定要求除 SDK 字面参数 `period` 外统一使用 `interval`
- 现有代码质量方向强调具体异常和明确日志，不鼓励宽泛异常吞并

### Integration Points
- Phase 2 的 `src/galaxy_db_sync/application/kline/sync_orchestrator.py` 将直接消费 Phase 1 产出的 async client 面
- 现有测试目录 `tests/amazing_data/` 是 Phase 1 的主要验证落点
- 任何对 public client 面的重整都将影响后续 orchestrator / command / service 规划

</code_context>

<specifics>
## Specific Ideas

- 用户明确要求：Phase 1 不按“验收+补洞”处理，而按“重做 client 面”规划
- 用户明确要求：覆盖面做到 `AmazingDataClient` 全公开读取面，而不是只围绕 K 线主链路
- 用户明确要求：兼容策略偏向 async 优先切换，而不是长期保留 sync/async 并行主地位

</specifics>

<deferred>
## Deferred Ideas

- orchestrator 的 `asyncio.gather` / `asyncio.Semaphore` 改造 — 属于 Phase 2
- SQLAlchemy async / AsyncDatabaseManager / DI 改造 — 属于 Phase 3
- CLI `asyncio.run()` 入口收口 — 属于 Phase 4

</deferred>

---

*Phase: 01-async-api-client-wrapper*
*Context gathered: 2026-04-06*