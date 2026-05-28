# Async Refactoring Plan

**Created:** 2026-04-06
**Branch:** main
**Status:** DRAFT

## Executive Summary

The codebase currently uses synchronous I/O throughout. The AmazingData SDK is synchronous and cannot be changed. This plan outlines a phased migration to async/await patterns that will:

1. Improve concurrency for batch API calls (wrap synchronous SDK with `asyncio.to_thread`)
2. Enable true async database operations (migrate to SQLAlchemy 2.0 async)
3. Replace `ThreadPoolExecutor` with `asyncio.gather` for cleaner concurrency

**Key insight:** The AmazingData SDK is a black box. We cannot make it async. All async gains come from:
- Parallelizing SDK calls via `asyncio.to_thread` (same as current ThreadPoolExecutor)
- Eliminating blocking database I/O with async SQLAlchemy
- Cleaner code structure with native async/await

## Current Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI Entry Point                          │
│                     (synchronous argparse)                       │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                    Command Handler                              │
│              (sync, completeness check)                         │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                   Sync Orchestrator                             │
│        (ThreadPoolExecutor, 5 workers)                          │
│                                                                 │
│   ┌─────────────────┐    ┌─────────────────┐                   │
│   │  API Client     │    │  DB Service     │                   │
│   │  (sync SDK)     │    │  (sync SQLA)    │                   │
│   └─────────────────┘    └─────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

**Bottlenecks:**
1. Each API call blocks a thread for ~100-500ms (network latency)
2. Database queries block the same thread
3. ThreadPoolExecutor overhead for managing worker threads

## Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI Entry Point                          │
│                     (synchronous argparse)                       │
│                          │ asyncio.run()                        │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                    Async Command Handler                        │
│              (async, completeness check)                        │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                   Async Sync Orchestrator                       │
│           (asyncio.gather, semaphore control)                   │
│                                                                 │
│   ┌─────────────────┐    ┌─────────────────┐                   │
│   │  Async API      │    │  Async DB       │                   │
│   │  (to_thread)    │    │  (SQLA 2.0)     │                   │
│   └─────────────────┘    └─────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

**Improvements:**
1. Single event loop instead of thread pool
2. Async database eliminates blocking I/O
3. Cleaner error propagation with async/await
4. Better cancellation handling

## Phased Migration Plan

### Phase 1: Async API Client Wrapper (Low Risk)

**Goal:** Add async methods to AmazingDataClient without changing sync methods.

**Changes:**
1. Add `query_kline_async()` using `asyncio.to_thread()`
2. Add `get_stock_list_async()` using `asyncio.to_thread()`
3. Add `get_listing_dates_async()` using `asyncio.to_thread()`

**Files to modify:**
- `src/galaxy_db_sync/amazing_data/api/client.py`

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
    """Async wrapper for query_kline."""
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

**Effort:** 2-4 hours (CC: 15 min)
**Risk:** Low - no existing code changes
**Completeness:** 10/10

---

### Phase 2: Async Sync Orchestrator (Medium Risk)

**Goal:** Replace ThreadPoolExecutor with asyncio.gather.

**Changes:**
1. Create `sync_kline_data_async()` in sync_orchestrator.py
2. Replace `ThreadPoolExecutor` with `asyncio.gather` + `asyncio.Semaphore`
3. Use async API client methods from Phase 1

**Files to modify:**
- `src/galaxy_db_sync/application/kline/sync_orchestrator.py`

**Before:**
```python
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = {
        executor.submit(fetch_single_batch, key, symbols, semaphore): key
        for key, symbols in range_groups.items()
    }
    for future in as_completed(futures):
        ...
```

**After:**
```python
semaphore = asyncio.Semaphore(max_concurrent)

async def fetch_batch_async(key, symbols):
    async with semaphore:
        return await query_kline_with_results_async(...)

results = await asyncio.gather(
    *[fetch_batch_async(key, symbols) for key, symbols in range_groups.items()],
    return_exceptions=True,
)
```

**Effort:** 4-8 hours (CC: 30 min)
**Risk:** Medium - changes core sync logic
**Completeness:** 10/10

---

### Phase 3: Async Database Layer (High Risk)

**Goal:** Migrate database services to SQLAlchemy 2.0 async.

