# Roadmap: v1.1 重构

## Milestones

- **v1.1 重构** — Phase 10~13
- **v1.4 gRPC Scheduler Control** — Phase 6~9 (completed / deferred)

## Phases

### Phase 10: 代码清理与架构规范化

**Goal:** 移除废弃代码，修复已知问题，改善模块命名与结构

**Depends on:** None (本里程碑起始)

**Requirements**: ARCH-01, ARCH-02, ARCH-03, ARCH-04, ARCH-05, ARCH-06

**Success Criteria**:
- `database/core/connection.py` 已移除（确认无引用）
- `kline_completeness_checker.py` 同步方法已清理，仅保留异步版本
- 区间合并工具函数已统一到单一模块
- `BatchSyncResult` 重复装饰器已修复
- 模块命名已改善（`empty_query.py` 等）
- 未使用的导入和代码已清理
- 所有现有测试仍通过

**Key Risks**:
- 删除同步 checker 方法时需确认 scheduler 和其他调用点已使用异步版本
- 移除 `connection.py` 时需确认无遗留引用

---

### Phase 11: K线同步逻辑优化

**Goal:** 简化并优化长周期与短周期检测逻辑，统一同步入口

**Depends on:** Phase 10

**Requirements**: KLINE-01, KLINE-02, KLINE-03, KLINE-04

**Success Criteria**:
- `LongPeriodChecker` 与 `ShortPeriodChecker` 重复代码已提取到基类或工具函数
- `IntervalBoundaryChecker` 长周期边界计算逻辑已优化
- 各周期数据同步入口统一，减少周期类型判断分支
- 所有周期（分钟线至年线）同步功能正常
- 完整性检查逻辑更清晰，易于维护

**Key Risks**:
- 重构 checker 逻辑时需保持检测准确性
- 长周期边界计算涉及复杂日期逻辑，需谨慎验证

---

### Phase 12: API调用策略优化

**Goal:** 优化缺失数据检测与API调用策略，最小化调用次数

**Depends on:** Phase 11

**Requirements**: API-01, API-02, API-03, API-04, API-05

**Success Criteria**:
- 用户传入 security_type + start_date + end_date 后，系统自动判断缺失数据
- 缺失数据检测优先使用完整日期范围批量查询（而非精确缺失区间）
- 单批次 API 查询最大化证券数量（利用 `code_list` 参数）
- 新上市证券自动识别上市日，跳过上市前日期查询
- 空查询缓存机制正常工作，避免重复查询
- API 调用次数较重构前显著减少

**Key Decisions to Make**:
- 缺失比例阈值：当缺失比例超过多少时，使用完整范围查询替代精确区间？
- 证券 batch 大小：单次 API 查询最多多少只证券？
- 上市日数据来源：从数据库 `stock_basic` 表获取，还是首次查询时推断？

**Key Risks**:
- 完整范围查询可能返回大量已有数据，依赖 UPSERT 去重
- 上市日推断不准确可能导致上市前数据被误判为缺失

---

### Phase 13: 文档同步与README重写

**Goal:** 重写 README，同步 .planning 文档与实际代码状态

**Depends on:** Phase 12

**Requirements**: DOC-01, DOC-02, DOC-03

**Success Criteria**:
- README.md 准确反映实际目录结构、CLI 命令、依赖和架构
- .planning/PROJECT.md 和 STATE.md 与实际代码状态一致
- 各模块添加或更新了模块级 docstring
- 提交原则文档化：最小数量提交，每个提交尽量详细

**Key Risks**:
- README 再次过时 — 需建立更新机制或提醒

---

## Progress

| Phase | Name | Requirements | Status |
|-------|------|--------------|--------|
| 10 | 代码清理与架构规范化 | ARCH-01~06 | Not started |
| 11 | K线同步逻辑优化 | KLINE-01~04 | Not started |
| 12 | API调用策略优化 | API-01~05 | Not started |
| 13 | 文档同步与README重写 | DOC-01~03 | Not started |

---
*Roadmap created: 2026-05-28*
*Milestone: v1.1 重构*
*Phase numbering continues from previous milestone (ended at Phase 9)*
