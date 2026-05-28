# Phase 1: Async API Client Wrapper - Research

**Researched:** 2026-04-06
**Domain:** AmazingData synchronous SDK wrapper boundary for async application code
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
## Implementation Decisions

### Phase boundary
- **D-01:** 本 phase 按“重做 client 面”规划，不把当前已有 async 方法仅视为补洞对象。
- **D-02:** Phase 1 只处理 `AmazingDataClient` 这一层，不把 orchestrator / DB / CLI 异步化混入本 phase。

### Async surface coverage
- **D-03:** Phase 1 的目标是收敛 `AmazingDataClient` 的**全公开读取面**，而不只覆盖 K 线当前主链路。
- **D-04:** 所有公开读取接口都应具备统一风格的 async 对等方法，避免后续 phase 再回头补 client 面。
- **D-05:** `AmazingDataClient` 是调用 AmazingData 同步 SDK 的唯一 async 包装边界；上层不应各自重复 `to_thread` 包装 SDK。

### Testing standard
- **D-06:** 测试按“边界级强化”执行，不满足于仅验证 async 方法能调用成功。
- **D-07:** Phase 1 测试必须明确覆盖 `asyncio.to_thread` 使用、参数透传、可选参数桥接、异常传播和并发不阻塞语义。
- **D-08:** 测试优先锁定 client wrapper 边界，不把本 phase 扩成 orchestrator / CLI 集成测试。

### Compatibility strategy
- **D-09:** Phase 1 采用 **async 优先切换** 策略，而不是长期保持 sync/async 并行对等地位。
- **D-10:** planner 应把同步接口视为过渡兼容层，而不是长期主接口；后续 phase 可以围绕 async client 面直接规划调用方迁移。

### Claude's Discretion
- 哪些公开方法属于“读取面”可在规划时结合 `AmazingDataClient` 现有 public API 精确归类
- async 方法命名保持 `<sync_name>_async` 还是做更激进重整，只要不破坏 Phase 1 已锁定目标
- 测试中对 `asyncio.to_thread` 的断言方式可按 pytest/mock 最稳妥方案决定

### Deferred Ideas (OUT OF SCOPE)
## Deferred Ideas

- orchestrator 的 `asyncio.gather` / `asyncio.Semaphore` 改造 — 属于 Phase 2
- SQLAlchemy async / AsyncDatabaseManager / DI 改造 — 属于 Phase 3
- CLI `asyncio.run()` 入口收口 — 属于 Phase 4
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ASYNC-01 | AmazingData client 提供 async 包装接口，并通过 `asyncio.to_thread` 调用同步 SDK | Defines the complete public read surface that still lacks async parity and standardizes `to_thread` as the only SDK async boundary |
| COMPAT-01 | 保持现有 CLI 参数、输出摘要和调用方式兼容 | Recommends preserving existing sync methods as a compatibility layer while moving planning and downstream design to async-first usage |
| TEST-01 | 为新增 async API / service / orchestrator / CLI 路径补齐单元测试 | Narrows Phase 1 tests to client-boundary tests and identifies concrete missing assertions around `to_thread`, parameter bridging, exception propagation, and concurrency semantics |
</phase_requirements>

## Summary

Phase 1 should be planned as a deliberate rework of the `AmazingDataClient` async surface, not as a light audit of four already-added methods. The current codebase already exposes `get_hist_code_list_async`, `get_stock_list_async`, `get_listing_dates_async`, and `query_kline_async`, but the public read API on the sync side is broader: `get_trading_calendar`, `get_backward_factor`, `query_snapshot`, `get_balance_sheet`, `get_income_statement`, and `get_cash_flow` still have no async counterparts. Given the locked decision that Phase 1 must cover the full public read surface, parity is incomplete today.

The right planning stance is: keep `AmazingDataClient` as the only place that knows the SDK is synchronous, wrap sync methods with `asyncio.to_thread`, and make tests prove that boundary instead of merely proving that async methods return mocked values. Current tests mostly patch the sync wrapper methods and assert call-through; that is useful smoke coverage, but it does not yet prove the critical properties the user asked to lock down: actual `to_thread` usage, optional parameter bridging, exception behavior, and non-blocking concurrency semantics.

The most important practical finding is environmental: the project virtualenv is present and has Python 3.13.12, pytest 9.0.2, pytest-asyncio 1.3.0, ruff 0.15.5, and mypy 1.19.1 installed, but importing `AmazingData` in the venv currently fails because `scipy` is missing. Since `src/galaxy_db_sync/amazing_data/api/client.py` imports `AmazingData as ad` at module import time, planner tasks should assume that unit tests may need an import-isolation strategy or environment repair before tests can run reliably.

