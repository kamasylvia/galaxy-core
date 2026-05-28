---
phase: 02
slug: async-sync-orchestrator
status: draft
nyquist_compliant: true
wave_0_complete: n/a
created: 2026-04-07
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest tests/unit/test_async_sync_orchestrator.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/unit/test_async_sync_orchestrator.py tests/unit/test_execute_kline_query.py tests/kline/test_kline_command.py tests/unit/test_kline_data_sync.py -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/unit/test_async_sync_orchestrator.py -q`
- **After every plan wave:** Run `.venv/bin/pytest tests/unit/test_async_sync_orchestrator.py tests/unit/test_execute_kline_query.py tests/kline/test_kline_command.py tests/unit/test_kline_data_sync.py -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | ASYNC-02, TEST-01, PERF-01 | unit | `.venv/bin/pytest tests/unit/test_async_sync_orchestrator.py -q` | ✅ | ⬜ pending |
| 02-01-02 | 01 | 1 | ASYNC-02, TEST-01, PERF-01 | unit + lint + type | `.venv/bin/pytest tests/unit/test_async_sync_orchestrator.py -q && .venv/bin/ruff check src/galaxy_db_sync/application/kline/sync_orchestrator.py tests/unit/test_async_sync_orchestrator.py && .venv/bin/mypy src/galaxy_db_sync/application/kline/sync_orchestrator.py` | ✅ | ⬜ pending |
| 02-02-01 | 02 | 2 | ASYNC-02, TEST-01, DATA-01 | unit | `.venv/bin/pytest tests/unit/test_execute_kline_query.py tests/unit/test_async_sync_orchestrator.py -q` | ✅ | ⬜ pending |
| 02-02-02 | 02 | 2 | ASYNC-02, TEST-01, DATA-01 | unit + lint + type | `.venv/bin/pytest tests/kline/test_kline_command.py tests/unit/test_execute_kline_query.py -q && .venv/bin/ruff check src/galaxy_db_sync/application/kline/sync_orchestrator.py tests/unit/test_execute_kline_query.py tests/kline/test_kline_command.py && .venv/bin/mypy src/galaxy_db_sync/application/kline/sync_orchestrator.py src/galaxy_db_sync/application/kline/command.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify coverage
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
