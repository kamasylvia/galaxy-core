---
phase: 06
slug: auto-sync-scheduler-23-12-20
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-12
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (pytest-asyncio configured) |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/scheduler/ -v --tb=short` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds (scheduler tests only), ~90 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/scheduler/ -v --tb=short`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds (scheduler tests)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-00-01 | 00 | 0 | Infrastructure | unit | `pytest tests/scheduler/ -v --tb=short` | created in W0 | pending |
| 06-00-02 | 00 | 0 | Infrastructure | unit | `pytest tests/scheduler/ -v --tb=short` | created in W0 | pending |
| 06-00-03 | 00 | 0 | Infrastructure | unit | `pytest tests/scheduler/ -v --tb=short` | created in W0 | pending |
| 06-01-01 | 01 | 1 | SCHED-04 | unit | `grep '\[scheduler\]' config/settings.toml` | existing file | pending |
| 06-01-02 | 01 | 1 | SCHED-02 | unit | `pytest tests/unit/shared_kernel/utils/test_interval_boundary_checker.py::TestIsLastTradingDayOfPeriod -v` | existing file | pending |
| 06-02-01 | 02 | 2 | SCHED-05 | unit | `grep 'class SyncState' src/galaxy_db_sync/database/models/sync_state.py` | new file | pending |
| 06-02-02 | 02 | 2 | SCHED-05 | unit | `grep 'class SyncStateManager' src/galaxy_db_sync/application/scheduler/state_manager.py` | new file | pending |
| 06-02-03 | 02 | 2 | SCHED-03 | unit | `pytest tests/scheduler/test_retry_handler.py -v --tb=short` | created in W0 | pending |
| 06-03-01 | 03 | 3 | SCHED-06 | unit | `pytest tests/scheduler/test_kline_sync_job.py -v --tb=short` | created in W0 | pending |
| 06-03-02 | 03 | 3 | SCHED-07 | unit | `pytest tests/scheduler/test_calendar_sync_job.py -v --tb=short` | created in W0 | pending |
| 06-04-01 | 04 | 4 | SCHED-01 | unit | `pytest tests/scheduler/test_scheduler_loop.py -v --tb=short` | created in W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [x] `tests/scheduler/__init__.py` — test package init (created in 06-00)
- [x] `tests/scheduler/conftest.py` — shared fixtures (mock_state_manager, mock_boundary_checker, mock_sync_func, mock_calendar_service)
- [x] `tests/scheduler/test_scheduler_config.py` — config loading test stub
- [x] `tests/scheduler/test_scheduler_loop.py` — asyncio loop test stub
- [x] `tests/scheduler/test_retry_handler.py` — retry logic test stub
- [x] `tests/scheduler/test_kline_sync_job.py` — kline sync job test stub
- [x] `tests/scheduler/test_calendar_sync_job.py` — calendar sync job test stub
- [ ] Extend `tests/unit/shared_kernel/utils/test_interval_boundary_checker.py` — add `is_last_trading_day_of_period()` tests (done in 06-01)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Daemon startup/shutdown | Deployment | Requires systemd/service manager | `systemctl start galaxy-sync; systemctl status galaxy-sync` |
| Clock-simulated trigger | Timing edge cases | Time manipulation fragile in tests | Set system clock to 23:00 on last trading day, verify sync triggered |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter (after Wave 0 execution)

**Approval:** pending