**Primary recommendation:** Plan Phase 1 around completing async parity for every public read method on `AmazingDataClient`, then harden the boundary with tests that assert `asyncio.to_thread` behavior directly and preserve sync methods only as a compatibility layer.

## Project Constraints (from CLAUDE.md)

- Use repository commands and conventions from `/home/laniakea/Development/galaxy-db-sync/CLAUDE.md`.
- Keep Phase 1 scoped to the AmazingData SDK wrapper layer; do not mix in orchestrator, database, or CLI async migration.
- Preserve internal naming convention: use `interval` everywhere except the literal `period` argument passed into the SDK call.
- Do not hardcode SDK interval values; use the established runtime mapping rules and preserve the no-hardcoded-periods discipline.
- Tests should rely heavily on mocking rather than real database/API calls.
- Integration tests require real database access; unit tests should stay isolated.
- Sensitive configuration belongs in `.env` and must not be committed.
- Existing architecture patterns matter for planning: singleton `AmazingDataClient`, lazy initialization, and centralized SDK wrapping are already project conventions.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.13.12 | Runtime for async wrapper implementation | Project requires Python `>=3.13,<3.14`; async surface is built on stdlib asyncio |
| asyncio | stdlib (Python 3.13) | `async`/`await` runtime and `asyncio.to_thread` wrapper boundary | Standard way to bridge blocking sync calls into async code without redesigning the private SDK |
| AmazingData | 1.0.26 wheel | Private synchronous market-data SDK | This is the fixed vendor boundary; Phase 1 wraps it rather than replacing it |
| pandas | project dependency (`>=2.0.0`) | Return type for several read APIs | Existing client surface already returns `DataFrame` objects; planner should preserve this contract |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.2 | Unit test runner | For all Phase 1 boundary tests |
| pytest-asyncio | 1.3.0 | Async test support for coroutine tests | Use for `async def` tests and event-loop driven assertions |
| unittest.mock | stdlib | Patching sync methods, SDK objects, and `asyncio.to_thread` call sites | Use for precise wrapper-boundary assertions |
| ruff | 0.15.5 | Lint/format verification | Use on any touched test/client files |
| mypy | 1.19.1 | Type checking | Use to catch async signature drift and return type mismatch |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `asyncio.to_thread` wrapper in client layer | ThreadPoolExecutor or custom worker plumbing in upper layers | Violates locked boundary decision and spreads SDK-threading concerns across orchestrator/CLI code |
| Full async SDK rewrite | Native async HTTP client around vendor API | Not feasible in this phase; SDK is private and already integrated deeply |
| Long-term sync/async co-equal APIs | Async-first migration with sync retained temporarily | User explicitly chose async-first direction; sync should remain transitional only |

**Installation / environment verification:**
```bash
/home/laniakea/Development/galaxy-db-sync/.venv/bin/python --version
/home/laniakea/Development/galaxy-db-sync/.venv/bin/pytest --version
/home/laniakea/Development/galaxy-db-sync/.venv/bin/ruff --version
/home/laniakea/Development/galaxy-db-sync/.venv/bin/mypy --version
```

**Version verification:** Versions above were verified against the project virtualenv, `pyproject.toml`, `uv.lock`, and the bundled AmazingData wheel at `/home/laniakea/Development/galaxy-db-sync/wheels/AmazingData-1.0.26-cp313-none-any.whl`. Network-based registry verification was not available during research, so confidence is highest for project-pinned versions, not ecosystem-latest claims.

## Architecture Patterns

### Recommended Project Structure
```text
src/galaxy_db_sync/
└── amazing_data/api/
    ├── client.py        # sync methods + async wrapper boundary
    └── lazy_client.py   # lazy initialization stays unchanged in this phase

tests/
└── amazing_data/
    └── test_async_client.py   # boundary-level async wrapper tests
```

