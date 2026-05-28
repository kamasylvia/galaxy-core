---
phase: 02-async-sync-orchestrator
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/unit/test_async_sync_orchestrator.py
  - src/galaxy_db_sync/application/kline/sync_orchestrator.py
autonomous: true
requirements:
  - ASYNC-02
  - TEST-01
  - PERF-01
must_haves:
  truths:
    - "批量补齐缺失 K 线时，多 symbol / 多缺失区间结果在异步执行下仍会被完整合并并返回给调用方"
    - "配置 `GALAXY_KLINE_MAX_CONCURRENT` 后，异步批量抓取的峰值并发不会超过设定上限"
    - "部分批次失败时，调用方仍能拿到成功 symbol 的结果，失败 symbol 会被准确汇总到 failed_codes"
  artifacts:
    - path: "tests/unit/test_async_sync_orchestrator.py"
      provides: "async orchestrator success/failure/semaphore/merge regression coverage"
      contains: "async def"
    - path: "src/galaxy_db_sync/application/kline/sync_orchestrator.py"
      provides: "async batch fetch helpers and async query result wrapper"
      contains: "asyncio.gather"
  key_links:
    - from: "src/galaxy_db_sync/application/kline/sync_orchestrator.py"
      to: "galaxy_db_sync.amazing_data.api.client.AmazingDataClient.query_kline_async"
      via: "await amazing_data_client.query_kline_async"
      pattern: "query_kline_async"
    - from: "src/galaxy_db_sync/application/kline/sync_orchestrator.py"
      to: "tests/unit/test_async_sync_orchestrator.py"
      via: "pytest async regression coverage"
      pattern: "test_.*semaphore|test_.*merge"
---

<objective>
Stabilize the async batch-fetch contract for the Phase 2 orchestrator before the sync adapter is rewired.

Purpose: Replace the thread-pool hot path with explicit async helpers while proving semaphore limits, batch failure mapping, and deterministic merge behavior per ASYNC-02, TEST-01, and PERF-01.
Output: New async orchestrator regression tests plus async helper functions in `sync_orchestrator.py` that downstream work can call directly.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/02-async-sync-orchestrator/02-RESEARCH.md
@.planning/phases/02-async-sync-orchestrator/02-VALIDATION.md
@.planning/phases/01-async-api-client-wrapper/01-02-SUMMARY.md
@src/galaxy_db_sync/application/kline/sync_orchestrator.py
@src/galaxy_db_sync/amazing_data/api/client.py
@tests/unit/test_execute_kline_query.py

<interfaces>
From src/galaxy_db_sync/application/kline/result.py:
```python
@dataclass
class KlineItemResult:
    code: str
    success: bool
    data: Optional[pd.DataFrame]
    error: Optional[KlineError] = None
    interval: Optional[str] = None

@dataclass
class KlineQueryResult:
    results: Dict[str, KlineItemResult]
```

From src/galaxy_db_sync/amazing_data/api/client.py:
```python
async def query_kline_async(
    self,
    code_list: list[str],
    begin_date: int,
    end_date: int,
    interval: int,
    begin_time: int | None = None,
    end_time: int | None = None,
) -> dict[str, pd.DataFrame]:
```

