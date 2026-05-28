# Phase 3: Async Database Layer - Research

**Researched:** 2026-04-07
**Domain:** SQLAlchemy async database layer migration
**Confidence:** HIGH

## Summary

This phase migrates the database layer from synchronous SQLAlchemy to async engine/session, enabling true async I/O for database operations while maintaining behavioral parity with existing sync implementation. The migration targets `DatabaseManager`, `KlineService`, `TradingCalendarService`, and related query/save modules.

**Primary recommendation:** Create `AsyncDatabaseManager` alongside existing sync `db_manager`, using `asyncpg` driver and dependency injection pattern. Async services receive injected session factory rather than accessing global singleton.

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ASYNC-03 | 数据库层使用 SQLAlchemy async engine / async session | Standard Stack section provides async engine setup patterns |
| ASYNC-04 | 异步热路径使用显式数据库依赖注入，替代全局同步 `db_manager` | Architecture Patterns section documents DI strategy |
| TEST-01 | 为新增 async 服务方法补齐单元测试 | Validation Architecture section maps test coverage |
| DATA-01 | 保证数据库查询、合并、去重、UPSERT、事务提交/回滚在异步改造后仍与当前行为等价 | Common Pitfalls section documents behavioral parity risks |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlalchemy[asyncio] | >=2.0.0 | ORM + async support | SQLAlchemy 2.0+ built-in async via `ext.asyncio` |
| asyncpg | 0.29.0 | PostgreSQL async driver | Pure Python async driver, fastest for PostgreSQL |
| pytest-asyncio | >=0.23.0 | Async test support | Already in dev dependencies, supports `asyncio_mode="auto"` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| psycopg2-binary | 2.9.11 | Sync PostgreSQL driver | Keep for sync paths and legacy code |
| greenlet | 3.3.2 | Async context bridging | SQLAlchemy async internals |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| asyncpg | psycopg (async) | psycopg 3 has async support but asyncpg is more mature and faster for SQLAlchemy |
| create_async_engine | Multiple engines | Single engine with pool is standard; multiple engines for read/write splitting is overkill |

**Installation:**
```bash
# Add asyncpg to dependencies
uv pip install asyncpg

# Or add to pyproject.toml
dependencies = [
    ...
    "asyncpg>=0.29.0",
]
```

**Version verification:**
- SQLAlchemy: Already installed at 2.0+ (supports async)
- asyncpg: NOT installed - needs to be added
- pytest-asyncio: Already in dev dependencies at >=0.23.0

## Architecture Patterns

### Current State: Sync DatabaseManager

The existing `DatabaseManager` (connection.py) uses sync patterns:

```python
# Current sync implementation
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

class DatabaseManager:
    _engine = None
    _session_maker = None
    
    def initialize(self, ...):
        self._engine = create_engine(
            f"postgresql://{user}:{password}@{host}:{port}/{database}",
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_pre_ping=True,
        )
        self._session_maker = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self._engine,
        )
    
    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        session = self._session_maker()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

# Global singleton
db_manager = DatabaseManager()
```

### Recommended Async Architecture

```python
# Async implementation pattern
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from contextlib import asynccontextmanager

class AsyncDatabaseManager:
    """Async database manager with explicit dependency injection support."""
    
    _engine = None
    _session_maker = None
    
    def initialize(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout: int = 30,
        echo: bool = False,
    ) -> None:
        # Use asyncpg driver (postgresql+asyncpg://)
        database_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
        
        self._engine = create_async_engine(
            database_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_pre_ping=True,
            echo=echo,
        )
        
        # async_sessionmaker with expire_on_commit=False
        # Critical: expire_on_commit=False prevents attribute expiration
        self._session_maker = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Async session context manager."""
        session = self._session_maker()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    async def get_session(self) -> AsyncSession:
        """Get a new async session (manual lifecycle management)."""
        return self._session_maker()
    
    async def close(self) -> None:
        """Dispose of the engine."""
        if self._engine:
            await self._engine.dispose()
    
    async def create_tables(self) -> None:
        """Create tables asynchronously."""
        from galaxy_db_sync.database.models import Base
        
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # TimescaleDB hypertables still need sync execution via run_sync
        await self._create_hypertables()
```

