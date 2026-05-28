# Phase 10: 代码清理与架构规范化 - Research

**Researched:** 2026-05-28
**Domain:** Python codebase refactoring, sync-to-async cleanup, module renaming
**Confidence:** HIGH

## Summary

This phase removes legacy synchronous database layer code, fixes known issues, and improves module naming consistency. All changes are internal refactoring with no external CLI behavior changes.

The codebase has a clear pattern: every service has both sync and async method pairs. The async versions are already used by the scheduler, CLI (via `asyncio.run`), and orchestrator. The sync versions are dead code that only remain because they were kept during the Phase 07 async migration. Removing them is safe once callers are verified.

**Primary recommendation:** Execute changes in dependency order: (1) fix callers that still use sync methods, (2) remove sync methods from services, (3) remove `connection.py`, (4) merge utility functions, (5) rename `empty_query` module, (6) clean orphaned imports.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Database connection mgmt | Database Layer (`database/core/`) | — | Singleton pattern, owned by core |
| K-line completeness check | Database Services (`database/services/`) | Application (`application/kline/`) | Checker is a service; CLI/orchestrator are consumers |
| Empty query caching | Database Services (`database/services/`) | — | Data access layer concern |
| Trading calendar | Database Services (`database/services/`) | — | Data access + akshare fetch |
| Missing data tracking | Database Services (`database/services/`) | — | Data access layer concern |
| Date range merging | Shared Utilities (`shared_kernel/utils/`) | — | Pure function, domain-agnostic |
| CLI command handling | Application Layer (`application/cli/`, `application/kline/`) | — | Entry points, thin wrappers |
| Scheduler jobs | Application Layer (`application/scheduler/`) | Database Services | Orchestrates service calls |

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** `database/core/connection.py` 同步连接文件一次性移除
- **D-02:** `database/core/__init__.py` 同步导出（`DatabaseManager`, `db_manager`, `init_database`）全部删除，不再保留兼容层
- **D-03:** 一并清理所有 services 的同步方法，仅保留 async 版本。涉及文件：
  - `database/services/empty_query.py` — 移除 `is_confirmed_empty`, `record_empty_result`, `batch_is_confirmed_empty`, `batch_record_empty_results` 等同步方法
  - `database/services/trading_calendar.py` — 移除同步 session 使用的方法
  - `database/services/missing_data_tracker.py` — 移除同步 session 使用的方法
  - `database/services/kline_completeness_checker.py` — 移除 `check`, `get_missing_dates`, `is_data_complete` 同步方法（ARCH-02）
- **D-04:** `application/calendar/command.py` 和 `application/kline/command.py` 的同步 `db_manager.initialize()` 调用改为 `async_db_manager.initialize()`
- **D-05:** `_merge_to_ranges`（checker）和 `_merge_dates_to_ranges`（data_sync、trading_calendar）合并为单一实现
- **D-06:** 统一后的函数放到 `shared_kernel/utils/date_range_utils.py` 新模块
- **D-07:** `database/services/empty_query.py` → `database/services/empty_query_cache.py`
- **D-08:** 类名同步改：`EmptyQueryResultService` → `EmptyQueryCacheService`
- **D-09:** 变量名同步改：`empty_query_service` → `empty_query_cache_service`
- **D-10:** 模型名同步改：`EmptyQueryResult` → `EmptyQueryCache`，表名 `empty_query_results` → `empty_query_caches`
- **D-11:** 表名变更需要 Alembic 迁移脚本
- **D-12:** 移除 `BatchSyncResult` 重复的 `@dataclass` 装饰器
- **D-13:** 所有被移除同步方法连带清理其未使用的导入

### Claude's Discretion
- None — all decisions are locked.

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ARCH-01 | 移除废弃的同步数据库连接文件 `database/core/connection.py` | Verified: 7 files import from `connection.py`; all have async alternatives. See ARCH-01 section. |
| ARCH-02 | 清理 `kline_completeness_checker.py` 中的同步方法 | Verified: 4 sync methods found; all callers have async equivalents. See ARCH-02 section. |
| ARCH-03 | 合并重复的区间合并工具函数 | Verified: 3 implementations across 2 files; unified signature determined. See ARCH-03 section. |
| ARCH-04 | 修复 `BatchSyncResult` 重复 `@dataclass` 装饰器 | Verified: lines 1227-1228 in `kline_data_sync.py`. Trivial fix. |
| ARCH-05 | 改善模块命名一致性（`empty_query.py` → `empty_query_cache.py`） | Verified: 15+ references across src/ and tests/. See ARCH-05 section. |
| ARCH-06 | 检查并移除未使用的导入和代码 | Verified: orphaned imports identified per ARCH-01~05 changes. See ARCH-06 section. |

