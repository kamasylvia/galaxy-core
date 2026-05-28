# Phase 2: Async Sync Orchestrator - Research

**Researched:** 2026-04-07
**Domain:** K 线并发抓取编排从线程池迁移到原生 asyncio
**Confidence:** HIGH

## User Constraints

No `CONTEXT.md` exists for Phase 2. Planning must therefore follow the locked project constraints from `ROADMAP.md`, `REQUIREMENTS.md`, Phase 1 summaries, and `CLAUDE.md`.

## Project Constraints (from CLAUDE.md)

- Keep AmazingData SDK as a synchronous black box; async boundaries must wrap it rather than replace it.
- Use `interval` naming throughout the codebase, except for the literal `period` argument required by the SDK call.
- Always resolve SDK interval constants via `get_sdk_interval_value()`; never hardcode interval values.
- Preserve the current CLI external behavior, including arguments, summary output, and exit semantics.
- Preserve completeness-first sync behavior: check DB completeness first, fetch only missing ranges.
- Preserve empty-result caching behavior via `empty_query_service`.
- Respect current architecture layers: orchestrator logic lives in `application/kline`, DB persistence remains in `database/services`.
- K-line tables use `(symbol, trade_time)` uniqueness; data handling must not introduce duplicate writes.
- Unit tests should mock DB/API calls heavily; integration tests require a real DB connection.
- Validation commands expected by the project are `pytest tests/`, `ruff check .`, `ruff format .`, and `mypy src/`.

## Summary

Phase 2 is not a greenfield async design problem; it is a narrow concurrency-model replacement inside `src/galaxy_db_sync/application/kline/sync_orchestrator.py`. The current orchestrator already owns the business-critical semantics that must remain stable: grouping symbols by missing ranges, skipping ranges confirmed empty by `empty_query_service`, collecting per-symbol failures, and merging multiple API batches for the same symbol with dedupe-by-index and sorted output. The migration target is therefore: keep those semantics, replace only the execution model.

The current code still uses `ThreadPoolExecutor`, `as_completed`, and `threading.Semaphore` in the hot API-fetch path. Phase 1 already established the correct async boundary on the AmazingData client with `query_kline_async()` implemented as `await asyncio.to_thread(self.query_kline, ...)`, so Phase 2 should consume that wrapper instead of creating new thread-pool plumbing. Official Python 3.13 docs confirm the intended primitives: `asyncio.gather()` for concurrent awaitable aggregation, `asyncio.Semaphore` for concurrency limiting, and `asyncio.to_thread()` for blocking call offload. Because database access is still synchronous until Phase 3, the async benefit in Phase 2 is limited to orchestration clarity and removal of custom thread-pool management, not elimination of all blocking.

