---
phase: 07
phase_name: Full Async Database Layer
milestone: v1.3
status: planning
created: 2026-04-16
---

# Context: Phase 7 - Full Async Database Layer

## Problem Statement

异步调用链中存在同步阻塞点，导致数据库交互无法真正并发：

```
CLI (async) → handle_kline_command_async → batch_sync_kline_data_async
  → _group_by_missing_ranges → missing_data_tracker (同步阻塞!)
```

## Current Architecture

**已异步化的部分：**
- `database/services/kline.py` — KlineService 全异步 ✓
- `database/services/kline_data_sync.py` — 批量同步服务（但内部调用同步 missing_data_tracker）
- `database/services/kline_completeness_checker.py` — 完整性检查全异步 ✓
- `application/kline/command.py` — CLI 入口使用 asyncio.run() ✓
- `application/scheduler/*` — 调度器全异步 ✓

**阻塞点（同步 db_manager）：**

| 服务 | 文件 | 当前模式 | 优先级 |
|-----|-----|---------|--------|
| MissingDataTracker | `missing_data_tracker.py` | 全同步 `db_manager.session()` | HIGH |
| EmptyQueryResultService | `empty_query.py` | 全同步 `db_manager.session()` | MEDIUM |
| TradingCalendarService (sync methods) | `trading_calendar.py` | 混合：部分同步 `db_manager.get_session()` | LOW |
| KlineCompletenessChecker (sync check) | `kline_completeness_checker.py` | 混合：同步 `check()` 方法 | LOW |

## Dependency Analysis

### Call Chain (HIGH Priority)

```
batch_sync_kline_data_async()
  └── _group_by_missing_ranges()
       └── missing_data_tracker.get_known_missing_ranges() ← 同步阻塞!
       └── missing_data_tracker.is_range_confirmed_missing() ← 同步阻塞!
```

### Call Chain (MEDIUM Priority)

```
sync_kline_data_async()
  └── _check_empty_query_cache() 或类似
       └── empty_query_service.is_confirmed_empty() ← 同步阻塞!
```

## Key Patterns to Follow

现有异步服务的模式（参考 `kline.py`）：

```python
async with async_db_manager.session() as session:
    stmt = select(Kline).where(...)
    result = await session.execute(stmt)
    data = result.scalars().all()
```

vs 同步模式（需要消除）：

```python
with db_manager.session() as session:
    results = session.query(CompletenessCheckResult).filter(...).all()
```

## Constraints

1. **不改变外部行为** — CLI 命令语义、输出格式保持不变
2. **保持数据完整性** — 异步改造不影响数据一致性
3. **渐进式改造** — 按优先级分阶段实施
4. **测试覆盖** — 每个改造的文件需要对应的异步测试

## Success Criteria

- 所有异步路径中不再有 `db_manager.session()` 或 `db_manager.get_session()` 调用
- `missing_data_tracker.py` 提供完整 async API
- `empty_query.py` 提供完整 async API
- 异步测试覆盖新增的 async 方法