---

## ARCH-01: Remove database/core/connection.py

### Files Importing from `connection.py`

| # | File | Line | Import | Action |
|---|------|------|--------|--------|
| 1 | `src/galaxy_db_sync/__init__.py` | 19 | `DatabaseManager, db_manager, init_database` | Remove exports |
| 2 | `src/galaxy_db_sync/database/core/__init__.py` | 6 | `DatabaseManager, db_manager, init_database` | Remove exports |
| 3 | `src/galaxy_db_sync/database/services/empty_query.py` | 10 | `db_manager` | Remove import (sync methods removed in ARCH-02/05) |
| 4 | `src/galaxy_db_sync/database/services/trading_calendar.py` | 12 | `db_manager` | Remove import (sync methods removed) |
| 5 | `src/galaxy_db_sync/database/services/missing_data_tracker.py` | 12 | `db_manager` | Remove import (sync methods removed) |
| 6 | `src/galaxy_db_sync/database/services/kline_completeness_checker.py` | 17 | `db_manager` | Remove import (sync methods removed in ARCH-02) |
| 7 | `src/galaxy_db_sync/application/kline/command.py` | 13 | `db_manager` | Remove import; replace `db_manager.initialize()` calls |
| 8 | `src/galaxy_db_sync/application/calendar/command.py` | 6 | `db_manager` | Remove import; replace `db_manager.initialize()` call |

### `db_manager` Usage Points to Replace

**In `application/kline/command.py`:**
- Line 47: `db_manager.initialize()` in `KLineCommandService.__init__()` — **SURPRISE:** `KLineCommandService` is a legacy sync compatibility class. The `handle_kline_command` (sync) at line 148, 202 also calls `db_manager.initialize()`. The async version `handle_kline_command_async` at lines 451-452, 506-507 calls BOTH `async_db_manager.initialize()` AND `db_manager.initialize()`.
- **Decision:** Remove `KLineCommandService` class entirely (lines 38-104) — it is not used by CLI (which uses `handle_kline_command_async`). Verify no other callers exist.
- **Decision:** In `handle_kline_command_async`, remove the `db_manager.initialize()` calls at lines 452 and 507, keeping only `async_db_manager.initialize()`.
- **Decision:** `handle_kline_command` (sync, lines 107-312) calls `kline_completeness_checker.check()` (sync) and `sync_kline_data()` (sync). Since CLI now uses `handle_kline_command_async` exclusively (via `commands.py:207`), the entire sync `handle_kline_command` function can be removed IF tests don't need it. **CRITICAL:** Tests in `tests/kline/test_kline_command.py` directly call `handle_kline_command` (sync) — see test analysis below.

**In `application/calendar/command.py`:**
- Line 66: `db_manager.initialize()` — Replace with `async_db_manager.initialize()`. Note: `handle_calendar_command` is called via `asyncio.to_thread` from `commands.py:210`, so it runs in a thread. However, `async_db_manager.initialize()` is synchronous initialization of the async engine — it can be called from a thread. Alternatively, initialize before calling `handle_calendar_command`.

### Test Files Using `db_manager` (Sync)

| File | Usage | Action |
|------|-------|--------|
| `tests/kline/comprehensive_acceptance_test.py` | `db_manager.initialize()`, `db_manager.session()` | Integration test — update to `async_db_manager` |
| `tests/integration/comprehensive_kline_test.py` | `db_manager.initialize()` | Integration test — update to `async_db_manager` |
| `tests/unit/test_market_mapping.py` | `db_manager.initialize()` | Unit test — update to `async_db_manager` |
| `tests/kline/simple_kline_test.py` | `db_manager.initialize()`, `db_manager._engine` | Integration test — update to `async_db_manager` |
| `tests/unit/test_full_calendar.py` | `db_manager.initialize()` | Unit test — update to `async_db_manager` |
| `tests/unit/test_trading_calendar_functionality.py` | `db_manager.initialize()` | Unit test — update to `async_db_manager` |
| `tests/unit/test_szse_sync.py` | Mocks `db_manager` | Update mock path to `async_db_manager` |
| `tests/unit/test_trading_calendar_service.py` | Mocks `db_manager` | Update mock path to `async_db_manager` |
| `tests/unit/test_cache_verification.py` | Mocks `db_manager` | Update mock path to `async_db_manager` |
| `tests/unit/test_empty_query.py` | Mocks `db_manager.session` | Update mock path to `async_db_manager.session` |
| `tests/kline/test_kline_command.py` | Mocks `db_manager.initialize` | Update mock path to `async_db_manager.initialize` |

