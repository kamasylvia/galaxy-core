# Requirements: v1.1 重构

**Defined:** 2026-05-28
**Core Value:** 规范化项目架构，聚焦日线同步，提升代码质量与可维护性

## v1.1 Requirements

### 架构规范化 (ARCH)

- [ ] **ARCH-01**: 移除废弃的同步数据库连接文件 `database/core/connection.py`
- [ ] **ARCH-02**: 清理 `kline_completeness_checker.py` 中的同步方法（`check()`, `get_missing_dates()`, `is_data_complete()`），仅保留异步版本
- [ ] **ARCH-03**: 合并重复的区间合并工具函数（`_merge_to_ranges`, `_merge_dates_to_ranges`）到统一工具模块
- [ ] **ARCH-04**: 修复 `BatchSyncResult` 重复 `@dataclass` 装饰器
- [ ] **ARCH-05**: 改善模块命名一致性（如 `empty_query.py` → `empty_query_cache.py`）
- [ ] **ARCH-06**: 检查并移除未使用的导入和代码

### K线同步优化 (KLINE)

- [ ] **KLINE-01**: 保留所有周期支持（分钟线至年线），优化长周期检测逻辑
- [ ] **KLINE-02**: 简化 `LongPeriodChecker` 与 `ShortPeriodChecker` 的重复代码
- [ ] **KLINE-03**: 优化 `IntervalBoundaryChecker` 的长周期边界计算
- [ ] **KLINE-04**: 统一各周期数据同步入口，减少周期类型判断分支

### API调用优化 (API)

- [ ] **API-01**: 用户传入 security_type + start_date + end_date，kline 指令自动判断缺失数据
- [ ] **API-02**: 缺失数据检测优先使用完整日期范围批量查询，而非精确缺失区间
- [ ] **API-03**: 利用 `get_kline(code_list=[...])` 一次查询多只证券，最大化 batch 效率
- [ ] **API-04**: 新上市证券自动识别上市日，跳过上市前日期的 API 查询
- [ ] **API-05**: 空查询缓存机制保留，避免重复查询已知空数据

### 文档 (DOC)

- [ ] **DOC-01**: 重写 README.md，反映实际代码结构、CLI 命令、依赖和架构
- [ ] **DOC-02**: 同步更新 .planning/PROJECT.md 和 .planning/STATE.md 与实际代码状态一致
- [ ] **DOC-03**: 在代码中添加或更新模块级 docstring，说明职责和用法

## Future Requirements

- 全局单例实例改为依赖注入（ARCH-07）— 超出当前重构范围，需更大改动
- 完整单元测试覆盖所有重构后的模块 — 逐步补充

## Out of Scope

| Feature | Reason |
|---------|--------|
| 新增数据源或证券类型 | 本里程碑专注重构与简化 |
| gRPC Scheduler Control | Defer 到后续版本 |
| 性能基准测试 | 非重构核心目标 |
| 数据库 Schema 变更 | 已有主键重构完成，无需再改 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ARCH-01~06 | Phase 1: 代码清理 | Pending |
| KLINE-01~04 | Phase 2: K线优化 | Pending |
| API-01~05 | Phase 3: API优化 | Pending |
| DOC-01~03 | Phase 4: 文档同步 | Pending |

---
*Requirements defined: 2026-05-28*
*Milestone: v1.1 重构*
