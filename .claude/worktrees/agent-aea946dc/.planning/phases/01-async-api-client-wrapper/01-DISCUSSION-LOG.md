# Phase 1: Async API Client Wrapper - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-06
**Phase:** 01-async-api-client-wrapper
**Areas discussed:** Phase 1 边界, 包装覆盖面, 测试强度, 兼容策略

---

## Phase 1 边界

| Option | Description | Selected |
|--------|-------------|----------|
| 验收+补齐 | 按当前仓库现状审计已有 async 包装、补齐缺口和测试 | |
| 重做 client 面 | 把 Phase 1 当作 async client 面重整 phase，而不是补洞 | ✓ |
| 仅最小验收 | 只做最小确认，把缺口留给后续 | |

**User's choice:** 重做 client 面
**Notes:** 用户明确不希望把 Phase 1 限定成“已有实现验收 + 补洞”，而是希望按更完整的 client 层重做来规划。

---

## 包装覆盖面

| Option | Description | Selected |
|--------|-------------|----------|
| 全公开读取面 | AmazingDataClient 的公开同步读取接口都补成统一 async 对等面 | ✓ |
| 仅 K 线相关 | 只覆盖当前 K 线主链路会用到的接口 | |
| 仅核心查询 | 只做 `query_kline*` 等核心查询接口 | |

**User's choice:** 全公开读取面
**Notes:** 用户希望趁 Phase 1 一次把 client 面收敛干净，不把其余读取接口继续留成后债。

---

## 测试强度

| Option | Description | Selected |
|--------|-------------|----------|
| 边界级强化 | 锁定 `to_thread`、参数透传、异常传播、并发不阻塞等 wrapper 边界 | ✓ |
| 轻量补测 | 在现有“调用成功即可”的基础上补一点 case | |
| 接近集成级 | 在 Phase 1 里把 client 层测试做得更接近集成验证 | |

**User's choice:** 边界级强化
**Notes:** 用户希望 Phase 1 把 async client 边界测扎实，好让后续 phase 直接依赖。

---

## 兼容策略

| Option | Description | Selected |
|--------|-------------|----------|
| 保留 sync 并行层 | sync/async 并行存在，后续再逐步迁移调用方 | |
| 开始迁移调用方 | Phase 1 就让一部分调用方偏向 async client | |
| async 优先切换 | 把 async 视为主方向，同步层更多是过渡兼容 | ✓ |

**User's choice:** async 优先切换
**Notes:** 用户不希望 planner 把 sync/async 长期当成并行主地位，而是希望后续 phase 围绕 async 面收口。

---

## Claude's Discretion

- 公开“读取面”方法清单的最终精确定义
- async 方法签名与命名的一致化方式
- `asyncio.to_thread` 的最佳测试断言方案

## Deferred Ideas

- Async orchestrator redesign — Phase 2
- Async database + DI migration — Phase 3
- Async CLI entry point — Phase 4