**Changes:**
1. Update `DatabaseManager` to use `create_async_engine`
2. Replace `sessionmaker` with `async_sessionmaker`
3. Add `AsyncSession` context manager
4. Migrate query methods to async
5. Migrate save methods to async

**Files to modify:**
- `src/galaxy_db_sync/database/core/connection.py`
- `src/galaxy_db_sync/database/services/kline_query.py`
- `src/galaxy_db_sync/database/services/kline_save.py`
- `src/galaxy_db_sync/database/services/kline.py`
- `src/galaxy_db_sync/database/services/trading_calendar.py`
- `src/galaxy_db_sync/database/services/kline_completeness_checker.py`
- `src/galaxy_db_sync/database/services/kline_data_sync.py`

**Database URL change:**
```python
# Before
database_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"

# After
database_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
```

**Connection manager:**
```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

class DatabaseManager:
    _engine = None
    _session_maker = None

    def initialize(self, ...):
        self._engine = create_async_engine(database_url, ...)
        self._session_maker = async_sessionmaker(self._engine, ...)

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self._session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
```

**Effort:** 8-16 hours (CC: 1-2 hours)
**Risk:** High - touches all database code
**Completeness:** 10/10

---

### Phase 4: Async CLI Entry Point (Low Risk)

**Goal:** Update CLI to use asyncio.run() for async command handlers.

**Changes:**
1. Make command handlers async
2. Use `asyncio.run()` in CLI entry point
3. Maintain backward compatibility with sync code paths

**Files to modify:**
- `src/galaxy_db_sync/application/kline/command.py`
- `src/galaxy_db_sync/application/cli/commands.py`

**Example:**
```python
# commands.py
def kline_command(args):
    asyncio.run(handle_kline_command_async(args))

# command.py
async def handle_kline_command_async(args):
    ...
```

**Effort:** 2-4 hours (CC: 15 min)
**Risk:** Low - thin adapter layer
**Completeness:** 10/10

---

## Dependency Changes

### Required New Dependencies

```toml
[project.dependencies]
# Async PostgreSQL driver
"asyncpg" = ">=0.29.0"

# SQLAlchemy async support (already in 2.0)
# "sqlalchemy[asyncio]" = ">=2.0.0"
```

### pyproject.toml Updates

```toml
[project.dependencies]
asyncpg = ">=0.29.0"

[project.optional-dependencies]
dev = [
    "pytest-asyncio>=0.23.0",  # Async test support
]
```

---

## Testing Strategy

### Unit Tests
- Mock async methods with `unittest.mock.AsyncMock`
- Test semaphore limiting with concurrent tasks
- Verify error propagation in async context

### Integration Tests
- Use `pytest-asyncio` for async test fixtures
- Test against real database with async driver
- Verify batch operations maintain correctness

### Performance Benchmarks
- Compare ThreadPoolExecutor vs asyncio.gather throughput
- Measure database query latency with asyncpg vs psycopg2
- Track memory usage during large batch syncs

---

## Migration Order (Recommended)

```
Phase 1 (API wrapper)     ─────►  No dependencies, safe to merge
        │
        ▼
Phase 2 (Orchestrator)    ─────►  Uses Phase 1, still sync DB
        │
        ▼
Phase 3 (Database)        ─────►  Breaking change, needs migration script
        │
        ▼
Phase 4 (CLI)             ─────►  Final integration
```

Each phase can be merged independently. Phases 1-2 maintain full backward compatibility. Phase 3 is the breaking change.

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| AmazingData SDK thread safety | Keep SDK calls in `to_thread`, never call directly from async context |
| Database connection pool exhaustion | Configure async pool size appropriately |
| Breaking existing sync callers | Keep sync methods as thin wrappers over async |
| Test suite complexity | Use `pytest-asyncio` with auto mode |
| Transaction handling differences | Verify commit/rollback behavior in async session |

---

## NOT in Scope

- **AmazingData SDK replacement** - We're stuck with the synchronous SDK
- **Full rewrite** - Incremental migration, not big bang
- **API changes** - External interfaces remain the same
- **Performance optimization beyond async** - Separate concern
- **Thread-safe singleton refactoring** - Out of scope for async work

---

## What Already Exists

