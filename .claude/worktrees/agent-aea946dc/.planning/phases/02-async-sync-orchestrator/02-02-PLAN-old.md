---
phase: 02-async-sync-orchestrator
plan: 02
type: execute
wave: 2
depends_on:
  - 02-01
files_modified:
  - src/galaxy_db_sync/application/kline/sync_orchestrator.py
  - tests/unit/test_execute_kline_query.py
  - tests/kline/test_kline_command.py
autonomous: true
requirements:
  - ASYNC-02
  - TEST-01
  - DATA-01
must_haves:
  truths:
    - "兼容查询入口 execute_kline_query 通过 async orchestrator 获取 API 数据，同时保留当前同步调用方式"
    - "缺失区间分组、空查询缓存跳过、失败代码收集与合并去重排序行为保持一致"
    - "CLI 命令层无需变成 async 仍可复用新的异步编排内部实现"
  artifacts:
    - path: "src/galaxy_db_sync/application/kline/sync_orchestrator.py"
      provides: "sync adapter around async execute_kline_query_async"
      contains: "asyncio.run"
    - path: "tests/unit/test_execute_kline_query.py"
      provides: "compatibility regression for execute_kline_query async bridge"
      contains: "execute_kline_query_async"
    - path: "tests/kline/test_kline_command.py"
      provides: "command-layer regression that sync entrypoints still invoke orchestrator successfully"
      contains: "sync_kline_data"
  key_links:
    - from: "src/galaxy_db_sync/application/kline/command.py"
      to: "src/galaxy_db_sync/application/kline/sync_orchestrator.py"
      via: "execute_kline_query and sync_kline_data imports"
      pattern: "from \.sync_orchestrator import sync_kline_data, execute_kline_query"
    - from: "src/galaxy_db_sync/application/kline/sync_orchestrator.py"
      to: "galaxy_db_sync.database.services.kline.kline_service.merge_db_and_api_data"
      via: "final data merge after async fetch"
      pattern: "merge_db_and_api_data"
---

<objective>
Wire the async orchestrator into the existing synchronous query surface without changing CLI behavior.

Purpose: Finish the Phase 2 hot-path migration by routing `execute_kline_query()` through async internals while preserving completeness-first logic, empty-range skipping, failure handling, and command compatibility per ASYNC-02, TEST-01, and DATA-01.
Output: Async execution function plus a thin sync adapter, with updated unit/command regressions proving behavior parity.
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
@.planning/phases/02-async-sync-orchestrator/02-01-PLAN.md
@src/galaxy_db_sync/application/kline/command.py
@src/galaxy_db_sync/application/kline/sync_orchestrator.py
@tests/unit/test_execute_kline_query.py
@tests/kline/test_kline_command.py

<interfaces>
From src/galaxy_db_sync/application/kline/command.py:
```python
def handle_kline_command(args: argparse.Namespace) -> int:
    ...

class KLineCommandService:
    def get_kline(
        self,
        symbol: str,
        interval: "Interval",
        start_date: Optional[str],
        end_date: Optional[str],
        fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
```