**Risk Assessment:** MEDIUM. Many tests mock `db_manager`. All mock paths must be updated. The integration tests that actually initialize `db_manager` need to switch to `async_db_manager`.

---

## ARCH-02: Clean Sync Methods from kline_completeness_checker.py

### Sync Methods to Remove

| Method | Class | Line | Async Equivalent | Used By (Sync) |
|--------|-------|------|------------------|----------------|
| `check()` | `LongPeriodChecker` | 112 | `check_async()` (line 255) | `KlineCompletenessChecker.check()` |
| `check()` | `ShortPeriodChecker` | 629 | `check_async()` (line 712) | `KlineCompletenessChecker.check()` |
| `check()` | `KlineCompletenessChecker` | 812 | `check_async()` (line 861) | `handle_kline_command`, `kline_data_sync._check_data_completeness`, tests |
| `get_missing_dates()` | `KlineCompletenessChecker` | 910 | `get_missing_dates_async()` (line 940) | **No callers found in src/** |
| `is_data_complete()` | `KlineCompletenessChecker` | 970 | No direct async equivalent (calls `check_async`) | **No callers found in src/** |

### Callers of Sync `check()`

1. **`application/kline/command.py:226`** — `handle_kline_command` (sync CLI handler)
2. **`database/services/kline_data_sync.py:178`** — `_check_data_completeness` (sync fallback in sync `sync_kline_data`)

### Analysis

- `handle_kline_command` (sync) is the main concern. It is still directly tested in `tests/kline/test_kline_command.py`.
- `kline_data_sync.sync_kline_data` (sync) at line 320 calls `_check_data_completeness` which calls sync `check()`.
- **However:** The CLI entry point (`commands.py:207`) uses `handle_kline_command_async`. The scheduler (`kline_sync_job.py`) uses `check_async`. The orchestrator (`sync_orchestrator.py`) uses `check_async`.
- The sync `sync_kline_data` in `kline_data_sync.py` is called by:
  - `sync_orchestrator.sync_kline_data` (line 29) — but `sync_orchestrator.py` also has `sync_kline_data_async_impl` which is what the async path uses.
  - `tests/unit/test_kline_data_sync.py` directly tests `sync_kline_data` and `batch_sync_kline_data`.

**Decision per CONTEXT.md D-03/D-04:** Remove sync `handle_kline_command` and sync `sync_kline_data` / `batch_sync_kline_data`. Update tests to use async versions. This is a larger change than just removing checker sync methods — the entire sync call chain from CLI through orchestrator to data_sync must be removed.

**Surprise:** The sync `KLineCommandService` class (lines 38-104) is entirely unused. Its `__init__` calls `db_manager.initialize()` and `get_kline()` calls `execute_kline_query()` which is already async-internally. This class can be removed outright.

**Risk Assessment:** MEDIUM-HIGH. Tests heavily use sync versions. Need to update `tests/kline/test_kline_command.py`, `tests/unit/test_kline_data_sync.py`, and mock paths.

---

## ARCH-03: Merge Duplicate Range Merge Functions

### Implementations Found

**1. `LongPeriodChecker._merge_to_ranges`** (lines 536-583 in `kline_completeness_checker.py`)
```python
def _merge_to_ranges(
    self,
    missing_dates: List[date],
    first_trading_day_to_period: Dict[date, Tuple[date, date]],
) -> List[Tuple[date, date]]:
```
- Uses `first_trading_day_to_period` mapping to resolve period boundaries
- Merges consecutive periods if `period_start <= current_range_end + timedelta(days=1)`
- Returns list of `(period_start, period_end)` tuples

**2. `ShortPeriodChecker._merge_to_ranges`** (lines 774-791 in `kline_completeness_checker.py`)
```python
def _merge_to_ranges(self, dates: List[date]) -> List[Tuple[date, date]]:
```
- Simple date list merging
- Merges if `dates[i] > range_end + timedelta(days=1)`
- Returns list of `(range_start, range_end)` tuples

**3. `KlineDataSyncService._merge_dates_to_ranges`** (lines 299-318 in `kline_data_sync.py`)
```python
def _merge_dates_to_ranges(
    self,
    dates: list[date],
) -> list[tuple[date, date]]:
```
- Identical logic to ShortPeriodChecker version
- Called by `_fallback_completeness_check` and `_fallback_completeness_check_async`

**4. `TradingCalendarService._merge_dates_to_ranges`** (lines 461-480 in `trading_calendar.py`)
```python
def _merge_dates_to_ranges(
    self,
    dates: list[date],
) -> list[tuple[date, date]]:
```
- Identical logic again
- Called by `get_trading_days` and `get_trading_days_async`

### Unified Signature

```python
def merge_dates_to_ranges(
    dates: list[date],
    date_to_period: dict[date, tuple[date, date]] | None = None,
) -> list[tuple[date, date]]:
    """将日期列表合并为连续区间.

    Args:
        dates: 已排序或无序的日期列表
        date_to_period: 可选的日期到周期边界的映射。
            如果提供，使用映射中的 (period_start, period_end) 作为范围边界；
            否则直接使用日期本身作为范围边界。

    Returns:
        合并后的范围列表 [(start, end), ...]
    """
```

**Migration Plan:**
1. Create `shared_kernel/utils/date_range_utils.py` with `merge_dates_to_ranges()`
2. Replace `LongPeriodChecker._merge_to_ranges` calls with `merge_dates_to_ranges(sorted(missing_dates), first_trading_day_to_period)`
3. Replace `ShortPeriodChecker._merge_to_ranges` calls with `merge_dates_to_ranges(missing_dates)`
4. Replace `KlineDataSyncService._merge_dates_to_ranges` calls with `merge_dates_to_ranges(missing_dates)`
5. Replace `TradingCalendarService._merge_dates_to_ranges` calls with `merge_dates_to_ranges(missing_dates)`
6. Remove the 4 instance methods

**Risk Assessment:** LOW. Pure function refactoring with clear test coverage.

---

## ARCH-04: Fix BatchSyncResult Duplicate Decorator

**Location:** `src/galaxy_db_sync/database/services/kline_data_sync.py`, lines 1227-1228

```python
@dataclass
@dataclass
class BatchSyncResult:
```

**Fix:** Remove one `@dataclass` decorator.

**Risk Assessment:** Trivial. No references to change.

---

## ARCH-05: Rename empty_query.py → empty_query_cache.py

### Rename Scope

| Item | Current | New |
|------|---------|-----|
| File | `database/services/empty_query.py` | `database/services/empty_query_cache.py` |
| Service class | `EmptyQueryResultService` | `EmptyQueryCacheService` |
| Instance variable | `empty_query_service` | `empty_query_cache_service` |
| Model file | `database/models/empty_query_result.py` | `database/models/empty_query_cache.py` |
| Model class | `EmptyQueryResult` | `EmptyQueryCache` |
| Table name | `empty_query_results` | `empty_query_caches` |

### References to Update in `src/`

**In `database/services/empty_query.py` (the file itself):**
- All internal references to `EmptyQueryResult` → `EmptyQueryCache`
- All `empty_query_results` table name references → `empty_query_caches`

**In `database/services/kline_data_sync.py`:**
- Line 16: `from galaxy_db_sync.database.services.empty_query import empty_query_service`
- Lines 384, 456, 464: `empty_query_service.is_confirmed_empty`, `.record_empty_result` (sync)
- Lines 541, 615, 623: `await empty_query_service.is_confirmed_empty_async`, `.record_empty_result_async` (async)
- Lines 774, 836: `empty_query_service.batch_record_empty_results`, `.batch_is_confirmed_empty` (sync)
- Lines 895, 1119: `await empty_query_service.batch_is_confirmed_empty_async`, `.batch_record_empty_results_async` (async)

**In `application/kline/sync_orchestrator.py`:**
- Line 16: `from galaxy_db_sync.database.services.empty_query import empty_query_service`
- Line 200: `empty_query_service.is_confirmed_empty()`

**In `database/models/__init__.py`:**
- Line 25: `from galaxy_db_sync.database.models.empty_query_result import EmptyQueryResult`
- Line 57: `"EmptyQueryResult"` in `__all__`

**In `database/services/__init__.py`:**
- Check if `empty_query_service` or `EmptyQueryResultService` is exported (currently not exported)

### Test References to Update

| File | References |
|------|-----------|
| `tests/unit/test_empty_query.py` | Module docstring, import paths, mock paths |
| `tests/unit/test_kline_data_sync.py` | Mock paths like `galaxy_db_sync.database.services.kline_data_sync.empty_query_service.is_confirmed_empty` |
| `tests/kline/test_async_orchestrator_integration.py` | Mock paths like `galaxy_db_sync.application.kline.sync_orchestrator.empty_query_service.is_confirmed_empty` |
| `tests/unit/test_execute_kline_query.py` | Mock paths |
| `tests/unit/test_async_sync_orchestrator.py` | Mock paths |

### Alembic Migration

Need a new migration script to rename table:
```python
op.rename_table('empty_query_results', 'empty_query_caches')
```

The model uses composite PK on `(symbol, interval, start_date, end_date)` — no FK constraints reference this table, so rename is safe.

**Risk Assessment:** MEDIUM. Many import and mock paths to update. Alembic migration needed.

---

## ARCH-06: Remove Unused Imports/Code

### Orphaned Imports After ARCH-01~05

**After ARCH-01 (remove connection.py):**
- `sqlalchemy` imports in `kline_completeness_checker.py` (line 131 inside `check()`) — only used by sync `check()` methods
- `INTERVAL_MODEL_MAP` import in `kline_completeness_checker.py` (line 19) — only used by sync `check()` methods
- `db_manager` import in `kline_completeness_checker.py` (line 17) — only for sync methods

**After ARCH-02 (remove sync checker methods):**
- `BaseCompletenessChecker` abstract class — if both sync `check()` methods are removed, the ABC may still be useful for documentation; keep but evaluate
- `get_missing_dates()` and `is_data_complete()` — no callers found; safe to remove

**After ARCH-03 (merge range functions):**
- `timedelta` may become unused in some files if only used by `_merge_dates_to_ranges` — verify

**After ARCH-05 (rename empty_query):**
- Old import statements become invalid — caught by Python import errors

### Additional Dead Code

**In `application/kline/command.py`:**
- `KLineCommandService` class (lines 38-104) — entirely unused, calls sync `db_manager`
- `handle_kline_command()` function (lines 107-312) — sync CLI handler, superseded by `handle_kline_command_async`. Tests still use it.
- `sync_kline_data()` function (lines 29-103 in `sync_orchestrator.py`) — sync version, tests still use it.

**In `database/services/kline_data_sync.py`:**
- `sync_kline_data()` method (lines 320-475) — sync version
- `batch_sync_kline_data()` method (lines 637-796) — sync version
- `_check_data_completeness()` method (lines 169-193) — sync version
- `_fallback_completeness_check()` method (lines 219-257) — sync version

**Note on test dependency:** `tests/unit/test_kline_data_sync.py` directly calls sync methods. These tests must be updated to call async methods (with `asyncio.run()` or `pytest-asyncio`) before sync methods can be removed.

---

## Safe Execution Order

### Wave 1: Fix Foundation (No Dependencies)
1. **ARCH-04:** Remove duplicate `@dataclass` — trivial, no dependencies
2. **ARCH-03:** Create `date_range_utils.py` and replace `_merge_dates_to_ranges` / `_merge_to_ranges` calls — pure function, no runtime dependencies

### Wave 2: Rename Module (Depends on nothing)
3. **ARCH-05:** Rename `empty_query` → `empty_query_cache`:
   - Create new file with renamed classes
   - Update all imports in `src/`
   - Update all mock paths in `tests/`
   - Create Alembic migration for table rename
   - Delete old file

### Wave 3: Remove Sync Database Layer (Depends on Wave 2)
4. **ARCH-02:** Remove sync methods from services:
   - Remove sync methods from `kline_completeness_checker.py`
   - Remove sync methods from `empty_query_cache.py`
   - Remove sync methods from `trading_calendar.py`
   - Remove sync methods from `missing_data_tracker.py`
   - Update tests that mock sync methods to mock async methods

### Wave 4: Remove Sync CLI Handlers (Depends on Wave 3)
5. Update `application/kline/command.py`:
   - Remove `KLineCommandService` class
   - Remove `handle_kline_command` sync function OR convert tests to use `handle_kline_command_async`
   - Remove `db_manager` import, keep only `async_db_manager`
6. Update `application/calendar/command.py`:
   - Replace `db_manager.initialize()` with `async_db_manager.initialize()`

### Wave 5: Remove connection.py (Depends on Wave 4)
7. **ARCH-01:** Delete `database/core/connection.py`
8. Update `database/core/__init__.py` to remove sync exports
9. Update `src/galaxy_db_sync/__init__.py` to remove sync exports
10. Update all test files that import/mock `db_manager`

### Wave 6: Final Cleanup (Depends on Wave 5)
11. **ARCH-06:** Run `ruff check .` and `mypy src/` to find orphaned imports
12. Remove any remaining unused imports

---

## Surprises and Edge Cases

### Surprise 1: `handle_kline_command` (sync) still heavily tested
The main CLI entry `commands.py` uses `handle_kline_command_async`, but `tests/kline/test_kline_command.py` has ~15 test cases calling the sync `handle_kline_command`. These tests must be migrated to async versions or the sync function kept as a thin wrapper.

**Recommendation:** Convert tests to use `asyncio.run(handle_kline_command_async(args))` rather than keeping sync wrapper. This aligns with D-13 (all services async).

### Surprise 2: `KLineCommandService` is completely unused
This class (lines 38-104) appears to be a legacy compatibility layer. No imports found outside its own file. Safe to remove.

### Surprise 3: `handle_kline_command_async` initializes BOTH managers
Lines 451-452 and 506-507 in `command.py`:
```python
async_db_manager.initialize()
db_manager.initialize()
```
After ARCH-01, `db_manager` won't exist. Remove the second line.

### Surprise 4: `kline_data_sync.py` has sync AND async versions of everything
The sync `sync_kline_data()` and `batch_sync_kline_data()` methods are tested directly. The scheduler and CLI only use async versions. Tests need updating.

### Surprise 5: `trading_calendar.py` sync methods may still be used by calendar command
`handle_calendar_command` calls `trading_calendar_service.sync_calendar(year)` which is sync. However, `sync_calendar` doesn't use `db_manager` for queries — it uses `db_manager.get_session()` in `_save_to_db()`. After ARCH-01, this needs to use `async_db_manager` or the calendar command needs to be made async.

**Resolution:** `handle_calendar_command` is already wrapped in `asyncio.to_thread` at `commands.py:210`. The sync `sync_calendar` method calls `_save_to_db` which uses sync `db_manager.get_session()`. We need to either:
- Make `handle_calendar_command` async and use async methods
- Or keep a minimal sync path for calendar only

Per CONTEXT.md D-04, calendar command's `db_manager.initialize()` should become `async_db_manager.initialize()`. The `_save_to_db` in `trading_calendar.py` should use `async_db_manager` (async version `_save_to_db_async` already exists).

### Edge Case: Table rename migration
The `empty_query_results` table rename requires Alembic migration. No foreign keys reference this table. The migration is straightforward:
```python
def upgrade() -> None:
    op.rename_table('empty_query_results', 'empty_query_caches')

def downgrade() -> None:
    op.rename_table('empty_query_caches', 'empty_query_results')
```

---

## Test Impact Summary

| Test File | Impact | Action Required |
|-----------|--------|-----------------|
| `tests/kline/test_kline_command.py` | HIGH | Mock paths change `db_manager` → `async_db_manager`; test sync `handle_kline_command` → async `handle_kline_command_async` |
| `tests/unit/test_kline_data_sync.py` | HIGH | Test sync `sync_kline_data` / `batch_sync_kline_data` → async versions; mock paths change |
| `tests/unit/test_empty_query.py` | MEDIUM | Mock paths change; module import path changes |
| `tests/unit/test_kline_completeness_checker.py` | MEDIUM | Test sync `check` → `check_async`; `_merge_to_ranges` tests → `date_range_utils` |
| `tests/unit/test_kline_completeness_checker_async.py` | LOW | May need to add coverage for methods that were only tested via sync path |
| `tests/kline/test_async_orchestrator_integration.py` | MEDIUM | Mock paths for `empty_query_service` → `empty_query_cache_service` |
| `tests/unit/test_execute_kline_query.py` | MEDIUM | Mock paths change |
| `tests/unit/test_async_sync_orchestrator.py` | MEDIUM | Mock paths change |
| `tests/unit/test_trading_calendar_service.py` | LOW | Mock `db_manager` → `async_db_manager` |
| `tests/unit/test_szse_sync.py` | LOW | Mock `db_manager` → `async_db_manager` |
| `tests/unit/test_cache_verification.py` | LOW | Mock `db_manager` → `async_db_manager` |
| Integration tests (`comprehensive_*`, `simple_kline_test`, etc.) | MEDIUM | Replace `db_manager.initialize()` with `async_db_manager.initialize()` |

---

## Package Legitimacy Audit

No external packages installed in this phase. All changes are internal code refactoring.

---

## Common Pitfalls

### Pitfall 1: Removing sync methods before updating tests
**What goes wrong:** Tests fail immediately because they call removed sync methods.
**How to avoid:** Update tests to use async methods BEFORE removing sync methods, or in the same commit.

### Pitfall 2: Missing mock path updates
**What goes wrong:** Tests pass but don't actually test anything because mocks patch wrong (old) paths.
**How to avoid:** When `empty_query` → `empty_query_cache`, mock paths like `galaxy_db_sync.database.services.empty_query.empty_query_service` must become `galaxy_db_sync.database.services.empty_query_cache.empty_query_cache_service`. Do a global search-replace.

### Pitfall 3: `handle_calendar_command` thread safety
**What goes wrong:** `async_db_manager.initialize()` creates an async engine. Calling it from `asyncio.to_thread` may work but is not the intended pattern.
**How to avoid:** Make `handle_calendar_command` async, or initialize `async_db_manager` in the caller (`commands.py`) before `asyncio.to_thread`.

### Pitfall 4: Orphaned `__all__` exports
**What goes wrong:** `database/models/__init__.py` exports `EmptyQueryResult`. After rename, this export becomes invalid.
**How to avoid:** Update `__all__` lists in all `__init__.py` files that reference renamed symbols.

---

## Code Examples

### Unified Date Range Merge Function
```python
# shared_kernel/utils/date_range_utils.py
from datetime import date, timedelta


def merge_dates_to_ranges(
    dates: list[date],
    date_to_period: dict[date, tuple[date, date]] | None = None,
) -> list[tuple[date, date]]:
    """将日期列表合并为连续区间.

    Args:
        dates: 日期列表（不需要预先排序）
        date_to_period: 可选的日期到周期边界的映射。
            如果提供，使用映射中的 (period_start, period_end) 作为范围边界；
            否则直接使用日期本身作为范围边界。

    Returns:
        合并后的范围列表 [(start, end), ...]
    """
    if not dates:
        return []

    sorted_dates = sorted(dates)
    ranges: list[tuple[date, date]] = []

    if date_to_period:
        # 长周期模式：使用周期边界
        current_range_start: date | None = None
        current_range_end: date | None = None

        for d in sorted_dates:
            if d not in date_to_period:
                continue
            period_start, period_end = date_to_period[d]

            if current_range_start is None:
                current_range_start = period_start
                current_range_end = period_end
            elif period_start <= current_range_end + timedelta(days=1):
                current_range_end = period_end
            else:
                ranges.append((current_range_start, current_range_end))
                current_range_start = period_start
                current_range_end = period_end

        if current_range_start is not None:
            ranges.append((current_range_start, current_range_end))
    else:
        # 短周期模式：直接使用日期
        range_start = sorted_dates[0]
        range_end = sorted_dates[0]

        for d in sorted_dates[1:]:
            if d > range_end + timedelta(days=1):
                ranges.append((range_start, range_end))
                range_start = d
            range_end = d

        ranges.append((range_start, range_end))

    return ranges
```

### Alembic Migration for Table Rename
```python
# alembic/versions/xxxx_rename_empty_query_results.py
"""Rename empty_query_results to empty_query_caches."""

from alembic import op

# revision identifiers, used by Alembic.
revision = "xxxx"
down_revision = "<previous>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("empty_query_results", "empty_query_caches")


def downgrade() -> None:
    op.rename_table("empty_query_caches", "empty_query_results")
```

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `KLineCommandService` is unused outside its definition file | ARCH-01 | If wrong, removing it breaks an internal API consumer |
| A2 | `handle_kline_command` (sync) is not called by production code — only tests | ARCH-01 | If wrong, CLI breaks after removal |
| A3 | `get_missing_dates()` and `is_data_complete()` have no callers in src/ | ARCH-02 | If wrong, removing them causes ImportError or AttributeError |
| A4 | No foreign keys reference `empty_query_results` table | ARCH-05 | If wrong, table rename migration fails |
| A5 | All scheduler jobs use async versions of services | ARCH-02 | If wrong, scheduler breaks after sync method removal |

---

## Open Questions

1. **Should `handle_kline_command` (sync) be kept as a thin wrapper for backward compatibility?**
   - What we know: CLI uses `handle_kline_command_async` exclusively
   - What's unclear: Whether any external scripts call `handle_kline_command` directly
   - Recommendation: Remove it. If external callers exist, they can use `asyncio.run(handle_kline_command_async(args))`

2. **Should sync `sync_kline_data` / `batch_sync_kline_data` in `kline_data_sync.py` be kept?**
   - What we know: Scheduler and CLI use async versions
   - What's unclear: Whether any manual scripts call sync versions
   - Recommendation: Remove per D-03. Tests should be updated to test async versions.

3. **Calendar command async conversion scope**
   - What we know: `handle_calendar_command` is wrapped in `asyncio.to_thread`
   - What's unclear: Whether to fully asyncify calendar command or just swap `db_manager` for `async_db_manager` inside the sync function
   - Recommendation: Keep calendar command sync but make it use `async_db_manager` via `asyncio.run()` pattern, or initialize `async_db_manager` before the thread call. Simpler: make `handle_calendar_command` async since it's already called via `asyncio.to_thread`.

---

## Environment Availability

No external dependencies required. This phase is purely code refactoring.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| ruff | Lint check (ARCH-06) | ✓ | — | — |
| mypy | Type check (ARCH-06) | ✓ | — | — |
| pytest | Test verification | ✓ | — | — |
| Alembic | Migration (ARCH-05) | ✓ | — | — |

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | `pyproject.toml` (pytest section) |
| Quick run command | `pytest tests/unit/ -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ARCH-01 | `connection.py` removed, no `db_manager` references | unit + integration | `pytest tests/ -k "not comprehensive"` | ✅ existing |
| ARCH-02 | Sync checker methods removed | unit | `pytest tests/unit/test_kline_completeness_checker.py -x` | ✅ existing |
| ARCH-03 | Range merge unified | unit | `pytest tests/unit/test_kline_completeness_checker.py -x` | ✅ existing |
| ARCH-04 | BatchSyncResult has single @dataclass | unit | `pytest tests/unit/test_kline_data_sync.py -x` | ✅ existing |
| ARCH-05 | empty_query renamed to empty_query_cache | unit | `pytest tests/unit/test_empty_query.py -x` | ✅ existing |
| ARCH-06 | No unused imports | lint | `ruff check .` | ✅ existing |

### Wave 0 Gaps
- [ ] `tests/unit/test_date_range_utils.py` — new test file for unified merge function
- [ ] `tests/unit/test_empty_query_cache.py` — rename of `test_empty_query.py`
- [ ] Update mock paths in all test files that reference `empty_query_service`

---

## Security Domain

No security impact. This phase is internal refactoring with no external behavior changes, no new dependencies, and no authentication/authorization code touched.

---

## Sources

### Primary (HIGH confidence)
- Direct codebase grep and file reads — all reference chains verified empirically
- `src/galaxy_db_sync/database/core/connection.py` — file to be removed
- `src/galaxy_db_sync/database/core/async_connection.py` — verified as replacement
- `src/galaxy_db_sync/application/cli/commands.py` — verified CLI uses async handler

### Secondary (MEDIUM confidence)
- `tests/kline/test_kline_command.py` — tests use sync handler (assumed: tests need updating)
- `tests/unit/test_kline_data_sync.py` — tests use sync methods (assumed: tests need updating)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no external packages
- Architecture: HIGH — all reference chains verified via grep
- Pitfalls: MEDIUM — test migration effort is the main risk

**Research date:** 2026-05-28
**Valid until:** 2026-06-28 (stable codebase)

---

## RESEARCH COMPLETE

**Phase:** 10 - 代码清理与架构规范化
**Confidence:** HIGH

### Key Findings
1. **7 files import from `connection.py`** — all have async alternatives in `async_connection.py`
2. **Sync `handle_kline_command` is dead in production** — CLI uses `handle_kline_command_async`, but 15+ tests still call sync version
3. **4 duplicate range merge implementations** — 3 identical simple versions + 1 period-aware version; can unify with optional `date_to_period` parameter
4. **15+ references to `empty_query_service`** across src/ and tests/ need updating for rename
5. **`KLineCommandService` class is completely unused** — safe to remove outright
6. **`BatchSyncResult` duplicate decorator** at lines 1227-1228 — trivial one-line fix

### File Created
`.planning/phases/10-code-cleanup/10-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard stack | HIGH | No external dependencies |
| Architecture | HIGH | All imports verified via grep |
| Pitfalls | MEDIUM | Test migration is the main risk; ~20 test files need mock path updates |

### Open Questions
1. Are there external scripts calling sync `handle_kline_command`? (Recommendation: remove; callers can use `asyncio.run`)
2. Should calendar command be fully asyncified or just swap db_manager inside sync function? (Recommendation: make async since already wrapped in `asyncio.to_thread`)

### Ready for Planning
Research complete. Planner can now create PLAN.md files.
