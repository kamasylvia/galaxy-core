# Phase 10: 代码清理与架构规范化 - Context

**Gathered:** 2026-05-28
**Status:** Ready for planning

## Phase Boundary

移除废弃代码，修复已知问题，改善模块命名与结构。本 phase 不改变 CLI 外部行为，不新增功能。

## Implementation Decisions

### 同步数据库层清理 (ARCH-01 + ARCH-02)
- **D-01:** `database/core/connection.py` 同步连接文件一次性移除
- **D-02:** `database/core/__init__.py` 同步导出（`DatabaseManager`, `db_manager`, `init_database`）全部删除，不再保留兼容层
- **D-03:** 一并清理所有 services 的同步方法，仅保留 async 版本。涉及文件：
  - `database/services/empty_query.py` — 移除 `is_confirmed_empty`, `record_empty_result`, `batch_is_confirmed_empty`, `batch_record_empty_results` 等同步方法
  - `database/services/trading_calendar.py` — 移除同步 session 使用的方法
  - `database/services/missing_data_tracker.py` — 移除同步 session 使用的方法
  - `database/services/kline_completeness_checker.py` — 移除 `check`, `get_missing_dates`, `is_data_complete` 同步方法（ARCH-02）
- **D-04:** `application/calendar/command.py` 和 `application/kline/command.py` 的同步 `db_manager.initialize()` 调用改为 `async_db_manager.initialize()`

### 区间合并工具函数统一 (ARCH-03)
- **D-05:** `_merge_to_ranges`（checker）和 `_merge_dates_to_ranges`（data_sync、trading_calendar）合并为单一实现
- **D-06:** 统一后的函数放到 `shared_kernel/utils/date_range_utils.py` 新模块，作为通用日期范围合并工具

### 模块命名改善 (ARCH-05)
- **D-07:** `database/services/empty_query.py` → `database/services/empty_query_cache.py`
- **D-08:** 类名同步改：`EmptyQueryResultService` → `EmptyQueryCacheService`
- **D-09:** 变量名同步改：`empty_query_service` → `empty_query_cache_service`
- **D-10:** 模型名同步改：`EmptyQueryResult` → `EmptyQueryCache`，表名 `empty_query_results` → `empty_query_caches`
- **D-11:** 表名变更需要 Alembic 迁移脚本

### BatchSyncResult 修复 (ARCH-04)
- **D-12:** 移除 `BatchSyncResult` 重复的 `@dataclass` 装饰器（`database/services/kline_data_sync.py:1227-1228`）

### 未使用代码清理 (ARCH-06)
- **D-13:** 所有被移除同步方法连带清理其未使用的导入

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/ROADMAP.md` §Phase 10 — 阶段目标、成功标准、关键风险
- `.planning/REQUIREMENTS.md` §架构规范化 (ARCH) — ARCH-01~06 具体需求
- `.planning/PROJECT.md` §Current Milestone: v1.1 重构 — 里程碑上下文

### Architecture Decisions
- `.planning/STATE.md` §Key Decisions — D-01~D-36 历史决策（尤其 D-13：所有 services 直接转 async）
- `.planning/STATE.md` §Files Converted to Async — Phase 07 异步化完成文件清单

### Code Structure
- `CLAUDE.md` §Architecture — 项目分层结构、设计模式、数据流

No external specs — requirements fully captured in decisions above.

## Existing Code Insights

### Reusable Assets
- `AsyncDatabaseManager` (`database/core/async_connection.py`): 所有数据库交互的统一异步入口
- `async_db_manager` 单例: 已初始化，替换 `db_manager` 的直接替代
- Alembic 迁移基础设施: 表名变更需要新建迁移脚本

### Established Patterns
- 全异步数据库层: 所有 services 已使用 async def，Phase 10 只是清理残留同步方法
- 单例模式: `db_manager` → `async_db_manager` 替换遵循相同模式
- 工具函数统一放在 `shared_kernel/utils/`: D-06 遵循此模式

### Integration Points
- `application/kline/command.py`: 使用 `db_manager.initialize()` 初始化 → 改为 `async_db_manager.initialize()`
- `application/calendar/command.py`: 同上
- `database/services/kline_data_sync.py`: 引用 `empty_query_service` → 改为 `empty_query_cache_service`
- `application/kline/sync_orchestrator.py`: 同上

## Specific Ideas

- 清理同步方法时，先确认每个同步方法都有对应的 async 版本可用（从调用链验证）
- `date_range_utils.py` 的合并函数应支持两种输入：原始日期列表（data_sync/trading_calendar 用法）和带周期边界映射的日期列表（checker 用法）

## Deferred Ideas

None — discussion stayed within phase scope

---

*Phase: 10-代码清理与架构规范化*
*Context gathered: 2026-05-28*
