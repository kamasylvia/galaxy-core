# Phase 3: Async Database Layer - Research

**Researched:** 2026-04-06
**Domain:** SQLAlchemy async + 数据库依赖注入
**Confidence:** MEDIUM-HIGH

## Summary

Phase 3 是整个 async 改造里风险最高的阶段。当前 `src/galaxy_db_sync/database/core/connection.py` 仍是基于同步 `create_engine`、同步 `sessionmaker` 和全局单例 `db_manager` 的设计；而 command、service、completeness checker 等代码普遍直接导入这个全局单例。要让 async 真正落地，数据库热路径必须改成 async session，同时清掉异步链路中对同步单例的硬依赖。

## Current State

- `DatabaseManager` 仍是单例类，`session()` 是同步 `contextmanager`
- 连接 URL 仍使用 `postgresql://...`，未切到 `postgresql+asyncpg://...`
- 下列服务文件会受影响：
  - `src/galaxy_db_sync/database/core/connection.py`
  - `src/galaxy_db_sync/database/services/kline_query.py`
  - `src/galaxy_db_sync/database/services/kline_save.py`
  - `src/galaxy_db_sync/database/services/kline.py`
  - `src/galaxy_db_sync/database/services/trading_calendar.py`
  - `src/galaxy_db_sync/database/services/kline_completeness_checker.py`
  - `src/galaxy_db_sync/database/services/kline_data_sync.py`
- Eng review 决策已明确推荐：使用 **Dependency Injection Pattern**，不要在 async 化时继续强化全局单例

## Architecture Findings

### Pattern 1: New async manager over in-place mutation
直接把现有 `DatabaseManager` 原地改成 async 会让同步调用方和初始化路径一起震荡。更稳妥的是引入 `AsyncDatabaseManager` 或等价的 async 管理器边界，然后逐步把 async 服务切过去。

### Pattern 2: DI at service boundary
目前多个 service 通过模块级导入直接拿 `db_manager`。异步路径需要把数据库依赖从“隐式全局”改为“显式构造参数”，否则测试、事务边界和多实现共存都会非常难控。

### Pattern 3: Keep transaction semantics explicit
现有同步 `session()` context manager 自动 commit / rollback。async 版本必须保留同样清晰的事务边界，并用测试锁住 commit / rollback 行为。

## Test Requirements

- async session context manager 的 commit / rollback 行为
- query/save/completeness/trading calendar 关键服务的 async 路径
- 与真实数据库或等价集成环境的 async driver 验证
- 兼容层是否还能服务同步调用方（若保留）

## Key Decisions

- **Decision 1:** Phase 3 采用 DI，而不是让 async 路径继续直接 import 全局 `db_manager`
  - **Rationale:** 这是 eng review 已确认的待落地决策
- **Decision 2:** 把数据库改造视为独立高风险 phase
  - **Rationale:** 影响面跨 core + services + command/orchestrator
- **Decision 3:** 事务行为必须先被测试锁住，再迁移更多服务
  - **Rationale:** 数据正确性是这里的首要验收标准

## Failure Modes

- async engine 引入后连接池配置不当，导致连接耗尽或行为漂移
- 事务提交/回滚行为与同步版本不一致
- 某些 service 混用 sync/async session，导致隐蔽错误
- 保留全局 `db_manager` 直连 async path，导致边界仍然混乱

## Patterns to Follow

- 用 `create_async_engine` + `async_sessionmaker` + `asynccontextmanager`
- 先迁移底层 session 获取方式，再迁移 query/save/completeness 具体服务
- 对外通过构造函数或显式参数传入 database manager，不用模块级隐式依赖

## Files of Interest

- `src/galaxy_db_sync/database/core/connection.py`
- `src/galaxy_db_sync/database/services/kline_query.py`
- `src/galaxy_db_sync/database/services/kline_save.py`
- `src/galaxy_db_sync/database/services/kline.py`
- `src/galaxy_db_sync/database/services/trading_calendar.py`
- `src/galaxy_db_sync/database/services/kline_completeness_checker.py`
- `src/galaxy_db_sync/database/services/kline_data_sync.py`

## Recommended Planning Focus

1. 定义 async manager / session 边界
2. 确定 DI 注入点与同步兼容策略
3. 优先迁移 query/save/completeness 热路径
4. 用事务与集成测试兜底
