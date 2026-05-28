# Kline Completeness Checker 当前推进计划

> 本文件只负责 **当前进度管理**。历史归档请看 `boards/kline_completeness_checker/tasks.md`，技术设计请看 `boards/kline_completeness_checker/design.md`。

## 1. 当前结论

- **当前阶段**：基础能力已完成，进入依赖侧维护。
- **当前焦点**：保持 checker 与 `kline` 主流程的单一完整性语义一致。
- **当前判断**：`kline_completeness_checker.py` 已成为 K 线完整性判断的唯一规则来源，长周期与短周期策略、缺失区间表达和关键回归测试已经对齐。

---

## 2. 当前状态看板

| 事项 | 状态 | 说明 |
| --- | --- | --- |
| 结果模型 | 已完成 | `CompletenessResult` 已统一输出 `is_complete`、`missing_count`、`total_count`、`coverage_ratio`、`missing_ranges`、`check_method` |
| 分层检查策略 | 已完成 | `LongPeriodChecker` / `ShortPeriodChecker` 已按周期分层 |
| 长周期最后交易日语义 | 已完成 | 月 / 季 / 年线期望点已改为交易日历中的最后交易日 |
| 短周期交易日对比 | 已完成 | 周线及以下已基于交易日集合与数据库集合对比 |
| 主流程接入 | 已完成 | 命令层与同步层已统一依赖 `kline_completeness_checker` |
| 辅助接口 | 已完成 | `get_missing_dates()` 与 `is_data_complete()` 已提供兼容辅助能力 |
| 回归验证 | 已完成 | `tests/unit/test_kline_completeness_checker.py` 与 K 线联动测试已覆盖关键场景 |

---

## 3. 当前结论后的维护重点

### 3.1 已完成收口项

- `KlineCompletenessChecker.check()` 已支持 `Interval | str` 与多种日期入参标准化。
- 长周期检查已通过 `trading_calendar_service.get_trading_days()` 生成各周期最后交易日集合。
- 短周期在“目标范围内没有交易日”时会返回 `is_complete=True`、`total_count=0`。
- 主流程缺失区间已统一复用 `CompletenessResult.missing_ranges`。
- `tests/unit/test_kline_completeness_checker.py` 已覆盖长周期、短周期、无交易日与辅助接口场景。

### 3.2 当前维护边界

- 后续若调整完整性规则，应优先修改 `src/galaxy_db_bridge/database/services/kline_completeness_checker.py`，不要在命令层、同步层或兼容包装里再复制判断逻辑。
- 若调整 `CompletenessResult` 字段或 `missing_ranges` 语义，必须同步检查 `kline` 命令层、同步层和相关测试。
- 若调整长周期语义，必须同时维护 `tests/unit/test_kline_completeness_checker.py` 中的最后交易日断言。

### 3.3 当前验证结果

- 直接测试文件：
  - `tests/unit/test_kline_completeness_checker.py`
- 联动验证文件：
  - `tests/kline/test_kline_command.py`
  - `tests/unit/test_kline_non_trading_day.py`
- 当前基线结论：完整 / 不完整 / 非交易日 / 长周期最后交易日语义已完成回归覆盖。

### 3.4 文档维护要求

- `plan.md` 继续只维护当前状态、风险和维护边界。
- `tasks.md` 只记录阶段归档，不再回写执行过程。
- `design.md` 只保留当前采用的结构、结果模型与检查策略。

---

## 4. 当前推荐维护顺序

### Maintenance A：保持单一规则来源

- [x] `KlineCompletenessChecker.check()` 成为主流程统一入口。
- [x] `CompletenessResult` 成为共享结果模型。
- [x] `missing_ranges` 成为缺失区间唯一表达。

### Maintenance B：保持周期语义稳定

- [x] 长周期使用最后交易日语义。
- [x] 短周期仅比较理论上应存在的交易日。
- [x] 无交易日范围不被误判为缺失。

### Maintenance C：持续回归验证

- [x] Checker 单元测试已覆盖核心分支。
- [x] Kline 命令层联动测试已覆盖依赖场景。
- [x] 文档分工已与 `boards/kline` 结构对齐。

---

## 5. 验收标准

以下条目全部满足后，可继续视为“已完成、仅维护”：

- [x] 长周期与短周期使用不同但统一封装的检查策略。
- [x] 长周期缺口按最后交易日计算，而非自然周期末。
- [x] 非交易日范围不会被误判为数据缺失。
- [x] 主流程共享 `CompletenessResult` 与 `missing_ranges`。
- [x] 关键测试已覆盖 checker 主分支与 K 线联动场景。
- [x] 三份文档职责已与 `boards/kline` 对齐。

---

## 6. 后续维护风险

### 风险 1：结果模型漂移

- 若命令层或同步层再次绕过 `CompletenessResult`，会重新造成“是否完整”和“补哪些区间”不一致。

### 风险 2：长周期语义回退

- 若未来重新按自然月末 / 季末 / 年末判断，现有测试与业务语义都会失真。

### 风险 3：辅助接口被误当主流程

- `get_missing_dates()` 会把区间展开为逐日列表，适合辅助场景，不应替代主流程的 `missing_ranges` 语义。

---

## 7. 后续更新模板

### 本轮目标

- 目标 1：保持完整性规则单源。
- 目标 2：补充规则变更后的测试或文档同步。

### 本轮完成

- [ ] 已同步状态变化。
- [ ] 已更新相关测试 / 文档。

### 本轮发现

- 问题：
- 影响：
- 结论：

### 下一步

- [ ] 下一步 1
- [ ] 下一步 2
