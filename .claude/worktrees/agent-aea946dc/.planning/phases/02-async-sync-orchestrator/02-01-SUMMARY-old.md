---
phase: 02-async-sync-orchestrator
plan: 01
subsystem: api
tags: [asyncio, kline, orchestrator, pandas, pytest]
requires:
  - phase: 01-async-api-client-wrapper
    provides: async AmazingData client wrappers via query_kline_async
provides:
  - async batch fetch helpers for grouped K-line ranges
  - regression coverage for merge ordering, failure mapping, and semaphore limits
  - sync wrappers that preserve current callers while delegating hot-path concurrency to asyncio
affects: [execute_kline_query, phase-02-plan-02, async-orchestrator]
tech-stack:
  added: [pandas-stubs]
  patterns: [asyncio.gather batch orchestration, asyncio.Semaphore concurrency limiting, sync-to-async compatibility wrappers]
key-files:
  created: [/home/laniakea/Development/galaxy-db-sync/tests/unit/test_async_sync_orchestrator.py]
  modified: [/home/laniakea/Development/galaxy-db-sync/src/galaxy_db_sync/application/kline/sync_orchestrator.py]
key-decisions:
  - "Kept execute_kline_query and other sync entrypoints unchanged while introducing dedicated async helper functions for Phase 2 callers."
  - "Preserved existing pandas concat, duplicated(keep=\"last\"), and sort_index merge semantics so async completion order cannot change data results."
patterns-established:
  - "Pattern 1: one coroutine per missing-range batch using fetch_single_batch_async under a shared asyncio.Semaphore"
  - "Pattern 2: sync compatibility wrappers call asyncio.run around async helper primitives until later CLI rewiring"
requirements-completed: [ASYNC-02, TEST-01, PERF-01]
duration: 17min
completed: 2026-04-07
---

# Phase 02 Plan 01: Async Sync Orchestrator Summary

**Async K-line batch fetch helpers using asyncio.gather and asyncio.Semaphore with deterministic merge and failure semantics preserved.**

## Performance

- **Duration:** 17 min
- **Started:** 2026-04-07T05:26:02Z
- **Completed:** 2026-04-07T05:43:42Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added async regression coverage for batch merge ordering, whole-batch failure mapping, semaphore-limited concurrency, and unsuccessful item handling.
- Replaced thread-pool batch-fetch internals with async helpers built on `await amazing_data_client.query_kline_async`, `asyncio.gather`, and `asyncio.Semaphore`.
- Kept current synchronous callers compatible by wrapping the new async helpers with thin `asyncio.run(...)` adapters.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create async orchestrator regression scaffold** - `cc95a59` (test)
2. **Task 2: Add async batch fetch helpers in sync_orchestrator.py** - `31365a7` (feat)

## Files Created/Modified
- `/home/laniakea/Development/galaxy-db-sync/tests/unit/test_async_sync_orchestrator.py` - async regression tests covering merge, failed_codes behavior, empty groups, and semaphore limits
- `/home/laniakea/Development/galaxy-db-sync/src/galaxy_db_sync/application/kline/sync_orchestrator.py` - async query normalization, async single-batch fetch, and async grouped batch orchestration helpers

## Decisions Made
- Kept `group_symbols_by_missing_ranges()` behavior unchanged apart from stricter typing so Phase 2 only swaps concurrency primitives, not business grouping rules.
- Used `return_exceptions=True` with an explicit `(key, symbols)` zip map so failed batches still deterministically extend `failed_codes` for every symbol in that batch.
- Installed `pandas-stubs` in the project venv so the plan’s exact `mypy` verification command can pass without custom flags.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing local dependencies required by plan verification**
- **Found during:** Task 1 and Task 2 verification
- **Issue:** The project venv was missing `toml` and later lacked `pandas-stubs`, causing test collection and the exact `mypy` command from the plan to fail before code behavior could be verified.
- **Fix:** Installed `toml` and `pandas-stubs` into the existing `.venv` so the repository’s configured import and type-check flow could execute.
- **Files modified:** `/home/laniakea/Development/galaxy-db-sync/uv.lock`
- **Verification:** `.venv/bin/pytest tests/unit/test_async_sync_orchestrator.py -q`, `.venv/bin/ruff check ...`, `.venv/bin/mypy src/galaxy_db_sync/application/kline/sync_orchestrator.py`
- **Committed in:** not committed (pre-existing workspace file `uv.lock` had unrelated modifications and was left untouched per scope boundary)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Verification-only environment repair was necessary to complete the scoped plan. No product scope creep.

## Known Stubs
- `/home/laniakea/Development/galaxy-db-sync/src/galaxy_db_sync/application/kline/sync_orchestrator.py:57` — `failed_codes=[]` is an intentional empty result initializer for the no-sync-needed path, not a user-visible placeholder.

## Issues Encountered
- Import-time side effects from optional SDK dependencies (`AmazingData`, `akshare`) would have blocked isolated unit tests, so the new test module injects lightweight stubs before importing orchestrator modules.
- The repository contained unrelated pre-existing modifications and untracked planning files; task commits were staged narrowly to keep plan scope limited to 02-01 deliverables.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 2 Plan 02 can now route `execute_kline_query` through the new async helpers with confidence that merge, failure, and concurrency contracts are regression-tested.
- Sync compatibility remains in place, so later phases can rewire callers incrementally without reintroducing thread-pool primitives.

## Self-Check: PASSED
- Found summary file: `/home/laniakea/Development/galaxy-db-sync/.planning/phases/02-async-sync-orchestrator/02-01-SUMMARY.md`
- Found commit: `cc95a59`
- Found commit: `31365a7`

---
*Phase: 02-async-sync-orchestrator*
*Completed: 2026-04-07*