| Component | Current State | Reuse Strategy |
|-----------|---------------|----------------|
| `ThreadPoolExecutor` in sync_orchestrator | Working concurrent implementation | Replace with asyncio.gather |
| Semaphore in sync_orchestrator | Already has concurrency control | Use asyncio.Semaphore |
| Database connection pool | Working with psycopg2 | Migrate to asyncpg |
| Error handling patterns | Good exception hierarchy | Preserve, add async variants |

---

## Success Criteria

1. **Phase 1:** All API methods have async equivalents, sync methods unchanged
2. **Phase 2:** Batch sync uses asyncio.gather, tests pass
3. **Phase 3:** Database operations are fully async, no sync DB calls in hot path
4. **Phase 4:** CLI works identically to before, but internally uses async

**Verification:**
- All existing tests pass
- New async tests cover async code paths
- Performance is equal or better than current implementation
- No regression in data integrity

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAN | 3 arch issues, 2 quality issues, 8 test gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**VERDICT:** ENG REVIEW PASSED — Ready for implementation

---

## Eng Review Findings Summary

### Architecture Issues

1. **Singleton + Async Safety** — Need to decide on DatabaseManager approach
   - Options: New AsyncDatabaseManager class vs modify existing vs DI
   - Recommendation: New class for clean separation during migration

2. **Transaction Handling** — Async SQLAlchemy requires explicit await
   - Covered in plan examples

3. **Semaphore Migration** — threading.Semaphore → asyncio.Semaphore
   - Low risk, direct replacement

### Code Quality Issues

1. **Exception Handling** — Prior learning: avoid `except Exception`
   - Use specific exceptions (SDKError, APIConnectionError)
   - Preserve exception type in logs

2. **Event Loop Blocking Risk** — SDK calls must use asyncio.to_thread
   - Add explicit warnings in code comments

### Test Gaps

8 new async paths need tests:
- query_kline_async, get_stock_list_async, get_listing_dates_async
- sync_kline_data_async, batch_fetch_kline_data_async, execute_kline_query_async
- async session context, query_kline_from_db_async

**Strategy:** Add tests with each phase (user confirmed)

### Pending Decision

- ~~**DatabaseManager approach** — User confirmed: Dependency Injection pattern~~

**Decision: Dependency Injection Pattern**

Remove singleton, pass database manager explicitly:
```python
# Before
from galaxy_db_sync.database.core.connection import db_manager

class KlineService:
    def query(self, ...):
        with db_manager.session() as session:
            ...

# After
class KlineService:
    def __init__(self, db_manager: DatabaseManager):
        self._db = db_manager

    async def query_async(self, ...):
        async with self._db.session() as session:
            ...

# Async version
class AsyncDatabaseManager:
    def __init__(self, database_url: str, pool_size: int = 10):
        self._engine = create_async_engine(database_url, pool_size=pool_size)
        self._session_maker = async_sessionmaker(self._engine)

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        ...
```

This is the most significant change in Phase 3. All services that currently import `db_manager` will need to receive it via constructor.

---

## Appendix: Code Examples

### Async Database Query

```python
# kline_query.py
async def query_kline_from_db_async(
    symbols: List[str],
    start_date: Optional[Union[str, int, datetime]],
    end_date: Optional[Union[str, int, datetime]],
    interval: str = "day",
    interval_model_map: dict = None,
) -> Dict[str, pd.DataFrame]:
    """Async version of query_kline_from_db."""
    if interval_model_map is None:
        interval_model_map = INTERVAL_MODEL_MAP

    interval_lower = interval.lower()
    if interval_lower not in interval_model_map:
        raise ValueError(f"Unsupported interval: {interval}")

    table_model = interval_model_map[interval_lower]
    results = {}

    async with db_manager.session() as session:
        for symbol in symbols:
            query = await session.execute(
                select(table_model)
                .where(table_model.symbol == symbol)
                .order_by(table_model.trade_time)
            )
            rows = query.scalars().all()
            if rows:
                results[symbol] = _rows_to_dataframe(rows)

    return results
```

### Async Batch Save

```python
# kline_save.py
async def batch_save_kline_to_db_async(
    kline_dict: Dict[str, pd.DataFrame],
    interval: str,
    interval_model_map: dict = None,
) -> int:
    """Async batch save using PostgreSQL UPSERT."""
    # ... same logic but with async session ...
    async with db_manager.session() as session:
        await session.execute(upsert_stmt)
        # session.commit() is automatic in context manager
```