Primary recommendation: implement an async orchestrator surface in `sync_orchestrator.py` that uses `asyncio.gather()` plus `asyncio.Semaphore`, preserves existing grouping and merge behavior exactly, and keeps sync compatibility as a thin bridge until Phase 4 moves the CLI boundary to `asyncio.run()`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ASYNC-02 | K 线同步编排使用 `asyncio.gather` + `asyncio.Semaphore` | Use async batch fetch helpers in `sync_orchestrator.py`, consuming Phase 1 `query_kline_async()` and removing `ThreadPoolExecutor` / `as_completed` / `threading.Semaphore` from the hot path. |
| TEST-01 | 为新增 async API / service / orchestrator / CLI 路径补齐单元测试 | Add orchestrator-focused async unit tests for success, partial failure, empty-result, dedupe/merge, and semaphore-limited concurrency. |
| PERF-01 | 异步实现吞吐不低于当前实现，并保持可配置并发限制 | Preserve `GALAXY_KLINE_MAX_CONCURRENT` control and map it to `asyncio.Semaphore`; avoid serial awaits inside batch loops. |
| DATA-01 | 改造后不出现重复写入、丢数据、错误合并或事务一致性回退 | Preserve current grouping, failure collection, `empty_query_service` skipping, and pandas concat/dedupe/sort behavior before DB merge. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python `asyncio` | 3.13.12 runtime in project venv | Native async orchestration, `gather`, `Semaphore`, task scheduling | Standard library, officially documents the exact concurrency primitives Phase 2 requires |
| AmazingData client async wrapper | repo code, Phase 1-complete | Async boundary for synchronous SDK via `query_kline_async()` | Already implemented in-project; avoids reintroducing executor logic higher in the stack |
| pandas | 3.0.1 | Batch result merge, concat, index dedupe, sort | Already used by orchestrator and DB merge path; avoids changing data-shape semantics during concurrency migration |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.2 | Unit test runner | Run all orchestrator regression tests and targeted async tests |
| pytest-asyncio | 1.3.0 | Async test execution with `asyncio_mode = auto` | Required for new coroutine tests in Phase 2 |
| SQLAlchemy | 2.0.48 | Existing sync DB layer beneath orchestrator | Still used indirectly in Phase 2 through sync services until Phase 3 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `asyncio.gather()` | `asyncio.TaskGroup` | TaskGroup is cleaner for structured cancellation, but roadmap and requirements explicitly lock Phase 2 to `gather` + `Semaphore` |
| `asyncio.Semaphore` | custom rate limiter / queue worker pool | Adds unnecessary abstraction and risks behavior drift from the locked design |
| project async client wrapper | direct `asyncio.to_thread` calls in orchestrator | Spreads SDK-threading concerns out of the client boundary and duplicates Phase 1 work |

**Installation:**
```bash
uv pip install -e ".[dev,format]"
```

**Version verification:** Verified from local lockfile / registry data on 2026-04-07.
- `pytest` 9.0.2 — uploaded 2025-12-06
- `pytest-asyncio` 1.3.0 — uploaded 2025-11-10
- `pandas` 3.0.1 in lockfile, while current PyPI is 3.0.2 uploaded 2026-03-31
- `SQLAlchemy` 2.0.48 in lockfile, while current PyPI is 2.0.49 uploaded 2026-04-03

Planning implication: Phase 2 should target the versions actually locked in `uv.lock`, not assume latest PyPI behavior.

## Architecture Patterns

### Recommended Project Structure
```text
src/galaxy_db_sync/application/kline/
├── command.py              # existing sync CLI/service entrypoints remain in Phase 2
├── sync_orchestrator.py    # add async orchestration helpers here
├── result.py               # keep KlineQueryResult / KlineSyncResult contracts
└── parser.py               # continue SDK interval resolution via get_sdk_interval_value()
```

### Pattern 1: Keep business grouping synchronous, make batch execution async
**What:** Keep `group_symbols_by_missing_ranges()` as synchronous pure business logic, and swap only the batch execution layer to coroutines.
**When to use:** Always for Phase 2; grouping rules are already part of current correctness behavior.
**Example:**
```python
range_groups = group_symbols_by_missing_ranges(
    {s: completeness_results[s] for s in symbols_needing_sync},
    interval,
    interval_value,
)

api_data, failed_codes = await batch_fetch_kline_data_async(
    range_groups,
    max_concurrent=max_concurrent,
)
```
Source: repository code pattern in `/home/laniakea/Development/galaxy-db-sync/src/galaxy_db_sync/application/kline/sync_orchestrator.py` and Phase 2 requirement in `/home/laniakea/Development/galaxy-db-sync/.planning/REQUIREMENTS.md`

### Pattern 2: One coroutine per missing-range batch, gated by `asyncio.Semaphore`
**What:** Convert `fetch_single_batch()` into `fetch_single_batch_async()` that awaits the async client under semaphore control.
**When to use:** For every grouped `(begin_date, end_date, interval_value)` batch.
**Example:**
```python
async def fetch_single_batch_async(key, symbols, semaphore):
    begin_date, end_date, sdk_interval = key
    async with semaphore:
        query_result = await query_kline_with_results_async(
            code_list=symbols,
            begin_date=begin_date,
            end_date=end_date,
            interval=sdk_interval,
        )
    return normalize_batch_result(symbols, query_result)
```
Source: official Python asyncio task/synchronization docs and current repository batch shape in `sync_orchestrator.py`

