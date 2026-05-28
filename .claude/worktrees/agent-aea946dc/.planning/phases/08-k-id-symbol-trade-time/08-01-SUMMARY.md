---
phase: 08-k-id-symbol-trade-time
plan: 01
subsystem: database
 tags:
  - primary-key
  - composite-key
  - sqlalchemy
  - timescaledb
  - async
requires:
  - 07-full-async-database-layer
provides:
  - composite-primary-key-models
  - async-hypertable-creation
affects:
  - database-models
  - database-services
  - database-core
key-files:
  created: []
  modified:
    - src/galaxy_db_sync/database/models/kline.py
    - src/galaxy_db_sync/database/services/kline.py
    - src/galaxy_db_sync/database/core/timescale.py
    - src/galaxy_db_sync/database/core/connection.py
    - tests/integration/test_timescale_integration.py
decisions:
  - D-03: Remove redundant indexes since composite primary key provides (symbol, trade_time) index
  - D-01: Convert create_hypertable to async to align with Phase 7 async database layer
metrics:
  duration: 5m58s
  completed_date: "2026-04-23T16:29:31Z"
  tasks_completed: 5
  files_modified: 5
  commits: 5
---

# Phase 08 Plan 01: 修改 ORM 模型定义使用组合主键 Summary

**One-liner:** 将 BaseKline 从自增 id 主键改为 (symbol, trade_time) 组合主键，移除 13 个子类的冗余索引，修复 model.id 引用，并将 create_hypertable 同步函数迁移为 AsyncSession 异步版本。

## What Was Built

### 1. BaseKline 组合主键 (Task 1)
- 删除 `id: Mapped[int]` 自增主键列
- `symbol` 列添加 `primary_key=True`
- `trade_time` 列添加 `primary_key=True`，移除 `index=True`（主键自动创建索引）
- 更新类文档字符串，说明组合主键设计

### 2. 13 个 K 线表子类清理 (Task 2)
- 移除所有子类的 `__table_args__`（包含 `UniqueConstraint` 和 `Index`）
- 从 imports 中移除未使用的 `Index`, `Integer`, `UniqueConstraint`
- 组合主键天然提供 `(symbol, trade_time)` 唯一索引，无需额外约束

### 3. model.id 引用修复 (Task 3)
- `kline.py:295` `func.count(model.id)` 改为 `func.count()`
- 使用列无关计数，更健壮

### 4. create_hypertable 异步化 (Task 4)
- 函数签名从 `Session` 改为 `AsyncSession`
- 所有 `session.execute()` / `session.commit()` / `session.rollback()` 添加 `await`
- `create_kline_hypertables()` 改为异步，接受 `AsyncSession` 参数
- 移除对全局同步 `db_manager` 单例的依赖

### 5. 同步调用者适配 (Task 5 — Deviation Rule 3)
- `connection.py`: 从 `create_tables()` 中移除同步 hypertable 创建调用，记录提示使用异步版本
- `test_timescale_integration.py`: 重写为异步版本，使用 `async_db_manager` 和 `create_kline_hypertables(session)`

## Commits

| Hash | Type | Message |
|------|------|---------|
| 5afbd39 | feat | modify BaseKline to use composite primary key (symbol, trade_time) |
| c21ef80 | feat | remove redundant indexes and UniqueConstraint from 13 kline subclasses |
| bb4ef26 | fix | replace func.count(model.id) with func.count() in kline service |
| e4c71a5 | feat | convert create_hypertable to async version with AsyncSession |
| 44ae4cb | fix | adapt sync callers to async create_hypertable API |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] 同步调用者适配**
- **Found during:** Task 4 完成后验证
- **Issue:** `create_hypertable` 改为异步后，`connection.py:100` 的同步调用 `create_kline_hypertables()` 和 `tests/integration/test_timescale_integration.py:22` 的同步调用会崩溃
- **Fix:**
  - `connection.py`: 移除同步 hypertable 创建，添加日志提示使用异步版本
  - `test_timescale_integration.py`: 完全重写为异步测试，使用 `async_db_manager` 和 `asyncio.run()`
- **Files modified:** `src/galaxy_db_sync/database/core/connection.py`, `tests/integration/test_timescale_integration.py`
- **Commit:** 44ae4cb

## Verification Results

| Check | Status | Command |
|-------|--------|---------|
| kline.py syntax | PASS | `python -m py_compile` |
| kline service syntax | PASS | `python -m py_compile` |
| timescale.py syntax | PASS | `python -m py_compile` |
| connection.py syntax | PASS | `python -m py_compile` |
| test_timescale_integration.py syntax | PASS | `python -m py_compile` |
| id column removed | PASS | `grep "id: Mapped\[int\]"` returns empty |
| composite primary key | PASS | `symbol` and `trade_time` both have `primary_key=True` |
| model.id removed | PASS | `grep "model\.id"` returns empty |
| async create_hypertable | PASS | `async def create_hypertable` exists |
| redundant constraints removed | PASS | `UniqueConstraint` and `Index(` not found in subclasses |

## Known Stubs

None — all changes are structural model and API updates with no placeholder data.

## Threat Flags

None — this plan only modifies ORM model definitions and internal API signatures. No new network endpoints, auth paths, or trust boundaries introduced.

## Self-Check: PASSED

- [x] `src/galaxy_db_sync/database/models/kline.py` exists and modified
- [x] `src/galaxy_db_sync/database/services/kline.py` exists and modified
- [x] `src/galaxy_db_sync/database/core/timescale.py` exists and modified
- [x] `src/galaxy_db_sync/database/core/connection.py` exists and modified
- [x] `tests/integration/test_timescale_integration.py` exists and modified
- [x] All 5 commits verified in git log
- [x] All syntax checks pass
- [x] SUMMARY.md committed