### Dependency Injection Pattern

```python
# Service receives injected session factory, not global singleton
class AsyncKlineService:
    """Async K-line service with injected database dependency."""
    
    def __init__(self, db_manager: AsyncDatabaseManager):
        self._db_manager = db_manager
        self.interval_model_map = INTERVAL_MODEL_MAP
    
    async def query_kline_from_db(
        self,
        symbols: List[str],
        start_date: Optional[Union[str, int, datetime]] = None,
        end_date: Optional[Union[str, int, datetime]] = None,
        interval: str = "day",
    ) -> Dict[str, pd.DataFrame]:
        """Async query implementation."""
        async with self._db_manager.session() as session:
            # Use SQLAlchemy 2.0 select() pattern
            table_model = self.interval_model_map[interval.lower()]
            query = select(table_model).where(table_model.symbol.in_(symbols))
            
            if start_date:
                start_dt = parse_date_for_interval(start_date, interval, is_end=False)
                query = query.where(table_model.trade_time >= start_dt)
            if end_date:
                end_dt = parse_date_for_interval(end_date, interval, is_end=True)
                query = query.where(table_model.trade_time <= end_dt)
            
            result = await session.execute(query)
            records = result.scalars().all()
            
            # Convert to DataFrame dict (same logic as sync version)
            return self._records_to_dict(records, symbols)
```

### Project Structure After Migration

```
src/galaxy_db_sync/database/
├── core/
│   ├── connection.py         # Sync DatabaseManager (keep for legacy)
│   ├── async_connection.py   # NEW: AsyncDatabaseManager
│   └── timescale.py          # TimescaleDB hypertable setup (sync)
├── models/
│   └── kline.py              # ORM models (unchanged)
├── services/
│   ├── kline.py              # Sync KlineService wrapper
│   ├── async_kline.py        # NEW: AsyncKlineService
│   ├── kline_query.py        # Sync query functions (keep)
│   ├── async_kline_query.py  # NEW: Async query functions
│   ├── kline_save.py         # Sync save functions (keep)
│   ├── async_kline_save.py   # NEW: Async save functions
│   ├── trading_calendar.py   # TradingCalendarService (partial async exists)
│   └── async_trading_calendar.py  # NEW: Full async version
```

### Integration with Existing Orchestrator

Phase 2's `execute_kline_query_async` currently uses sync database calls:

```python
# Phase 2 orchestrator (current)
async def execute_kline_query_async(...):
    # Database query is still sync (Phase 3 stub)
    db_data = kline_service.query_kline_from_db(...)  # SYNC
    
    # API fetch uses asyncio.to_thread
    api_data, failed_codes = await asyncio.to_thread(...)
    
    return kline_service.merge_db_and_api_data(db_data, api_data)
```

After Phase 3:

```python
# Phase 3 orchestrator (updated)
async def execute_kline_query_async(
    symbol_list: list[str],
    interval: str,
    start_date: str,
    end_date: str,
    interval_value: int,
    async_db_manager: AsyncDatabaseManager,  # Injected dependency
):
    async_kline_service = AsyncKlineService(async_db_manager)
    
    # Now fully async
    db_data = await async_kline_service.query_kline_from_db(...)
    
    # API fetch unchanged
    api_data, failed_codes = await asyncio.to_thread(...)
    
    return async_kline_service.merge_db_and_api_data(db_data, api_data)
```

### Anti-Patterns to Avoid

