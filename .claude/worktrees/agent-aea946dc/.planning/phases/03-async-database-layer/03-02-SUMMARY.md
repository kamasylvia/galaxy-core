---
phase: 03-async-database-layer
plan: 02
subsystem: database.services
tags: [async, kline, query, upsert, dependency-injection]
requires: [03-01]
provides: [AsyncKlineService, async_kline_query, async_kline_save]
affects: [Phase 2 orchestrator stub replacement]
tech_stack:
  added:
    - asyncpg (already installed in 03-01)
  patterns:
    - Dependency injection pattern (no global singleton)
    - PostgreSQL UPSERT with on_conflict_do_update
    - SQLAlchemy async execute/scalars pattern
    - Reuse sync helpers (parse_trade_time, extract_row_values, KlineDBInterface)
key_files:
  created:
    - src/galaxy_db_sync/database/services/async_kline_query.py (~168 lines)
    - src/galaxy_db_sync/database/services/async_kline_save.py (~195 lines)
    - src/galaxy_db_sync/database/services/async_kline.py (~214 lines)
    - tests/unit/test_async_kline_query.py (~232 lines)
    - tests/unit/test_async_kline_save.py (~255 lines)
    - tests/unit/test_async_kline.py (~252 lines)
  modified:
    - tests/unit/conftest.py (akshare mocking for import chain)
decisions:
  - D-13: AsyncKlineService uses explicit DI pattern (no global singleton)
  - D-14: Reuse sync query builders (KlineDBInterface) - they use select() pattern compatible with async
  - D-15: Reuse sync save helpers (parse_trade_time, extract_row_values) - no async needed for pure functions
  - D-16: Same UPSERT logic as sync version - on_conflict_do_update on (symbol, trade_time)
metrics:
  duration: ~15 minutes
  tasks_completed: 4
  tests_added: 28
  files_created: 6
  files_modified: 1
---

# Phase 3 Plan 02: Async Kline Services Summary

## One-liner

Implemented async K-line services (AsyncKlineService, async query, async UPSERT) with dependency injection pattern, maintaining behavioral parity with sync version.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create async kline query functions | 15f1781 | async_kline_query.py, test_async_kline_query.py, conftest.py |
| 2 | Create async kline save functions (UPSERT) | 302e137 | async_kline_save.py, test_async_kline_save.py |
| 3 | Create AsyncKlineService with dependency injection | 3d089a6 | async_kline.py, test_async_kline.py |
| 4 | Create unit tests for async services | included above | test_async_kline*.py (28 tests) |

## Key Artifacts

### async_kline_query.py

Location: `src/galaxy_db_sync/database/services/async_kline_query.py`

Key functions:
- `query_kline_from_db_async(session, symbols, start_date, end_date, interval)` - Returns Dict[str, pd.DataFrame]
- `get_available_intervals_for_symbol_async(session, symbol)` - Returns List[str]
- `get_data_range_for_symbol_async(session, symbol, interval)` - Returns tuple[datetime, datetime]

Implementation notes:
- Reuses `KlineDBInterface.build_query()` from sync version (select() pattern)
- Reuses `parse_date_for_interval()` for date parsing (no async needed)
- DataFrame format identical to sync version (columns: open, high, low, close, volume, amount)

### async_kline_save.py

Location: `src/galaxy_db_sync/database/services/async_kline_save.py`

Key functions:
- `batch_save_kline_to_db_async(session, kline_dict, interval)` - Returns int (records saved)
- `save_kline_to_db_async(session, symbol, df, interval, security_type)` - Returns int
- `_upsert_records_async(session, records, table_model)` - PostgreSQL UPSERT

Implementation notes:
- Reuses `parse_trade_time()` and `extract_row_values()` from sync version
- Deduplication by (symbol, trade_time) preserved exactly
- `pg_insert().on_conflict_do_update(index_elements=['symbol', 'trade_time'])`
- Exception triggers async rollback

### AsyncKlineService Class

Location: `src/galaxy_db_sync/database/services/async_kline.py`

Key design:
- `__init__(db_manager: AsyncDatabaseManager)` - Explicit DI (ASYNC-04 requirement)
- No global singleton - must be instantiated with injected db_manager
- Methods: query_kline_from_db, batch_save_kline_to_db, merge_db_and_api_data, get_data_range_for_symbol
- merge_db_and_api_data is pure function (no async, same logic as sync version)

### Unit Tests

28 tests covering:
- AsyncKlineService DI pattern verification
- Query returns correct DataFrame format
- Empty result handling
- UPSERT uses on_conflict_do_update
- Deduplication by (symbol, trade_time)
- Exception rollback behavior
- Merge parity with sync version (pd.testing.assert_frame_equal)

## Verification Results

All automated verification passed:
- 28 unit tests pass: `pytest tests/unit/test_async_kline*.py -v`
- All async services import correctly (verified via pytest collection)
- DI pattern enforced (TypeError if instantiated without db_manager)
- No global singleton created

## Deviations from Plan

None - plan executed exactly as written.

## Next Steps

- Plan 03: Integration tests for behavioral parity verification
- Phase 2: Replace stub async database calls with AsyncKlineService

## Self-Check: PASSED

All files and commits verified:
- async_kline_query.py: FOUND
- async_kline_save.py: FOUND
- async_kline.py: FOUND
- test_async_kline_query.py: FOUND
- test_async_kline_save.py: FOUND
- test_async_kline.py: FOUND
- 15f1781 (query): FOUND
- 302e137 (save): FOUND
- 3d089a6 (service): FOUND