### Pattern 3: Gather all batch tasks, then merge deterministically
**What:** Use `asyncio.gather(..., return_exceptions=True)` or per-task exception normalization, then merge successful DataFrames with the current concat/dedupe/sort logic.
**When to use:** After spawning one coroutine per range-group batch.
**Example:**
```python
batch_results = await asyncio.gather(*tasks, return_exceptions=True)

for batch_result in batch_results:
    if isinstance(batch_result, Exception):
        failed_codes.extend(batch_to_symbols[batch_result_key])
        continue
    success, failed, data = batch_result
    for symbol, df in data.items():
        if symbol in results and not results[symbol].empty:
            merged = pd.concat([results[symbol], df])
            results[symbol] = merged[~merged.index.duplicated(keep="last")].sort_index()
        else:
            results[symbol] = df
    failed_codes.extend(failed)
```
Source: current merge logic in `/home/laniakea/Development/galaxy-db-sync/src/galaxy_db_sync/application/kline/sync_orchestrator.py`

### Pattern 4: Keep sync compatibility as a temporary adapter
**What:** Because CLI and `KLineCommandService` are still synchronous in Phase 2, expose async-first internals but keep sync entrypoints as thin adapters until Phase 4.
**When to use:** For `execute_kline_query()` and any callsites in `command.py` that cannot become async yet.
**Example:**
```python
def execute_kline_query(...):
    return asyncio.run(execute_kline_query_async(...))
```
Source: roadmap phase split and current sync callers in `command.py`

### Anti-Patterns to Avoid
- **Hand-rolled executor bridge:** Do not replace one custom thread abstraction with another. Use Phase 1 `query_kline_async()` instead.
- **Changing grouping semantics during async migration:** Do not fold, split, or reorder missing-range grouping logic unless a test proves equivalence.
- **Serial awaits in batch loops:** Awaiting each batch one-by-one will violate PERF-01 even if code is technically async.
- **Broad `except Exception` without symbol attribution:** The current code already maps failures back to symbols; async code must keep that behavior.
- **Sneaking sync SDK calls into coroutines:** Calling `amazing_data_client.query_kline()` directly inside an async function would block the event loop.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Concurrent batch aggregation | custom worker-thread manager | `asyncio.gather()` | Official, simpler, matches locked requirement |
| Concurrency limiting | custom token bucket / manual acquire-release plumbing | `asyncio.Semaphore` | Correct async primitive with context-manager support |
| SDK async adaptation | direct low-level executor submissions in orchestrator | `AmazingDataClient.query_kline_async()` | Keeps SDK-threading concerns in one boundary established in Phase 1 |
| Result normalization transport | new custom DTO hierarchy | existing `KlineQueryResult` / `KlineItemResult` / `KlineSyncResult` | Existing tests and callsites already understand these contracts |
| Data merge logic rewrite | custom row-level dedupe engine | current pandas concat + duplicated-index filtering | Existing semantics already match current behavior and are tested indirectly |

**Key insight:** Phase 2 should not invent a new orchestration framework. The safest path is to preserve business logic and swap only the concurrency primitive stack.

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None found in repo audit. Phase 2 changes orchestration only; it does not rename tables, keys, or persisted identifiers. | Code edit only; no data migration expected. |
| Live service config | `GALAXY_KLINE_MAX_CONCURRENT` is read from environment in `sync_orchestrator.py`; concurrency semantics must remain configurable. No external UI-managed service config found in repo. | Preserve env-var contract; no migration. |
| OS-registered state | None found. No systemd/pm2/cron/task registration artifacts for this phase are present in repo. | None. |
| Secrets/env vars | No new secrets required. Existing `.env`-style runtime config remains relevant, especially concurrency and AmazingData credentials. | Code edit only; do not rename existing env var usage in Phase 2. |
| Build artifacts | None phase-specific. No installed artifact name depends on thread-pool orchestration. | None. |