From src/galaxy_db_sync/application/kline/sync_orchestrator.py:
```python
def group_symbols_by_missing_ranges(
    completeness_results: dict,
    interval: str,
    interval_value: int,
) -> dict[tuple[int, int, int], list[str]]:
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create async orchestrator regression scaffold</name>
  <files>tests/unit/test_async_sync_orchestrator.py</files>
  <read_first>
    - tests/unit/test_execute_kline_query.py
    - tests/unit/test_kline_data_sync.py
    - src/galaxy_db_sync/application/kline/sync_orchestrator.py
    - src/galaxy_db_sync/application/kline/result.py
    - .planning/phases/02-async-sync-orchestrator/02-RESEARCH.md
    - .planning/phases/02-async-sync-orchestrator/02-VALIDATION.md
  </read_first>
  <action>Create `tests/unit/test_async_sync_orchestrator.py` with async pytest coverage for the new coroutine helpers described in research. Add explicit tests for: (1) one coroutine per grouped missing range merged back into one symbol result with `pd.concat`, `~index.duplicated(keep="last")`, and `sort_index()` semantics preserved; (2) batch exception normalization extending `failed_codes` with every symbol in the failed batch; (3) semaphore-limited concurrency by instrumenting an `AsyncMock`/counter around the awaited API call and asserting the peak concurrent count never exceeds `max_concurrent=2`; (4) empty or error item results returning failed symbols without crashing gather. Use `pytest.mark.asyncio` or plain `async def` tests compatible with `asyncio_mode = auto`.   <verify>
    <automated>.venv/bin/pytest /home/laniakea/Development/galaxy-db-sync/tests/unit/test_async_sync_orchestrator.py -q</automated>
  </verify>
  <acceptance_criteria>
    - `tests/unit/test_async_sync_orchestrator.py` exists
    - file contains `async def test_async_batch`
    - file contains `semaphore` and `failed_codes`
    - file contains assertions against `duplicated(keep="last")` behavior or resulting sorted index order
  </acceptance_criteria>
  <done>Wave 0 coverage exists for the async helpers, and the file can fail meaningfully before production rewiring begins.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add async batch fetch helpers in sync_orchestrator.py</name>
  <files>src/galaxy_db_sync/application/kline/sync_orchestrator.py</files>
  <read_first>
    - src/galaxy_db_sync/application/kline/sync_orchestrator.py
    - src/galaxy_db_sync/amazing_data/api/client.py
    - src/galaxy_db_sync/application/kline/result.py
    - .planning/phases/02-async-sync-orchestrator/02-RESEARCH.md
    - .planning/phases/02-async-sync-orchestrator/02-VALIDATION.md
    - tests/unit/test_async_sync_orchestrator.py
  </read_first>
  <behavior>
    - Test 1: grouped batches are awaited concurrently through `asyncio.gather` and return merged `{symbol: DataFrame}` data plus `failed_codes`
    - Test 2: `asyncio.Semaphore(max_concurrent)` wraps the awaited `amazing_data_client.query_kline_async(...)` call so peak in-flight batch count never exceeds the configured value
    - Test 3: if one batch raises or returns unsuccessful item results, every symbol from that batch is added to `failed_codes` while successful batches still contribute data
  </behavior>
  <action>Refactor `src/galaxy_db_sync/application/kline/sync_orchestrator.py` to introduce async-first helpers without changing CLI entrypoints yet: add `import asyncio` and remove thread-pool imports from the hot path; keep `group_symbols_by_missing_ranges()` unchanged except for typing cleanup; add `async def query_kline_with_results_async(...) -> KlineQueryResult` that awaits `amazing_data_client.query_kline_async(code_list=..., begin_date=..., end_date=..., interval=..., begin_time=..., end_time=...)` and preserves the exact current error normalization for known `TypeError`, `SDKError`, generic exceptions, empty data, and invalid symbols; add `async def fetch_single_batch_async(key, symbols, semaphore)` that acquires `asyncio.Semaphore` immediately before awaiting `query_kline_with_results_async`; add `async def batch_fetch_kline_data_async(range_groups, max_concurrent=5)` that uses `asyncio.gather` over all batches, merges per-symbol DataFrames with the existing `pd.concat` + duplicated-index drop + `sort_index()` pipeline, and extends `failed_codes` deterministically. Do not edit `sync_kline_data()` or CLI code in this plan. Do not reintroduce `ThreadPoolExecutor`, `as_completed`, or `threading.Semaphore` anywhere in the async path. Finish with the validation contract from `02-VALIDATION.md`: async unit tests green, then `ruff check` on the touched source/test files, then `mypy` on `sync_orchestrator.py`.</action>
  <verify>
    <automated>.venv/bin/pytest /home/laniakea/Development/galaxy-db-sync/tests/unit/test_async_sync_orchestrator.py -q && .venv/bin/ruff check /home/laniakea/Development/galaxy-db-sync/src/galaxy_db_sync/application/kline/sync_orchestrator.py /home/laniakea/Development/galaxy-db-sync/tests/unit/test_async_sync_orchestrator.py && .venv/bin/mypy /home/laniakea/Development/galaxy-db-sync/src/galaxy_db_sync/application/kline/sync_orchestrator.py</automated>
  </verify>
  <acceptance_criteria>
    - `src/galaxy_db_sync/application/kline/sync_orchestrator.py` contains `async def query_kline_with_results_async`
    - `src/galaxy_db_sync/application/kline/sync_orchestrator.py` contains `async def fetch_single_batch_async`
    - `src/galaxy_db_sync/application/kline/sync_orchestrator.py` contains `async def batch_fetch_kline_data_async`
    - `src/galaxy_db_sync/application/kline/sync_orchestrator.py` contains `asyncio.gather`
    - `src/galaxy_db_sync/application/kline/sync_orchestrator.py` contains `asyncio.Semaphore`
    - `src/galaxy_db_sync/application/kline/sync_orchestrator.py` contains `await amazing_data_client.query_kline_async`
    - `src/galaxy_db_sync/application/kline/sync_orchestrator.py` does not contain `ThreadPoolExecutor`
    - `src/galaxy_db_sync/application/kline/sync_orchestrator.py` does not contain `as_completed`
    - `src/galaxy_db_sync/application/kline/sync_orchestrator.py` does not contain `threading.Semaphore`
  </acceptance_criteria>
  <done>The module exposes tested async batch-fetch primitives that preserve current data merge and failure semantics while satisfying the locked async concurrency design.</done>
</task>

</tasks>

<verification>
Follow `02-VALIDATION.md` for this plan: run `.venv/bin/pytest tests/unit/test_async_sync_orchestrator.py -q`, then `.venv/bin/ruff check src/galaxy_db_sync/application/kline/sync_orchestrator.py tests/unit/test_async_sync_orchestrator.py`, then `.venv/bin/mypy src/galaxy_db_sync/application/kline/sync_orchestrator.py`.
</verification>

<success_criteria>
- Async helper coverage exists for success, partial failure, merge, and semaphore limits.
- `sync_orchestrator.py` contains async helpers built on `query_kline_async`, `asyncio.gather`, and `asyncio.Semaphore`.
- No thread-pool primitives remain in the batch-fetch implementation introduced by this plan.
</success_criteria>

<output>
After completion, create `.planning/phases/02-async-sync-orchestrator/02-01-SUMMARY.md`
</output>
