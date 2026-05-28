---
phase: 08
phase_name: 重构 K 线表主键
milestone: TBD
status: planning
created: 2026-04-23
---

# Validation Architecture: Phase 08

> 本文件定义验证策略，确保 phase 实现符合研究阶段确定的技术规范。
> 由 `/gsd-plan-phase` 在 Nyquist 模式启用时自动生成。

## Validation Dimensions

| 维度 | 描述 | 验证方法 |
|------|------|---------|
| PK-01 | 模型定义使用组合主键 | 单元测试验证 `primary_key=True` 在两列上 |
| PK-02 | 迁移脚本执行备份-删除-恢复 | 集成测试验证迁移脚本执行 |
| PK-03 | 数据完整性（行数一致） | 集成测试验证备份/恢复行数匹配 |
| PK-04 | hypertable 功能正常 | 集成测试验证 `create_hypertable` 成功 |
| PK-05 | UPSERT 行为不变 | 单元测试验证 `on_conflict_do_update` |
| PK-06 | 查询行为不变 | 单元测试验证 `query_kline_from_db` |
| PK-07 | `model.id` 不再被引用 | 单元测试验证无 `model.id` 代码 |
| PK-08 | 回滚脚本可执行 | 集成测试验证回滚脚本执行 |

## Requirement -> Test Mapping

| 需求 ID | 行为 | 测试类型 | 自动化命令 | 覆盖状态 |
|---------|------|---------|------------|----------|
| PK-01 | 模型定义使用组合主键 | unit | `pytest tests/unit/test_kline_model_pk.py -v` | PLANNED |
| PK-02 | 迁移脚本正确执行备份-删除-恢复 | integration | `pytest tests/integration/test_pk_migration.py -v` | PLANNED |
| PK-03 | 迁移后数据完整性（行数一致） | integration | `pytest tests/integration/test_pk_migration.py -v -k integrity` | PLANNED |
| PK-04 | 迁移后 hypertable 功能正常 | integration | `pytest tests/integration/test_pk_migration.py -v -k hypertable` | PLANNED |
| PK-05 | 迁移后 UPSERT 行为不变 | unit | `pytest tests/unit/test_async_kline_save.py -v` | EXISTING |
| PK-06 | 迁移后查询行为不变 | unit | `pytest tests/unit/test_async_kline_query.py -v` | EXISTING |
| PK-07 | `model.id` 不再被引用 | unit | `pytest tests/ -v -k "not id"` | PLANNED |
| PK-08 | 回滚脚本可正常执行 | integration | 手动执行 `scripts/rollback_pk_migration.py --dry-run` | PLANNED |

## Sampling Rate

- **每次任务提交:** `pytest tests/ -x --timeout=30`
- **每次 wave 合并:** `pytest tests/ -v`
- **Phase 门控:** 完整套件通过 + 手动验证回滚脚本

## Wave 0 Gaps

以下测试需要在执行前创建：

- [ ] `tests/unit/test_kline_model_pk.py` — 验证组合主键定义 (PK-01, PK-07)
- [ ] `tests/integration/test_pk_migration.py` — 验证迁移和回滚 (PK-02, PK-03, PK-04, PK-08)

## Acceptance Criteria

Phase 08 验证通过条件：

1. **所有单元测试通过:** `pytest tests/unit/ -v` exits 0
2. **所有集成测试通过:** `pytest tests/integration/ -v` exits 0
3. **无 `model.id` 引用:** `grep -r "model\.id" src/` returns empty
4. **组合主键定义正确:** `BaseKline` 的 `symbol` 和 `trade_time` 都有 `primary_key=True`
5. **迁移脚本可执行:** `python scripts/migrate_pk_to_symbol_trade_time.py --dry-run` exits 0
6. **回滚脚本可执行:** `python scripts/rollback_pk_migration.py --dry-run` exits 0

---

*Generated from RESEARCH.md Validation Architecture section*
*Created: 2026-04-23*