Interpretation: this migration changes control flow, not runtime identity. Planner should schedule code/test work, not data or environment migrations.

## Common Pitfalls

### Pitfall 1: Losing per-symbol failure attribution under `asyncio.gather`
**What goes wrong:** One failed batch becomes a generic exception and planners forget to map it back to the symbols in that batch.
**Why it happens:** `as_completed()` exposed futures keyed by batch, while naive `gather()` code often loses that key-to-symbol mapping.
**How to avoid:** Preserve a task-to-batch or positional batch map and convert exceptions back into `failed_codes.extend(range_groups[key])` semantics.
**Warning signs:** Failed symbol counts drop unexpectedly, or logs show batch failure without matching `failed_codes` output.

### Pitfall 2: Reintroducing duplicate rows when merging async batch results
**What goes wrong:** Multiple missing ranges for the same symbol produce duplicate timestamps or unsorted output.
**Why it happens:** Async completion order is nondeterministic; merge order must not affect dedupe semantics.
**How to avoid:** Keep the existing `pd.concat` + `~index.duplicated(keep="last")` + `sort_index()` pipeline exactly.
**Warning signs:** Same symbol returns more rows than expected or index order differs between test runs.

### Pitfall 3: Blocking the event loop with sync DB or SDK calls
**What goes wrong:** Code is labeled async but still blocks on direct sync client/service calls.
**Why it happens:** The repository is mid-migration; only the AmazingData wrapper is async-ready in Phase 2.
**How to avoid:** Only API fetch concurrency should move async in this phase; any unavoidable sync DB work stays before/after the gather step, not inside per-batch coroutines.
**Warning signs:** `query_kline()` is called directly from `async def`, or async tests show no concurrency gain despite multiple tasks.

### Pitfall 4: Semaphore not actually limiting batch concurrency
**What goes wrong:** All tasks start unbounded or the semaphore wraps only post-fetch processing instead of the network-bound call.
**Why it happens:** Misplacing `async with semaphore` around the wrong section of code.
**How to avoid:** Acquire the semaphore immediately before awaiting the async API call.
**Warning signs:** Concurrent-call counter in tests exceeds configured max; rate-limited SDK failures spike.

### Pitfall 5: Changing CLI behavior too early
**What goes wrong:** Phase 2 tries to make `handle_kline_command()` async before Phase 4, forcing test and callsite churn beyond scope.
**Why it happens:** Async migration pressure leaks across phase boundaries.
**How to avoid:** Keep sync command boundary in Phase 2; only make orchestration internals async-first.
**Warning signs:** Planner tasks start editing `application/cli/commands.py` or changing CLI invocation semantics.

## Code Examples

Verified patterns from official sources and current repo behavior:

### Async batch orchestration pattern
```python
semaphore = asyncio.Semaphore(max_concurrent)

async def fetch_single_batch_async(key, symbols):
    async with semaphore:
        return await query_kline_with_results_async(
            code_list=symbols,
            begin_date=key[0],
            end_date=key[1],
            interval=key[2],
        )

batch_results = await asyncio.gather(
    *(fetch_single_batch_async(key, symbols) for key, symbols in range_groups.items()),
    return_exceptions=True,
)
```
Source: Python 3.13 asyncio task and sync primitives docs; roadmap requirement for Phase 2

### Existing merge behavior to preserve
```python
if symbol in results and not results[symbol].empty:
    results[symbol] = pd.concat([results[symbol], df])
    results[symbol] = results[symbol][
        ~results[symbol].index.duplicated(keep="last")
    ]
    results[symbol].sort_index(inplace=True)
else:
    results[symbol] = df
```
Source: `/home/laniakea/Development/galaxy-db-sync/src/galaxy_db_sync/application/kline/sync_orchestrator.py`