### Pattern 1: Thin async wrapper over sync method
**What:** Each async public read method should delegate to the existing sync method with `await asyncio.to_thread(...)`, not reimplement SDK calls.
**When to use:** For every `AmazingDataClient` public read API that ultimately calls the synchronous AmazingData SDK.
**Example:**
```python
async def query_kline_async(
    self,
    code_list: list[str],
    begin_date: int,
    end_date: int,
    interval: int,
    begin_time: int = None,
    end_time: int = None,
) -> dict[str, pd.DataFrame]:
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

### Pattern 2: Preserve sync semantics by reusing sync methods
**What:** Async methods should inherit parameter handling, logging, and exception mapping by calling the sync method rather than duplicating logic.
**When to use:** Always, unless a sync method is itself malformed and needs repair first.
**Why:** This is the cleanest path to `COMPAT-01`; one behavior definition, two call surfaces.

### Pattern 3: Full public read-surface parity
**What:** Treat every public read method on `AmazingDataClient` as part of the async boundary, not just the currently-used K-line methods.
**When to use:** Phase 1 planning and task decomposition.
**Public read methods found:**
- Already async: `get_hist_code_list`, `get_stock_list`, `get_listing_dates`, `query_kline`
- Missing async parity: `get_trading_calendar`, `get_backward_factor`, `query_snapshot`, `get_balance_sheet`, `get_income_statement`, `get_cash_flow`

### Anti-Patterns to Avoid
- **Hand-wrapping SDK calls in orchestrator/service code:** Breaks the locked boundary and duplicates threading concerns.
- **Duplicating sync logic inside async methods:** Creates behavior drift between sync and async paths.
- **Planning only around current K-line callers:** Violates the locked “full public read surface” decision.
- **Testing only happy-path call-through:** Misses the exact boundary failures this phase exists to prevent.
- **Importing the real SDK in unit tests without isolation:** Current environment shows the SDK import path is fragile due to missing dependencies.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async bridge for sync SDK | Custom thread manager / queue / executor orchestration per call site | `asyncio.to_thread` inside `AmazingDataClient` | Standard, minimal, and keeps the boundary centralized |
| Async test harness | Ad-hoc event loop setup in every test | `pytest` + `pytest-asyncio` | Already configured in the project via `asyncio_mode = auto` |
| Wrapper assertions | Timing-only concurrency guesses | Direct patch/assertion on `asyncio.to_thread` and sync methods | Gives deterministic proof of wrapper behavior |
| Exception translation in async methods | New async-only exception hierarchy | Reuse sync method exception mapping | Prevents compatibility drift |

**Key insight:** The hard part is not “making methods awaitable”; it is enforcing one authoritative wrapper boundary so later phases never need to know the vendor SDK is synchronous.

## Common Pitfalls

### Pitfall 1: Mistaking partial parity for complete parity
**What goes wrong:** Planning assumes Phase 1 is nearly done because four async methods already exist.
**Why it happens:** Existing tests and draft research focus on K-line-adjacent methods only.
**How to avoid:** Inventory the whole public read surface before tasking.
**Warning signs:** Planner tasks mention only `query_kline_async`, `get_stock_list_async`, and `get_listing_dates_async`.

### Pitfall 2: Tests prove call-through, not boundary correctness
**What goes wrong:** Tests pass even if `asyncio.to_thread` is removed or bypassed.
**Why it happens:** Current tests patch sync methods and assert they were called, but do not assert the `to_thread` boundary directly.
**How to avoid:** Add tests that patch `asyncio.to_thread` or otherwise verify the wrapper delegates through it with the correct callable and kwargs.
**Warning signs:** Test suite never mentions `asyncio.to_thread`.

### Pitfall 3: Async wrapper silently drifts from sync semantics
**What goes wrong:** Optional args, exception behavior, or naming conventions differ between sync and async methods.
**Why it happens:** Async method copies logic instead of calling the sync method.
**How to avoid:** Keep async methods thin and route through sync methods.
**Warning signs:** Async implementations contain SDK calls directly or duplicate parameter-building code.

### Pitfall 4: Import-time SDK fragility blocks tests
**What goes wrong:** Client module import fails before tests can patch anything.
**Why it happens:** `client.py` imports `AmazingData as ad` at module import time; in the current venv, importing `AmazingData` fails because `scipy` is missing.
**How to avoid:** Plan either environment repair or import-isolation/monkeypatch strategy in Wave 0.
**Warning signs:** `ModuleNotFoundError` or transitive import failures before test collection completes.

### Pitfall 5: Async-first direction gets diluted into indefinite dual maintenance
**What goes wrong:** Planner treats sync and async APIs as permanent equal peers, increasing future migration cost.
**Why it happens:** Backward compatibility is mistaken for long-term architectural preference.
**How to avoid:** Keep sync methods callable for compatibility, but plan downstream phases against the async surface.
**Warning signs:** Future tasks continue introducing new sync-first call paths.

## Code Examples

Verified patterns from project sources:

### Existing wrapper pattern
```python
async def get_stock_list_async(self, security_type: str = "EXTRA_STOCK_A") -> pd.DataFrame:
    return await asyncio.to_thread(
        self.get_stock_list,
        security_type=security_type,
    )
