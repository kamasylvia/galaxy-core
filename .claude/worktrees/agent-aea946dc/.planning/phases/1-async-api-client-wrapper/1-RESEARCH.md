# Phase 1: Async API Client Wrapper - Research

**Researched:** 2026-04-06
**Domain:** AmazingData 同步 SDK 的 async 包装层
**Confidence:** HIGH

## Summary

Phase 1 不是从零开始：`src/galaxy_db_sync/amazing_data/api/client.py` 已经存在 `get_hist_code_list_async`、`get_stock_list_async`、`get_listing_dates_async`、`query_kline_async` 等 async 包装方法。这个 phase 的重点不应再是“新增 async 方法”，而是**验收并补齐边界**：确认所有关键同步 SDK 入口都有对应 async 包装、统一使用 `asyncio.to_thread`、错误语义与参数约定保持一致，并补齐缺失测试。

这意味着 Phase 1 更像一个 audit + hardening phase。后续 Phase 2 的异步编排会直接依赖这里的 async client 边界，因此这里必须先把 API surface 收敛稳定。

## Current State

- `src/galaxy_db_sync/amazing_data/api/client.py` 已导入 `asyncio`
- 当前文件已存在以下 async 方法：
  - `get_hist_code_list_async`
  - `get_stock_list_async`
  - `get_listing_dates_async`
  - `query_kline_async`
- 当前客户端仍保留同步单例模式与同步初始化/登出逻辑
- 同步异常处理已经过代码质量改进，已引入 `SDKError`、`APIConnectionError`、`APITimeoutError`

## Architecture Findings

### Pattern 1: Sync SDK behind async wrapper
AmazingData SDK 仍必须通过同步方法调用。异步边界应统一收敛在 client 层，并使用 `asyncio.to_thread(...)` 将同步 I/O 放到线程中执行，禁止在 orchestrator 或 command 层自己重复包装 SDK。

### Pattern 2: Keep sync and async surfaces parallel
当前代码已经同时暴露 sync/async 版本。Phase 1 应保持这种并行结构，避免为了 async 改造提前破坏同步调用方。

### Pattern 3: Preserve interval naming rule
项目约定要求内部统一使用 `interval`，只有最终调 SDK 的字面参数才使用 `period`。async 包装必须沿用同样规则，不引入新的 `period` 外泄。

## Test Requirements

- 为现有 async client 方法补齐单元测试，至少覆盖：
  - 调用是否经过 `asyncio.to_thread`
  - 参数是否原样透传到同步方法
  - 同步方法抛出的具体异常是否按现有语义传播
- 验证 `query_kline_async` 对 `interval`/SDK `period` 的桥接不回退到硬编码值
- 若还有缺失的核心 sync 方法没有 async 对等版本，需要在本 phase 补齐并测试

## Key Decisions

- **Decision 1:** Phase 1 按“验收已有 async wrapper + 补齐缺口”处理，而不是视为全新实现
  - **Rationale:** 代码现状已经有部分实现，规划必须贴近仓库实际状态
- **Decision 2:** 所有 SDK async 包装都必须集中在 `AmazingDataClient`
  - **Rationale:** 避免上层重复包装导致边界分散和异常语义漂移
- **Decision 3:** 同步接口暂时保留
  - **Rationale:** 后续 phase 仍需渐进迁移，兼容边界不能提前收缩

## Failure Modes

- 在事件循环里直接调用同步 SDK，导致 async 编排表面异步、实际阻塞
- async 方法参数透传不完整，尤其是 `query_kline_async` 的 interval/time 参数
- async 包装有覆盖不全的 SDK 入口，后续 Phase 2/4 只能回退到同步 client
- 测试只验证 happy path，未覆盖异常传播与参数桥接

## Patterns to Follow

- 用 `await asyncio.to_thread(self.sync_method, ...)` 包装，不在 async 方法内复制同步逻辑
- 让 async 方法复用同步方法的现有异常处理与参数约定
- 用 `AsyncMock` / patch 验证 wrapper 行为，而不是碰真实 SDK

## Files of Interest

- `src/galaxy_db_sync/amazing_data/api/client.py`
- `src/galaxy_db_sync/application/kline/sync_orchestrator.py`
- `tests/` 下与 AmazingData client 相关的单元测试文件（待 Phase 1 规划时精确定位）

## Recommended Planning Focus

1. 先盘点当前 async client surface 与 sync public API 是否一致
2. 补齐缺失 async 方法或统一实现风格
3. 增加针对 `to_thread` 包装、参数透传、异常传播的测试
4. 验证后将该层视为 Phase 2 的稳定依赖