### Existing async SDK boundary to reuse
```python
return await asyncio.to_thread(
    self.query_kline,
    code_list=code_list,
    begin_date=begin_date,
    end_date=end_date,
    interval=interval,
    begin_time=begin_time,
    end_time=end_time,
)
```
Source: `/home/laniakea/Development/galaxy-db-sync/src/galaxy_db_sync/amazing_data/api/client.py`

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `ThreadPoolExecutor` + `as_completed` in app-layer orchestrator | `asyncio.gather()` for awaitable aggregation | standard in current Python async docs | Simpler task orchestration and easier reuse of async client wrappers |
| `threading.Semaphore` for thread workers | `asyncio.Semaphore` for coroutine concurrency limiting | standard in current Python async docs | Correct non-blocking coordination primitive inside event loop |
| direct sync SDK invocation in orchestrator worker function | `asyncio.to_thread` hidden behind async client wrapper | already adopted in Phase 1 | Centralizes blocking-SDK adaptation and reduces leakage of thread concerns |

**Deprecated/outdated:**
- Custom executor-driven hot path in `sync_orchestrator.py`: outdated for this roadmap because it contradicts locked Phase 2 requirements.
- New direct uses of `threading.Semaphore` in async migration work: outdated because they block the event-loop model the roadmap requires.

## Open Questions

1. **Should Phase 2 add async versions alongside sync names, or replace implementations under existing names?**
   - What we know: `handle_kline_command()` and `KLineCommandService.get_kline()` are still sync callers in `command.py`.
   - What's unclear: whether planner prefers a temporary `*_async` dual surface or a hidden internal coroutine with sync adapter wrappers.
   - Recommendation: plan for async internals plus thin sync wrappers; defer public CLI async switch to Phase 4.

2. **Should `sync_kline_data()` also move to async now, or only `execute_kline_query()` hot path?**
   - What we know: roadmap success criteria focus on batch fetch hot path, while `sync_kline_data()` currently delegates mostly to synchronous DB service methods.
   - What's unclear: how much async value exists before Phase 3 moves DB writes async.
   - Recommendation: prioritize query/batch orchestration first; only async-ify `sync_kline_data()` if the planner can keep DB work outside fine-grained concurrent coroutines.

3. **How should exceptions be normalized in batch tasks?**
   - What we know: current code converts known SDK failures into `KlineQueryResult` item errors, but batch-level task failures still extend `failed_codes` directly.
   - What's unclear: whether to use `return_exceptions=True` or catch/normalize inside each task.
   - Recommendation: prefer task-local normalization for predictable return types; use `return_exceptions=True` only if batch-symbol mapping is explicitly preserved in tests.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python runtime in project venv | Async orchestrator implementation/tests | ✓ | 3.13.12 | — |
| `uv` | Dependency / venv workflow | ✓ | 0.11.3 | use existing `.venv` directly |
| `pytest` in project venv | Unit test execution | ✓ | 9.0.2 | — |
| `pytest-asyncio` in project venv | Async unit tests | ✓ | 1.3.0 | none; required for coroutine tests |
| `ruff` | Lint verification | ✗ on PATH during probe | — | use `.venv` tool or install via project dev deps |
| `mypy` | Type-check verification | ✗ on PATH during probe | — | use `.venv` tool or install via project dev deps |

**Missing dependencies with no fallback:**
- None. Async test support is available in `.venv`.

