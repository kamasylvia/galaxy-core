# Galaxy DB Bridge Async Migration

## What This Is

一个针对 `galaxy-db-sync` 的渐进式异步改造项目：在**不替换 AmazingData SDK**、**不改变现有 CLI 外部用法**的前提下，把 K 线同步主链路逐步迁移到 `async/await`。

## Core Value

提升批量 K 线抓取与落库链路的并发能力，去掉数据库热路径中的阻塞 I/O，同时保持数据完整性、错误语义和现有命令行为稳定。

## Requirements

### Active

- [x] **ASYNC-01**: `AmazingDataClient` 为现有同步接口提供 async 等价包装，并统一使用 `asyncio.to_thread` 调用同步 SDK
- [x] **ASYNC-02**: K 线批量同步编排从 `ThreadPoolExecutor` 迁移到 `asyncio.gather` + `asyncio.Semaphore`
- [x] **ASYNC-03**: 数据库层迁移到 SQLAlchemy async engine / async session
- [x] **ASYNC-04**: 异步热路径不再依赖全局单例 `db_manager`，改为显式依赖注入数据库管理器
- [x] **ASYNC-05**: CLI 入口通过 `asyncio.run()` 驱动异步命令处理链路
- [ ] **ASYNC-06**: 所有数据库交互全异步，禁止异步调用链中使用同步 `db_manager`：
  - `missing_data_tracker.py` — 当前全同步，需异步化
  - `empty_query.py` — 当前全同步，需异步化
  - `trading_calendar.py` — 同步方法需迁移或删除
  - `kline_data_sync.py` — `_group_by_missing_ranges` 内调用同步 `missing_data_tracker`
- [x] **COMPAT-01**: 现有 CLI 参数语义、输出摘要与对外调用方式保持兼容
- [ ] **TEST-01**: 每个 phase 都补齐对应的 async 单元/集成测试
- [x] **PERF-01**: 异步实现的吞吐不低于当前实现，并维持可配置并发限制
- [x] **DATA-01**: 改造后不出现数据重复、漏写、错误合并或事务一致性回退

### Out of Scope

| Feature | Reason |
|---------|--------|
| 替换 AmazingData SDK | SDK 是黑盒且已接入，当前项目只能包装其同步接口 |
| 大爆炸式重写 | 风险过高，不利于逐 phase 验证 |
| 改变 CLI 对外命令格式 | 本项目优先保持现有使用方式稳定 |
| 与 async 无关的性能优化 | 单独议题，不混入本里程碑 |
| 线程安全单例体系的全面重构 | 只处理 async 改造直接相关的数据库管理边界 |

## Context

**当前观察到的代码状态：**
- `src/galaxy_db_sync/amazing_data/api/client.py` 已存在部分 async 包装方法，说明 Phase 1 不是完全从零开始
- `src/galaxy_db_sync/application/kline/sync_orchestrator.py` 仍使用 `ThreadPoolExecutor`、`as_completed` 与 `threading.Semaphore`
- `src/galaxy_db_sync/database/core/connection.py` 仍是同步 `create_engine` + `sessionmaker` + 全局单例 `db_manager`
- `src/galaxy_db_sync/application/cli/commands.py` 与 `src/galaxy_db_sync/application/kline/command.py` 仍是同步 CLI 主流程

**约束：**
- AmazingData SDK 保持同步，只能通过 `asyncio.to_thread` 包装
- 周期命名仍遵守项目约定：除 SDK 字面参数 `period` 外，内部统一用 `interval`
- 改造必须保留完整性检查、空查询缓存、数据库合并与异常语义
- 测试要跟着 phase 走，不接受最后一次性补测

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