From src/galaxy_db_sync/application/kline/sync_orchestrator.py:
```python
def execute_kline_query(
    symbol_list: list[str],
    interval: str,
    start_date: str | None,
    end_date: str | None,
    interval_value: int,
    max_concurrent: int | None = None,
) -> dict:
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Route execute_kline_query through async internals with sync compatibility</name>
  <files>src/galaxy_db_sync/application/kline/sync_orchestrator.py, tests/unit/test_execute_kline_query.py</files>
  <read_first>
    - src/galaxy_db_sync/application/kline/sync_orchestrator.py
    - tests/unit/test_execute_kline_query.py
    - tests/unit/test_async_sync_orchestrator.py
    - src/galaxy_db_sync/application/kline/command.py
    - .planning/phases/02-async-sync-orchestrator/02-RESEARCH.md
  </read_first>
  <behavior>
    - Test 1: `execute_kline_query_async(...)` returns merged DB+API data with the same missing-range grouping and empty-range skipping as the old sync implementation
    - Test 2: `execute_kline_query(...)` becomes a thin sync wrapper that delegates to `asyncio.run(execute_kline_query_async(...))`
    - Test 3: `GALAXY_KLINE_MAX_CONCURRENT` still controls concurrency when `max_concurrent` is omitted
  </behavior>
  <action>Update `tests/unit/test_execute_kline_query.py` first so it asserts the new internal contract: patch `query_kline_with_results_async` or `batch_fetch_kline_data_async` instead of the removed thread-pool helpers, add a regression that `execute_kline_query()` calls `asyncio.run()` with the coroutine produced by `execute_kline_query_async(...)`, and keep existing coverage for multi-range merge and confirmed-empty skips. Then update `src/galaxy_db_sync/application/kline/sync_orchestrator.py` to add `async def execute_kline_query_async(...) -> dict[str, pd.DataFrame]` that preserves the current order of operations: read DB data synchronously before gather, run `kline_completeness_checker.check(...)` per symbol, build `range_groups` via `group_symbols_by_missing_ranges(...)`, await `batch_fetch_kline_data_async(...)`, log failed codes, and finally call `kline_service.merge_db_and_api_data(db_data, api_data)`.</action>
  <verify>
    <automated>.venv/bin/pytest /home/laniakea/Development/galaxy-db-sync/tests/unit/test_execute_kline_query.py /home/laniakea/Development/galaxy-db-sync/tests/unit/test_async_sync_orchestrator.py -q</automated>
  </verify>
  <acceptance_criteria>
    - `src/galaxy_db_sync/application/kline/sync_orchestrator.py` contains `async def execute_kline_query_async`
    - `src/galaxy_db_sync/application/kline/sync_orchestrator.py` contains `return asyncio.run(`
    - `src/galaxy_db_sync/application/kline/sync_orchestrator.py` contains `batch_fetch_kline_data_async`
    - `tests/unit/test_execute_kline_query.py` contains `execute_kline_query_async`
    - `tests/unit/test_execute_kline_query.py` contains `asyncio.run`
    - `src/galaxy_db_sync/application/kline/sync_orchestrator.py` does not contain `batch_fetch_kline_data(` as the hot-path caller inside `execute_kline_query`
  </acceptance_criteria>
  <done>The compatibility query path is async internally and sync externally, with regressions proving no behavior drift in grouping, empty-range skipping, or merged result shape.</done>
</task>

<task type="auto">
  <name>Task 2: Prove command-layer compatibility against the async bridge</name>
  <files>tests/kline/test_kline_command.py</files>
  <read_first>
    - tests/kline/test_kline_command.py
    - src/galaxy_db_sync/application/kline/command.py
    - src/galaxy_db_sync/application/kline/sync_orchestrator.py
    - tests/unit/test_execute_kline_query.py
  </read_first>
  <action>Extend `tests/kline/test_kline_command.py` only where Phase 2 behavior is observable from the sync command boundary. Add or update regression coverage so `KLineCommandService.get_kline(...)` still calls `execute_kline_query(...)` with `interval` naming and resolved SDK interval value, and `handle_kline_command(...)` continues to call `sync_kline_data(...)` only when completeness is not full. If any existing assertion patches old thread-pool details, replace it with compatibility assertions on the public sync functions only. Do not make `handle_kline_command` async and do not edit `application/cli/commands.py` in this phase.</action>
  <verify>
    <automated>.venv/bin/pytest /home/laniakea/Development/galaxy-db-sync/tests/kline/test_kline_command.py /home/laniakea/Development/galaxy-db-sync/tests/unit/test_execute_kline_query.py -q && .venv/bin/ruff check /home/laniakea/Development/galaxy-db-sync/src/galaxy_db_sync/application/kline/sync_orchestrator.py /home/laniakea/Development/galaxy-db-sync/tests/unit/test_execute_kline_query.py /home/laniakea/Development/galaxy-db-sync/tests/kline/test_kline_command.py && .venv/bin/mypy /home/laniakea/Development/galaxy-db-sync/src/galaxy_db_sync/application/kline/sync_orchestrator.py /home/laniakea/Development/galaxy-db-sync/src/galaxy_db_sync/application/kline/command.py</automated>
  </verify>
  <acceptance_criteria>
    - `tests/kline/test_kline_command.py` still contains `mock_sync_data.assert_called_once_with`
    - `tests/kline/test_kline_command.py` still contains `mock_execute.assert_called_once_with`
    - `tests/kline/test_kline_command.py` does not require `handle_kline_command` to be awaited
    - `tests/kline/test_kline_command.py` does not import `ThreadPoolExecutor`
  </acceptance_criteria>
  <done>Command-level regression coverage demonstrates that Phase 2 changed orchestration internals only, not the synchronous CLI/programmatic contract.</done>
</task>

</tasks>

<verification>
Run the orchestrator and command regression suites together to prove the sync entrypoints still work while the hot fetch path now routes through async internals.
</verification>

<success_criteria>
- `execute_kline_query_async` exists and is the implementation behind the synchronous compatibility wrapper.
- Existing query semantics for grouped missing ranges, empty-range skipping, and merged output remain covered by tests.
- Command-layer tests stay synchronous and green, confirming Phase 4 CLI work has not leaked into Phase 2.
</success_criteria>

<output>
After completion, create `.planning/phases/02-async-sync-orchestrator/02-02-SUMMARY.md`
</output>
