# Galaxy DB Bridge

## What This Is

`galaxy-db-sync` 是一个从银河证券 AmazingData API 拉取行情数据并持久化到 PostgreSQL/TimescaleDB 的数据桥接项目。支持 K 线数据、交易日历、证券基本信息等数据的同步。

## Core Value

提供稳定、高效的数据同步能力，确保 K 线数据完整性与一致性，支持 CLI 交互和调度器自动同步两种模式。

## Current Milestone: v1.1 重构

**Goal:** 规范化项目架构、聚焦日线同步、完善文档与代码质量

**Target features:**
- 规范化 Python 项目文件架构与命名
- kline 指令专注日线同步，移除周线/月线/季线/年线支持
- 重构 kline 缺失数据检测逻辑，最小化 API 调用次数
- 重写 README 与实际代码一致
- 清理 .planning 与实际代码的冲突

**Key context:**
- 父目录为 git 项目，本目录不单独初始化 git
- 异步化与主键重构实际已完成，.planning 文档待同步
- 当前项目架构已具备清晰分层（amazing_data / application / database / shared_kernel）

## Previous Milestones

### v1.4 gRPC Scheduler Control (Previous)
- Phase 6: Auto Sync Scheduler — Complete
- Phase 7: Full Async Database Layer — Complete
- Phase 8: K-line Primary Key Refactoring — Complete
- Phase 9: gRPC Scheduler Control — Not started (deferred)

## Requirements

### Active (v1.1)

- [ ] **ARCH-01**: 规范化项目文件架构与命名，消除不一致的模块组织
- [ ] **ARCH-02**: 统一代码风格与导入规范
- [ ] **KLINE-01**: kline 指令专注日线同步，移除 WEEK/MONTH/SEASON/YEAR 支持
- [ ] **KLINE-02**: 重构缺失数据检测逻辑，最小化 API 调用次数
- [ ] **KLINE-03**: 用户传入 security_type + start + end，自动处理数据完整性
- [ ] **DOC-01**: 重写 README，与实际代码完全一致
- [ ] **DOC-02**: 清理 .planning 文档与实际代码的冲突

### Validated (Previous Milestones)

- [x] **ASYNC-01~05**: 异步改造完成
- [x] **PK-01~08**: K 线表主键重构完成
- [x] **SCHED-01~07**: 自动同步调度器完成

### Out of Scope

| Feature | Reason |
|---------|--------|
| 替换 AmazingData SDK | SDK 是黑盒且已接入 |
| 新增 gRPC Scheduler Control | 本里程碑专注重构与简化，defer 到后续版本 |
| 新增数据源或证券类型 | 超出当前重构范围 |

## Context

**当前代码状态（2026-05-28）：**
- 异步化实际已完成：所有 database/services/ 已使用 async def
- 主键重构实际已完成：BaseKline 使用 (symbol, trade_time) 组合主键
- kline command 仍支持 WEEK/MONTH/SEASON/YEAR，需移除
- README 与实际代码严重不符
- 项目文件架构已具备清晰分层，但部分命名和组织可优化

**约束：**
- 父目录为 git 项目，本目录不单独初始化 git
- 保持 CLI 外部行为稳定（除移除长周期支持外）
- 周期命名仍遵守项目约定：除 SDK 字面参数 `period` 外，内部统一用 `interval`

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

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| D-01: SDK 维持同步黑盒 | 无法改 SDK，只能包装 | 使用 `asyncio.to_thread` 作为统一 async 边界 |
| D-02: 编排层先行异步化 | 能先收敛并发模型，减少线程池逻辑复杂度 | 用 `asyncio.gather` + `asyncio.Semaphore` 替换线程池 |
| D-03: 数据库层采用 AsyncDatabaseManager + DI | 直接在单例上原地改 async 风险高、边界不清 | Phase 3 采用显式依赖注入 |
| D-04: 分四个 phase 渐进交付 | 便于验证、回归和回退 | 每个 phase 可独立落地与验收 |
| D-05: 保持外部接口稳定 | 避免 async 改造影响现有使用者 | 兼容层放在 CLI / service 边界 |
| D-06: 异常处理继续使用具体异常 | 已有代码质量改进方向明确，不回退到宽泛捕获 | async 路径沿用具体异常与日志规则 |

## Evolution

本文件在以下时机更新：
1. 每次 phase 规划完成后，更新 Active requirements 的阶段映射
2. 每次 phase 执行完成后，移动已验证项并补充关键决策
3. 若当前代码状态与规划不一致，以仓库现状为准并回写这里

---
*Created: 2026-04-06*
*Last updated: 2026-04-06*