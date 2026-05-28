---
phase: 01
slug: async-api-client-wrapper
status: completed
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-06
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `/home/laniakea/Development/galaxy-db-sync/.venv/bin/pytest /home/laniakea/Development/galaxy-db-sync/tests/amazing_data/test_async_client.py -q` |
| **Full suite command** | `/home/laniakea/Development/galaxy-db-sync/.venv/bin/pytest /home/laniakea/Development/galaxy-db-sync/tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `/home/laniakea/Development/galaxy-db-sync/.venv/bin/pytest /home/laniakea/Development/galaxy-db-sync/tests/amazing_data/test_async_client.py -q`
- **After every plan wave:** Run `/home/laniakea/Development/galaxy-db-sync/.venv/bin/pytest /home/laniakea/Development/galaxy-db-sync/tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 0 | ASYNC-01 | unit | `/home/laniakea/Development/galaxy-db-sync/.venv/bin/pytest /home/laniakea/Development/galaxy-db-sync/tests/amazing_data/test_async_client.py -q` | ✅ | ✅ green |
| 01-01-02 | 01 | 1 | ASYNC-01, COMPAT-01 | unit | `/home/laniakea/Development/galaxy-db-sync/.venv/bin/pytest /home/laniakea/Development/galaxy-db-sync/tests/amazing_data/test_async_client.py -q` | ✅ | ✅ green |
| 01-02-01 | 02 | 1 | TEST-01 | unit | `/home/laniakea/Development/galaxy-db-sync/.venv/bin/pytest /home/laniakea/Development/galaxy-db-sync/tests/amazing_data/test_async_client.py -q` | ✅ | ✅ green |
| 01-02-02 | 02 | 2 | COMPAT-01, TEST-01 | unit + lint + type | `/home/laniakea/Development/galaxy-db-sync/.venv/bin/pytest /home/laniakea/Development/galaxy-db-sync/tests/amazing_data/test_async_client.py -q && /home/laniakea/Development/galaxy-db-sync/.venv/bin/ruff check /home/laniakea/Development/galaxy-db-sync/src/galaxy_db_sync/amazing_data/api/client.py /home/laniakea/Development/galaxy-db-sync/tests/amazing_data/test_async_client.py && /home/laniakea/Development/galaxy-db-sync/.venv/bin/mypy /home/laniakea/Development/galaxy-db-sync/src/galaxy_db_sync/amazing_data/api/client.py` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/amazing_data/test_async_client.py` — add assertions that wrappers delegate through `asyncio.to_thread`
- [ ] `src/galaxy_db_sync/amazing_data/api/client.py` import path — make unit tests deterministic even when real `AmazingData` transitive deps are unavailable
- [ ] Missing async parity tests for `get_trading_calendar_async`, `get_backward_factor_async`, `query_snapshot_async`, `get_balance_sheet_async`, `get_income_statement_async`, `get_cash_flow_async`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real SDK importability in project `.venv` | TEST-01 | Current research found `AmazingData` import can fail due to missing `scipy`; whether to repair env or isolate imports may need one manual confirmation during execution | In the project venv, run `python -c "import AmazingData"` and confirm whether import succeeds after Wave 0 changes |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
