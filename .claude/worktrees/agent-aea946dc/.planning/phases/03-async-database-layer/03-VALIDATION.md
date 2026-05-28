---
phase: 03-async-database-layer
created: 2026-04-07T16:30:00Z
status: pending
---

# Phase 03: Async Database Layer - Validation Architecture

## Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | pyproject.toml (`asyncio_mode="auto"`) |
| Quick run command | `pytest tests/unit/test_async_kline.py -x` |
| Full suite command | `pytest tests/ -v` |

## Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ASYNC-03 | Async engine/session setup | unit | `pytest tests/unit/test_async_connection.py -x` | Wave 0 - new file needed |
| ASYNC-04 | DI pattern works | unit | `pytest tests/unit/test_async_kline.py -x` | Wave 0 - new file needed |
| TEST-01 | Async query/save tested | unit | `pytest tests/unit/test_async_kline_query.py -x` | Wave 0 - new file needed |
| DATA-01 | UPSERT parity | integration | `pytest tests/integration/test_async_upsert.py -x` | Wave 0 - new file needed |

## Sampling Rate

- **Per task commit:** `pytest tests/unit/test_async_kline*.py -x`
- **Per wave merge:** `pytest tests/unit/ tests/integration/ -v`
- **Phase gate:** Full suite green + integration parity tests pass

## Wave 0 Gaps

- [ ] `tests/unit/test_async_connection.py` - AsyncDatabaseManager setup
- [ ] `tests/unit/test_async_kline.py` - AsyncKlineService DI
- [ ] `tests/unit/test_async_kline_query.py` - Async query functions
- [ ] `tests/unit/test_async_kline_save.py` - Async UPSERT functions
- [ ] `tests/integration/test_async_upsert.py` - DATA-01 parity verification
- [ ] `tests/unit/conftest.py` - Async fixtures (AsyncMock session)
- [ ] Framework install: `uv pip install asyncpg` - async driver needed

## Validation Commands

### Pre-Execution (Wave 0 Gap Check)
```bash
# Verify asyncpg installed
python -c "import asyncpg; print(asyncpg.__version__)" || echo "MISSING: asyncpg"

# Check test files exist
ls tests/unit/test_async_connection.py || echo "MISSING: test_async_connection.py"
ls tests/unit/test_async_kline.py || echo "MISSING: test_async_kline.py"
```

### Per-Task Verification
```bash
# After async_connection.py implementation
pytest tests/unit/test_async_connection.py -v

# After async_kline.py implementation
pytest tests/unit/test_async_kline.py -v

# After async query/save implementation
pytest tests/unit/test_async_kline_query.py tests/unit/test_async_kline_save.py -v
```

### Phase Gate Verification
```bash
# Full async database tests
pytest tests/unit/test_async*.py -v

# Integration parity tests
pytest tests/integration/test_async_upsert.py -v

# No regressions in existing tests
pytest tests/unit/ tests/kline/ -v
```

## Coverage Requirements

| Requirement | Min Coverage | Critical Paths |
|-------------|--------------|----------------|
| ASYNC-03 | 80% | engine creation, session factory, context manager |
| ASYNC-04 | 80% | DI injection, session usage, service creation |
| DATA-01 | 100% | UPSERT conflict handling, merge parity |

## Nyquist Compliance

This phase follows Nyquist validation rules:
- Wave 0 gaps identified before execution
- Per-task test verification required
- Phase gate: full suite green + parity tests pass
- Sampling rate: per-task commit verification

---
Created: 2026-04-07T16:30:00Z