```
Source: `/home/laniakea/Development/galaxy-db-sync/src/galaxy_db_sync/amazing_data/api/client.py`

### Existing sync-to-SDK interval bridge
```python
query_kwargs = {
    "code_list": code_list,
    "begin_date": begin_date,
    "end_date": end_date,
    "period": interval,
}

if begin_time is not None:
    query_kwargs["begin_time"] = begin_time
if end_time is not None:
    query_kwargs["end_time"] = end_time
```
Source: `/home/laniakea/Development/galaxy-db-sync/src/galaxy_db_sync/amazing_data/api/client.py`

### Current test pattern that should be strengthened
```python
with patch.object(client, "query_kline", return_value=mock_result) as mock_sync:
    result = await client.query_kline_async(...)
    mock_sync.assert_called_once_with(...)
```
Source: `/home/laniakea/Development/galaxy-db-sync/tests/amazing_data/test_async_client.py`

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pure sync client only | Partial async wrappers over sync client | Already present in current repo before planning | Phase 1 is a rework/completion phase, not greenfield |
| K-line-centric async wrapper thinking | Full public read-surface async boundary | Locked in discuss-phase context on 2026-04-06 | Planner must widen scope beyond current hot path |
| Sync/async co-equal planning | Async-first compatibility strategy | Locked in discuss-phase context on 2026-04-06 | Future phases should target async APIs directly |

**Deprecated/outdated:**
- Treating Phase 1 as “audit-only” is outdated; the user explicitly redirected the phase to a rework of the full public async surface.
- Treating current tests as sufficient is outdated; they are a starting point, not the acceptance bar.

## Open Questions

1. **Which public methods should be considered in-scope “read APIs” if any are intentionally excluded?**
   - What we know: The public read methods currently visible on `AmazingDataClient` include market/base/financial queries and do not include mutating operations.
   - What's unclear: Whether the planner should include every public query-like method listed in `client.py`, or only the subset reachable from current application code.
   - Recommendation: Use the broader interpretation unless a method is explicitly marked internal or out-of-scope; this matches the locked “full public read surface” decision.

2. **Should Phase 1 include an import-isolation fix for `AmazingData` testability?**
   - What we know: In the project venv, importing `AmazingData` currently fails because `scipy` is missing; `client.py` imports the SDK at module import time.
   - What's unclear: Whether the intended fix is environment repair, lazy import indirection, or test-time monkeypatching.
   - Recommendation: Add a Wave 0 task to decide and implement the least-invasive path that makes unit tests deterministic.

3. **Should async naming remain `<sync_name>_async`?**
   - What we know: That pattern is already used consistently in the existing async methods.
   - What's unclear: Whether the team wants a more aggressive async-first rename in this phase.
   - Recommendation: Keep `<sync_name>_async` for Phase 1. It minimizes churn and preserves compatibility while still enabling async-first downstream planning.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Project Python runtime | client implementation, tests | ✓ | 3.13.12 in `.venv` | Use project `.venv/bin/python`, not system Python 3.14 |
| pytest | async wrapper tests | ✓ | 9.0.2 in `.venv` | — |
| pytest-asyncio | coroutine test execution | ✓ | 1.3.0 in `.venv` | — |
| ruff | lint/format verification | ✓ | 0.15.5 in `.venv` | — |
| mypy | type verification | ✓ | 1.19.1 in `.venv` | — |
| AmazingData wheel file | vendor SDK boundary | ✓ | 1.0.26 wheel bundled | — |
| AmazingData importability in `.venv` | importing `client.py`, running unit tests without SDK shims | ✗ | imports fail due to missing `scipy` | Use test-time import isolation or repair venv dependency chain |
| System Python | ad-hoc commands | ✓ | 3.14.3 | Do not use for project verification; wrong major/minor versus project requirement |

**Missing dependencies with no fallback:**
- None confirmed for planning itself.

**Missing dependencies with fallback:**
- Real SDK importability is currently broken in `.venv` because `scipy` is missing; fallback is to isolate/patch SDK import for unit tests until the environment is repaired.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `/home/laniakea/Development/galaxy-db-sync/pyproject.toml` |
| Quick run command | `/home/laniakea/Development/galaxy-db-sync/.venv/bin/pytest /home/laniakea/Development/galaxy-db-sync/tests/amazing_data/test_async_client.py -q` |
| Full suite command | `/home/laniakea/Development/galaxy-db-sync/.venv/bin/pytest /home/laniakea/Development/galaxy-db-sync/tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ASYNC-01 | Every public read wrapper exposes an async method that delegates through `asyncio.to_thread` | unit | `/home/laniakea/Development/galaxy-db-sync/.venv/bin/pytest /home/laniakea/Development/galaxy-db-sync/tests/amazing_data/test_async_client.py -q` | ✅ |
| COMPAT-01 | Async wrappers preserve sync signatures/behavioral contracts without removing sync APIs | unit | `/home/laniakea/Development/galaxy-db-sync/.venv/bin/pytest /home/laniakea/Development/galaxy-db-sync/tests/amazing_data/test_async_client.py -q` | ✅ |
| TEST-01 | Client boundary covers `to_thread`, arg passthrough, optional args, exception propagation, and non-blocking semantics | unit | `/home/laniakea/Development/galaxy-db-sync/.venv/bin/pytest /home/laniakea/Development/galaxy-db-sync/tests/amazing_data/test_async_client.py -q` | ✅ but incomplete |

