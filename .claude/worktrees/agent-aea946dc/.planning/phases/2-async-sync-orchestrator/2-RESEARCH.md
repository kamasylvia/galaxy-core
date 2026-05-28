# Phase 2: Async Sync Orchestrator - Research

**Researched:** 2026-04-06
**Domain:** K 线同步编排层异步化
**Confidence:** HIGH

## Summary

`src/galaxy_db_sync/application/kline/sync_orchestrator.py` 仍然是当前 async 改造的核心缺口。这个文件明确使用 `ThreadPoolExecutor`、`as_completed` 和 `threading.Semaphore` 实现并发抓取；同时它还负责缺失区间分组、失败代码收集、DataFrame 合并去重和 API 查询封装。Phase 2 的目标不是简单把线程池语法换成 `asyncio.gather`，而是要在**保持这些业务语义一致**的前提下，把热路径迁移为原生 async 编排。

## Current State

- `batch_fetch_kline_data()` 使用 `ThreadPoolExecutor(max_workers=max_workers)`
- `fetch_single_batch()` 使用 `threading.Semaphore`
- `execute_kline_query()` 仍是同步入口，依赖同步数据库查询后再走线程池 API 查询
- 该模块已经依赖：
  - 缺失区间分组 `group_symbols_by_missing_ranges()`
  - 空查询缓存 `empty_query_service`
  - 结果封装 `KlineQueryResult` / `KlineItemResult` / `KlineSyncResult`

## Architecture Findings

### Pattern 1: Preserve business grouping, swap concurrency primitive
缺失区间分组和空结果短路逻辑已经是稳定业务规则。Phase 2 只应替换并发执行模型，不应重写分组规则。

### Pattern 2: Async orchestration should sit above async client
新的 orchestrator 应消费 Phase 1 提供的 `AmazingDataClient.*_async` 方法，而不是继续在线程池任务中调用同步 API。

### Pattern 3: DataFrame merge path remains synchronous CPU-side logic
DataFrame 合并/去重/排序本质上是本地 CPU 与内存操作，不需要为此强行引入额外 async 抽象。异步化重点应放在 I/O 边界。

## Test Requirements

- 覆盖成功批次、部分失败批次、全部失败批次
- 覆盖多缺失区间分组后的 gather 聚合与失败代码收集
- 覆盖重复 symbol DataFrame 合并去重逻辑不回退
- 覆盖 semaphore 并发限制仍可配置
- 验证不再依赖 `ThreadPoolExecutor` / `as_completed`

## Key Decisions

- **Decision 1:** 保留 `group_symbols_by_missing_ranges()` 业务逻辑，只替换执行模型
  - **Rationale:** 业务规则已稳定，风险集中在并发模型替换即可
- **Decision 2:** DataFrame merge 逻辑继续保留在 orchestrator 层
  - **Rationale:** 这部分是结果编排责任，不需要提前拆分
- **Decision 3:** 为异步编排提供新入口，再决定是否保留同步兼容壳
  - **Rationale:** CLI 与程序内兼容调用方仍可能需要渐进切换

## Failure Modes

- `asyncio.gather(return_exceptions=True)` 下遗漏异常归集，导致失败代码收集退化
- 忘记在 async path 中使用 semaphore，导致并发失控
- DataFrame 合并顺序变化引入重复记录或排序回退
- 新 orchestrator 继续偷偷调用同步 SDK / 同步 DB，导致“伪异步”

## Patterns to Follow

- 为单批次抓取提供 `fetch_single_batch_async()`，用 `async with` 风格的并发门控
- 用 gather 后统一归集成功/失败结果，保持现有 `failed_codes` 语义
- 让同步兼容入口尽量薄，只负责桥接到 async 主实现

## Files of Interest

- `src/galaxy_db_sync/application/kline/sync_orchestrator.py`
- `src/galaxy_db_sync/application/kline/command.py`
- `src/galaxy_db_sync/database/services/kline.py`
- `src/galaxy_db_sync/database/services/empty_query.py`

## Recommended Planning Focus

1. 引入 `fetch_single_batch_async()` / `batch_fetch_kline_data_async()`
2. 将 API 抓取切到 Phase 1 async client
3. 保留现有分组、去重、合并语义
4. 用测试锁定失败收集和去重行为
