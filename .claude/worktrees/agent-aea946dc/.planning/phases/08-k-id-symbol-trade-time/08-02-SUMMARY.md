---
phase: 08-k-id-symbol-trade-time
plan: 02
subsystem: database
tags: [postgresql, timescaledb, migration, async, sqlalchemy]

requires:
  - phase: 08-01
    provides: ORM model with composite PK (symbol, trade_time), async create_hypertable
provides:
  - 主迁移脚本 scripts/migrate_pk_to_symbol_trade_time.py
  - 回滚脚本 scripts/rollback_pk_migration.py
  - 异步数据库迁移流程（备份 -> 删除 -> 创建 -> 恢复 -> 重建 hypertable）
  - 行数验证和 dry-run 支持
affects:
  - 08-03
  - database-schema

tech-stack:
  added: []
  patterns:
    - "Raw SQL migration via async SQLAlchemy session"
    - "Backup-restore pattern for schema migration with data preservation"
    - "Cascading DROP TABLE for TimescaleDB hypertable cleanup"

key-files:
  created:
    - scripts/migrate_pk_to_symbol_trade_time.py
    - scripts/rollback_pk_migration.py
  modified: []

key-decisions:
  - "迁移顺序从小到大（year -> min1）：小表优先，减少长时间锁定风险"
  - "备份表命名格式 kline_{interval}_backup_{YYYYMMDD_HHMMSS}：统一且可追踪"
  - "使用 CASCADE DROP 确保 hypertable 元数据彻底清理"
  - "回滚采用 ALTER TABLE RENAME 而非重新建表：保留原始结构和数据"

patterns-established:
  - "Migration script: async raw SQL with row-count validation at each step"
  - "Rollback script: find backup by pattern, rename to restore, rebuild hypertable"

requirements-completed: [PK-02, PK-03, PK-04, PK-08]

# Metrics
duration: 15min
completed: 2026-04-23
---

# Phase 08 Plan 02: 迁移脚本与回滚脚本 Summary

**异步迁移脚本和回滚脚本，支持 dry-run、备份验证、hypertable 重建，按数据量从小到大顺序迁移 13 个 K 线表**

## Performance

- **Duration:** 15 min
- **Started:** 2026-04-23T16:35:11Z
- **Completed:** 2026-04-23T16:50:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- 创建主迁移脚本 `migrate_pk_to_symbol_trade_time.py`，支持完整的备份-删除-创建-恢复-重建流程
- 创建回滚脚本 `rollback_pk_migration.py`，支持按时间戳和表名选择性回滚
- 两个脚本均使用 `async_db_manager` 进行异步数据库操作
- 每步迁移都有行数验证，确保数据完整性
- 支持 `--dry-run` 和 `--keep-backup` 参数

## Task Commits

Each task was committed atomically:

1. **Task 1: 创建主迁移脚本 migrate_pk_to_symbol_trade_time.py** - `a9d6d43` (feat)
2. **Task 2: 创建回滚脚本 rollback_pk_migration.py** - `2dd33aa` (feat)

## Files Created/Modified
- `scripts/migrate_pk_to_symbol_trade_time.py` - 主迁移脚本：备份旧表、删除旧表、创建新表（组合主键）、恢复数据、重建 hypertable
- `scripts/rollback_pk_migration.py` - 回滚脚本：查找备份表、删除新表、重命名备份表恢复、重建 hypertable

## Decisions Made
- 迁移顺序从小到大（year -> min1）：小表优先，减少长时间锁定风险
- 备份表命名格式 `kline_{interval}_backup_{YYYYMMDD_HHMMSS}`：统一且可追踪
- 使用 `DROP TABLE ... CASCADE` 确保 TimescaleDB hypertable 元数据彻底清理
- 回滚采用 `ALTER TABLE ... RENAME TO` 而非重新建表：保留原始结构和数据（包含 id 列）

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- 发现 08-01 的模型变更提交 `ab49faf` 在 diff 中意外地将组合主键模型 revert 回了旧模型（含 id 列）。该问题属于前序 wave 的遗留问题，不影响 08-02 迁移脚本的正确性（迁移脚本使用 raw SQL 定义目标表结构，不依赖 ORM 模型）。已在执行记录中标注，建议在 08-03 或后续 wave 中修复模型文件。

## Known Stubs

None.

## Threat Flags

None - 迁移脚本不引入新的网络端点、认证路径或文件访问模式。

## User Setup Required

None - 脚本为独立手动执行工具，不需要外部服务配置。

## Next Phase Readiness

- 迁移脚本和回滚脚本已就绪
- 08-03（单元测试和集成测试）可直接引用这两个脚本进行测试
- 建议在执行实际迁移前，先在测试环境运行 `--dry-run` 验证

---
*Phase: 08-k-id-symbol-trade-time*
*Completed: 2026-04-23*
