---
phase: 10
slug: code-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-28
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/unit/ -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit/ -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | ARCH-04 | — | N/A | lint | `ruff check src/galaxy_db_sync/database/services/kline_data_sync.py` | ✅ | ⬜ pending |
| 10-02-01 | 02 | 1 | ARCH-03 | — | N/A | unit | `pytest tests/unit/ -k "date_range" -x` | ❌ W0 | ⬜ pending |
| 10-03-01 | 03 | 2 | ARCH-05 | — | N/A | unit | `pytest tests/unit/test_empty_query.py -x` | ✅ | ⬜ pending |
| 10-03-02 | 03 | 2 | ARCH-05 | — | N/A | migration | `alembic upgrade head` | ✅ | ⬜ pending |
| 10-04-01 | 04 | 3 | ARCH-02 | — | N/A | unit | `pytest tests/unit/test_kline_completeness_checker.py -x` | ✅ | ⬜ pending |
| 10-04-02 | 04 | 3 | ARCH-02 | — | N/A | unit | `pytest tests/unit/test_kline_data_sync.py -x` | ✅ | ⬜ pending |
| 10-05-01 | 05 | 4 | ARCH-01 | — | N/A | unit + integration | `pytest tests/ -x` | ✅ | ⬜ pending |
| 10-06-01 | 06 | 6 | ARCH-06 | — | N/A | lint | `ruff check .` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_date_range_utils.py` — new test file for unified merge function (ARCH-03)
- [ ] `tests/unit/test_empty_query_cache.py` — rename of `test_empty_query.py` (ARCH-05)

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