**Missing dependencies with fallback:**
- `ruff` and `mypy` were not on shell PATH, but project workflow can invoke them from the virtualenv after `uv pip install -e ".[dev,format]"`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `/home/laniakea/Development/galaxy-db-sync/pyproject.toml` |
| Quick run command | `.venv/bin/pytest tests/unit/test_execute_kline_query.py -q` |
| Full suite command | `.venv/bin/pytest tests/` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ASYNC-02 | async batch orchestration uses `gather` + `Semaphore` | unit | `.venv/bin/pytest tests/unit/test_async_sync_orchestrator.py -q` | ❌ Wave 0 |
| TEST-01 | success / partial failure / empty result async paths are covered | unit | `.venv/bin/pytest tests/unit/test_async_sync_orchestrator.py -q` | ❌ Wave 0 |
| PERF-01 | concurrency cap remains configurable and respected | unit | `.venv/bin/pytest tests/unit/test_async_sync_orchestrator.py -q -k semaphore` | ❌ Wave 0 |
| DATA-01 | merged DataFrames preserve dedupe/sort/failure semantics | unit | `.venv/bin/pytest tests/unit/test_async_sync_orchestrator.py -q -k merge` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/unit/test_async_sync_orchestrator.py -q`
- **Per wave merge:** `.venv/bin/pytest tests/unit/test_execute_kline_query.py tests/kline/test_kline_command.py tests/unit/test_kline_data_sync.py -q`
- **Phase gate:** `.venv/bin/pytest tests/` plus lint/type checks green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_async_sync_orchestrator.py` — new async orchestrator coverage for REQ-ASYNC-02 / TEST-01 / PERF-01 / DATA-01
- [ ] AsyncMock-based fixtures/helpers for `AmazingDataClient.query_kline_async` and per-batch concurrency tracking
- [ ] Explicit tests proving exception-to-`failed_codes` mapping survives gather-based execution
- [ ] Explicit tests proving same-symbol multi-range merge still dedupes and sorts identically under nondeterministic completion order
- [ ] Optional sync-wrapper regression test if existing `execute_kline_query()` becomes a bridge to async internals

## Sources

### Primary (HIGH confidence)
- Repository source: `/home/laniakea/Development/galaxy-db-sync/src/galaxy_db_sync/application/kline/sync_orchestrator.py` — current executor/semaphore hot path, grouping, merge, failure semantics
- Repository source: `/home/laniakea/Development/galaxy-db-sync/src/galaxy_db_sync/amazing_data/api/client.py` — existing `query_kline_async()` boundary via `asyncio.to_thread`
- Repository source: `/home/laniakea/Development/galaxy-db-sync/tests/unit/test_execute_kline_query.py` — current merge and empty-range behavior already under test
- Repository source: `/home/laniakea/Development/galaxy-db-sync/tests/unit/test_kline_data_sync.py` — empty-query cache and batch grouping semantics to preserve
- Python docs: https://docs.python.org/3.13/library/asyncio-task.html — official semantics for `asyncio.gather()` and `asyncio.to_thread()`
- Python docs: https://docs.python.org/3.13/library/asyncio-sync.html — official semantics for `asyncio.Semaphore`

### Secondary (MEDIUM confidence)
- pytest-asyncio configuration docs: https://pytest-asyncio.readthedocs.io/en/stable/reference/configuration.html — confirms `asyncio_mode = auto` and fixture loop-scope behavior used by project test config
- Project roadmap: `/home/laniakea/Development/galaxy-db-sync/.planning/ROADMAP.md` — locked success criteria for Phase 2
- Project requirements: `/home/laniakea/Development/galaxy-db-sync/.planning/REQUIREMENTS.md` — locked requirement mapping for ASYNC-02 / TEST-01 / PERF-01 / DATA-01
- Local lockfile and registry data: `/home/laniakea/Development/galaxy-db-sync/uv.lock` plus PyPI JSON queries — package versions and release dates

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - primarily based on current repo state, locked roadmap requirements, and official Python/pytest-asyncio docs
- Architecture: HIGH - current orchestrator code and callsites clearly show where the phase boundary is and what semantics must remain stable
- Pitfalls: HIGH - derived from concrete current implementation details plus official async primitive semantics

**Research date:** 2026-04-07
**Valid until:** 2026-05-07
