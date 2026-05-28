---
phase: 06-auto-sync-scheduler-23-12-20
plan: 03
subsystem: scheduler
tags: [sync-jobs, kline, calendar, retry, state-management]
dependencies:
  requires: [06-01, 06-02]
  provides: [KlineSyncJob, CalendarSyncJob]
  affects: [scheduler_loop, auto_sync]
tech_stack:
  added: [pytest-asyncio, AsyncMock]
  patterns: [TDD, state-pattern, retry-decorator]
key_files:
  created:
    - src/galaxy_db_sync/application/scheduler/kline_sync_job.py
    - src/galaxy_db_sync/application/scheduler/calendar_sync_job.py
    - tests/scheduler/test_kline_sync_job.py
    - tests/scheduler/test_calendar_sync_job.py
  modified:
    - src/galaxy_db_sync/application/scheduler/__init__.py
decisions:
  - D-19: KlineSyncJob syncs periods in order: DAY first, then ascending (DAY, WEEK, MONTH, SEASON, YEAR)
  - D-20: Period identifiers use ISO week calendar format for WEEK (YYYY-WNN)
  - D-21: CalendarSyncJob uses config-driven window (Dec 20-31) with force sync on Dec 20
metrics:
  duration: "22 tests in 0.37s"
  completed_date: "2026-04-12"
  test_coverage: "22 passing tests (13 KlineSyncJob, 9 CalendarSyncJob)"
---

# Phase 06 Plan 03: K-line and Calendar Sync Jobs Summary

## One-Liner

KlineSyncJob and CalendarSyncJob modules orchestrate scheduled K-line and calendar synchronization with retry integration and state tracking per SCHED-06 and SCHED-07.

## Key Changes

### Task 1: KlineSyncJob

Created `src/galaxy_db_sync/application/scheduler/kline_sync_job.py`:

- **run() method**: Detects periods ending today via `IntervalBoundaryChecker.get_periods_to_sync_today()`
- **Period identifiers**: DAY='YYYYMMDD', WEEK='YYYY-WNN', MONTH='YYYY-MM', SEASON='YYYY-QN', YEAR='YYYY'
- **State transitions**: `is_synced()` -> `mark_running()` -> sync with retry -> `mark_success()`/`mark_failed()`
- **Config filtering**: Only syncs intervals in `enabled_intervals` config setting
- **Sync ordering**: DAY first, then ascending (per D-19)

### Task 2: CalendarSyncJob

Created `src/galaxy_db_sync/application/scheduler/calendar_sync_job.py`:

- **run() method**: Handles Dec 20-31 calendar sync window
- **Dec 20**: Force sync next year calendar (sync_day config)
- **Dec 20-31**: Check if next year calendar exists, sync if missing
- **Non-December**: Skips entirely
- **State transitions**: Same pattern as KlineSyncJob

## Files Created/Modified

| File | Purpose |
|------|---------|
| kline_sync_job.py | K-line sync orchestration per SCHED-06 |
| calendar_sync_job.py | Calendar sync orchestration per SCHED-07 |
| test_kline_sync_job.py | 13 tests for KlineSyncJob |
| test_calendar_sync_job.py | 9 tests for CalendarSyncJob |
| __init__.py | Added KlineSyncJob, CalendarSyncJob exports |

## Dependencies Added

- pytest-asyncio for async test support
- AsyncMock for mocking async methods
- Copy of async_connection.py and sync_state.py models from earlier phases

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing akshare mock in conftest.py**
- **Found during:** Test import phase
- **Issue:** Import chain triggered akshare dependency which wasn't installed
- **Fix:** Added `sys.modules["akshare"] = MagicMock()` to conftest.py
- **Files modified:** tests/scheduler/conftest.py

**2. [Rule 1 - Bug] Week identifier test assertion incorrect**
- **Found during:** Test execution
- **Issue:** Test expected week 12 for March 28, 2025, but ISO calendar shows week 13
- **Fix:** Updated test assertion to use correct ISO week number (2025-W13)
- **Files modified:** tests/scheduler/test_kline_sync_job.py

**3. [Rule 3 - Blocking] Missing test method mocks**
- **Found during:** Test execution
- **Issue:** `test_non_december_skips` and `test_before_dec_20_skips` called `assert_not_called()` on real methods
- **Fix:** Added `job._check_calendar_exists = AsyncMock(return_value=True)` to tests
- **Files modified:** tests/scheduler/test_calendar_sync_job.py

None - plan executed with minor corrections for test infrastructure.

## Known Stubs

- `_do_sync()` in KlineSyncJob is a stub that logs sync intention - full implementation requires security list retrieval and date range calculation (deferred to integration testing)
- Calendar sync `_do_sync_calendar()` calls `sync_calendar()` which needs actual trading calendar service integration

## Verification

```bash
# All tests pass
uv run pytest tests/scheduler/test_kline_sync_job.py tests/scheduler/test_calendar_sync_job.py -v
# 22 passed in 0.37s
```

## Commits

| Hash | Message |
|------|---------|
| 4a43626 | feat(06-03): add KlineSyncJob for scheduled K-line synchronization |
| be2c832 | feat(06-03): add CalendarSyncJob for scheduled calendar synchronization |

## Self-Check: PASSED

- [x] kline_sync_job.py exists with KlineSyncJob class
- [x] calendar_sync_job.py exists with CalendarSyncJob class
- [x] Both modules export from __init__.py
- [x] 22 tests pass
- [x] Commits exist: 4a43626, be2c832

---
*Completed: 2026-04-12*
*Executor: Claude Opus 4.6*