- **Do NOT call sync db_manager inside async functions**: This blocks the event loop
- **Do NOT create engine per request**: Engine should be singleton with connection pool
- **Do NOT use `expire_on_commit=True`**: Causes lazy loading issues in async context
- **Do NOT forget `await session.commit()`**: Async sessions require explicit await

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async connection pooling | Custom async pool manager | SQLAlchemy `create_async_engine` with pool_size | Built-in, tested, handles edge cases |
| Transaction management | Manual begin/commit/rollback | `async with session.begin():` or contextmanager | Prevents leaked transactions |
| Upsert logic | Custom INSERT ON CONFLICT | SQLAlchemy `insert().on_conflict_do_update()` | Handles edge cases, type-safe |
| Mock async sessions | Custom AsyncSession mock | `unittest.mock.AsyncMock` + test fixtures | pytest-asyncio handles async mocks |

## Runtime State Inventory

> This phase involves database layer refactoring, not renaming/migration of user-facing identifiers.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | TimescaleDB hypertables (kline_min1, kline_day, etc.) | No migration - tables unchanged |
| Live service config | None - no external services | N/A |
| OS-registered state | None | N/A |
| Secrets/env vars | DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD | Add async URL construction (postgresql+asyncpg://) |
| Build artifacts | None | N/A |

**Nothing found requiring migration:** Database schema unchanged, ORM models unchanged, env vars unchanged.

## Common Pitfalls

### Pitfall 1: Blocking Event Loop with Sync DB Calls
**What goes wrong:** Calling `db_manager.session()` inside async function blocks event loop
**Why it happens:** Sync SQLAlchemy uses blocking I/O; async event loop can't proceed
**How to avoid:** Use `AsyncDatabaseManager` and `await` all session operations
**Warning signs:** High latency, sequential instead of concurrent execution

### Pitfall 2: Missing `expire_on_commit=False`
**What goes wrong:** Attributes become stale after commit, lazy loading fails in async
**Why it happens:** SQLAlchemy default behavior expires objects on commit
**How to avoid:** Set `expire_on_commit=False` in `async_sessionmaker`
**Warning signs:** `DetachedInstanceError`, stale data after commit

### Pitfall 3: Incorrect Async Driver URL
**What goes wrong:** Using `postgresql://` instead of `postgresql+asyncpg://`
**Why it happens:** Copying sync URL pattern without driver specification
**How to avoid:** Always use `postgresql+asyncpg://` for async engine
**Warning signs:** RuntimeError about missing async driver

### Pitfall 4: UPSERT Behavioral Parity
**What goes wrong:** Async UPSERT produces different results than sync version
**Why it happens:** Timing differences in concurrent execution
**How to avoid:** Use same SQLAlchemy `on_conflict_do_update()` logic; test equivalence
**Warning signs:** Data count mismatch in integration tests

### Pitfall 5: Transaction Not Committed
**What goes wrong:** Data not persisted after async operation completes
**Why it happens:** Missing `await session.commit()` or context manager exit
**How to avoid:** Always use `async with session.begin():` or explicit commit
**Warning signs:** Empty database after successful API fetch

## Code Examples

### Async Engine Setup

```python
# Source: SQLAlchemy 2.0 async documentation pattern
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Connection URL with async driver
DATABASE_URL = "postgresql+asyncpg://quant_user:password@localhost:5432/quant_db"

# Engine with connection pool
async_engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_pre_ping=True,  # Verify connections before use
    echo=False,
)

# Session factory
async_session_factory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Critical for async
    autocommit=False,
    autoflush=False,
)
```

### Async Query Pattern (select)

```python
# Source: SQLAlchemy 2.0 async query pattern
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def query_kline_async(
    session: AsyncSession,
    table_model,
    symbols: List[str],
    start_dt: datetime,
    end_dt: datetime,
) -> List:
    """Async select query."""
    stmt = select(table_model).where(
        table_model.symbol.in_(symbols),
        table_model.trade_time >= start_dt,
        table_model.trade_time <= end_dt,
    ).order_by(table_model.trade_time)
    
    result = await session.execute(stmt)
    return result.scalars().all()
```

### Async UPSERT Pattern

```python
# Source: SQLAlchemy PostgreSQL dialect async pattern
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func

async def upsert_kline_async(
    session: AsyncSession,
    table_model,
    data_list: List[dict],
) -> int:
    """Async UPSERT with conflict handling."""
    stmt = pg_insert(table_model).values(data_list)
    
    # Update on conflict
    update_dict = {
        'open': stmt.excluded.open,
        'high': stmt.excluded.high,
        'low': stmt.excluded.low,
        'close': stmt.excluded.close,
        'volume': stmt.excluded.volume,
        'amount': stmt.excluded.amount,
        'security_type': stmt.excluded.security_type,
        'updated_at': func.now(),
    }
    
    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=['symbol', 'trade_time'],
        set_=update_dict,
    )
    
    await session.execute(upsert_stmt)
    await session.commit()
    return len(data_list)
```

### TimescaleDB Hypertable Creation (Async)

```python
# Source: TimescaleDB requires sync execution via run_sync
async def create_hypertables_async(engine):
    """Create TimescaleDB hypertables via run_sync."""
    async with engine.begin() as conn:
        # TimescaleDB functions are sync, use run_sync
        await conn.run_sync(_create_hypertables_sync)

def _create_hypertables_sync(sync_conn):
    """Sync helper for TimescaleDB."""
    from sqlalchemy import text
    
    # Check TimescaleDB extension
    result = sync_conn.execute(text(
        "SELECT installed_version FROM pg_available_extensions WHERE name = 'timescaledb'"
    ))
    if not result.fetchone():
        return  # TimescaleDB not installed
    
    kline_tables = [
        "kline_min1", "kline_min3", "kline_min5", "kline_min10",
        "kline_min15", "kline_min30", "kline_min60", "kline_min120",
        "kline_day", "kline_week", "kline_month", "kline_season", "kline_year",
    ]
    
    for table_name in kline_tables:
        sync_conn.execute(text(f"""
            SELECT create_hypertable('{table_name}', 'trade_time', if_not_exists => true)
        """))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `session.query(Model)` | `select(Model)` via `session.execute()` | SQLAlchemy 2.0 | 2.0 style, async-compatible |
| `session.add()` + `session.commit()` | Same pattern with `await` | Async SQLAlchemy | Works identically with async |
| psycopg2 driver | asyncpg driver for async | Async SQLAlchemy | 10-20% faster for async I/O |
| Global singleton db_manager | Dependency injection | Phase 3 design | Explicit boundaries, testable |

**Deprecated/outdated:**
- `session.query()` style: Use `select()` + `execute()` for async compatibility
- `expire_on_commit=True`: Causes issues in async context; use `False`

## Open Questions

1. **Should sync and async paths share models?**
   - What we know: SQLAlchemy models are sync/async neutral
   - What's unclear: Whether to keep separate service classes or unified service with dual methods
   - Recommendation: Keep separate `KlineService` (sync) and `AsyncKlineService` (async) for clarity

2. **How to inject async_db_manager into orchestrator?**
   - What we know: Phase 2 orchestrator currently uses global `kline_service`
   - What's unclear: Best injection pattern for async entry point
   - Recommendation: Pass `async_db_manager` as parameter to `execute_kline_query_async()`, or use factory pattern

3. **TradingCalendarService partial async - full migration?**
   - What we know: `TradingCalendarService.sync_years()` already uses `asyncio.to_thread`
   - What's unclear: Whether to fully migrate or keep hybrid
   - Recommendation: Create `AsyncTradingCalendarService` for hot paths, keep sync for CLI commands

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | Database operations | Depends on deployment | External | Integration tests skip if unavailable |
| asyncpg | Async PostgreSQL driver | NOT installed | - | Must install before implementation |
| pytest-asyncio | Async tests | Installed | >=0.23.0 | - |
| SQLAlchemy | ORM | Installed | >=2.0.0 | - |
| greenlet | Async bridging | Installed | 3.3.2 | - |

**Missing dependencies with no fallback:**
- asyncpg: Must add to `pyproject.toml` before implementation starts

**Missing dependencies with fallback:**
- None - asyncpg is required for async PostgreSQL

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | pyproject.toml (`asyncio_mode="auto"`) |
| Quick run command | `pytest tests/unit/test_async_kline_service.py -x` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ASYNC-03 | Async engine/session setup | unit | `pytest tests/unit/test_async_connection.py -x` | Wave 0 - new file needed |
| ASYNC-04 | DI pattern works | unit | `pytest tests/unit/test_async_kline_service.py -x` | Wave 0 - new file needed |
| TEST-01 | Async query/save tested | unit | `pytest tests/unit/test_async_kline_query.py -x` | Wave 0 - new file needed |
| DATA-01 | UPSERT parity | integration | `pytest tests/integration/test_async_upsert.py -x` | Wave 0 - new file needed |

### Sampling Rate
- **Per task commit:** `pytest tests/unit/test_async_kline*.py -x`
- **Per wave merge:** `pytest tests/unit/ tests/integration/ -v`
- **Phase gate:** Full suite green + integration parity tests pass

### Wave 0 Gaps
- [ ] `tests/unit/test_async_connection.py` - AsyncDatabaseManager setup
- [ ] `tests/unit/test_async_kline_service.py` - AsyncKlineService DI
- [ ] `tests/unit/test_async_kline_query.py` - Async query functions
- [ ] `tests/unit/test_async_kline_save.py` - Async UPSERT functions
- [ ] `tests/integration/test_async_upsert.py` - DATA-01 parity verification
- [ ] `tests/unit/conftest.py` - Async fixtures (AsyncMock session)
- [ ] Framework install: `uv pip install asyncpg` - async driver needed

## Sources

### Primary (HIGH confidence)
- SQLAlchemy 2.0 asyncio documentation - async engine patterns
- SQLAlchemy 2.0 migration guide - sync to async conversion
- Project codebase analysis - current sync implementation patterns

### Secondary (MEDIUM confidence)
- Phase 2 orchestrator implementation - async entry point pattern
- WebSearch results - async SQLAlchemy patterns (verified against official docs)

### Tertiary (LOW confidence)
- None - all critical patterns verified against primary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - SQLAlchemy async patterns are well documented and tested
- Architecture: HIGH - Migration patterns from sync to async are standard
- Pitfalls: HIGH - Common async SQLAlchemy issues are well documented

**Research date:** 2026-04-07
**Valid until:** 30 days - SQLAlchemy patterns are stable

---

## Implementation Recommendations

### Recommended Plan Structure (3 Plans)

**Plan 1: Core Infrastructure (ASYNC-03)**
1. Add asyncpg to dependencies
2. Create `AsyncDatabaseManager` in `async_connection.py`
3. Create async fixtures in `tests/unit/conftest.py`
4. Verify engine/session setup with unit tests

**Plan 2: Async Services (ASYNC-04, TEST-01)**
1. Create `AsyncKlineService` with injected `AsyncDatabaseManager`
2. Create `async_kline_query.py` with async query functions
3. Create `async_kline_save.py` with async UPSERT functions
4. Unit tests for all async service methods

**Plan 3: Integration & Parity Verification (DATA-01)**
1. Update `execute_kline_query_async` to use async database
2. Integration tests for UPSERT parity
3. Integration tests for query parity
4. Benchmark async vs sync database performance

### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Behavioral parity failure | HIGH | Integration tests comparing sync vs async results |
| Connection pool exhaustion | MEDIUM | Configure pool_size appropriately |
| TimescaleDB hypertable creation async | LOW | Use `run_sync` for TimescaleDB operations |
| Missing await on session operations | HIGH | Lint with ruff/mypy for async safety |