### Sampling Rate
- **Per task commit:** `/home/laniakea/Development/galaxy-db-sync/.venv/bin/pytest /home/laniakea/Development/galaxy-db-sync/tests/amazing_data/test_async_client.py -q`
- **Per wave merge:** `/home/laniakea/Development/galaxy-db-sync/.venv/bin/pytest /home/laniakea/Development/galaxy-db-sync/tests/ -v`
- **Phase gate:** Async client unit suite green, plus lint/type checks on touched files before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] Strengthen `tests/amazing_data/test_async_client.py` to assert `asyncio.to_thread` is called for each wrapper.
- [ ] Add coverage for missing async methods once parity is completed: `get_trading_calendar_async`, `get_backward_factor_async`, `query_snapshot_async`, `get_balance_sheet_async`, `get_income_statement_async`, `get_cash_flow_async`.
- [ ] Add exception-propagation assertions for mapped exceptions and optional-failure semantics like `get_listing_dates`.
- [ ] Add an environment/test bootstrap fix so `client.py` can be imported even when the real SDK dependency chain is unavailable.
- [ ] Add lightweight signature/compatibility assertions ensuring sync methods remain callable during transition.

## Sources

### Primary (HIGH confidence)
- `/home/laniakea/Development/galaxy-db-sync/.planning/phases/01-async-api-client-wrapper/01-CONTEXT.md` - locked scope, async-first direction, and required test boundary
- `/home/laniakea/Development/galaxy-db-sync/.planning/REQUIREMENTS.md` - requirement IDs and official phase mapping
- `/home/laniakea/Development/galaxy-db-sync/.planning/ROADMAP.md` - phase goal and success criteria
- `/home/laniakea/Development/galaxy-db-sync/CLAUDE.md` - project conventions, commands, and architectural constraints
- `/home/laniakea/Development/galaxy-db-sync/src/galaxy_db_sync/amazing_data/api/client.py` - actual current sync/async API surface
- `/home/laniakea/Development/galaxy-db-sync/tests/amazing_data/test_async_client.py` - current validation coverage and gaps
- `/home/laniakea/Development/galaxy-db-sync/pyproject.toml` - project Python version, pytest config, declared dependencies
- `/home/laniakea/Development/galaxy-db-sync/uv.lock` - pinned pytest/pytest-asyncio/ruff versions
- `/home/laniakea/Development/galaxy-db-sync/.venv/lib/python3.13/site-packages/pytest_asyncio/plugin.py` - `asyncio_mode` behavior and plugin configuration semantics
- `/home/laniakea/Development/galaxy-db-sync/.venv/lib/python3.13/site-packages/pytest_asyncio-1.3.0.dist-info/METADATA` - installed pytest-asyncio version and support statement

### Secondary (MEDIUM confidence)
- Project virtualenv command probes run during research - verified tool/runtime availability in `.venv`
- Project virtualenv import probe for `AmazingData` - verified current import failure due to missing `scipy`

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - derived from project-pinned files, installed tools, and current codebase usage
- Architecture: HIGH - derived from locked discuss-phase decisions plus actual `client.py` implementation
- Pitfalls: HIGH - directly observed from current API parity gaps, existing tests, and environment probe results

**Research date:** 2026-04-06
**Valid until:** 2026-05-06
