# Kline Completeness Checker 技术设计文档

> 本文件只描述 **当前采用的技术设计与实现约束**。当前推进状态请看 `boards/kline_completeness_checker/plan.md`，阶段归档请看 `boards/kline_completeness_checker/tasks.md`。

## 1. 目标

`kline_completeness_checker` 用于回答一个统一问题：

> 在给定 `symbol`、`interval`、`start_date`、`end_date` 的情况下，数据库现有 K 线数据是否已经完整覆盖理论上应存在的数据点？

当前设计目标：

- 统一 K 线完整性检查入口。
- 根据周期选择不同的检查策略。
- 输出主流程可直接消费的缺失区间。
- 避免把非交易日误判为缺失数据。
- 为命令层、同步层和兼容接口提供一致结果模型。

---

## 2. 设计原则

- **单一规则来源**：完整性规则集中在 `kline_completeness_checker.py`。
- **按周期分层**：长周期与短周期采用不同检查策略。
- **交易日优先语义**：完整性判断只针对理论上应存在的数据点。
- **结果模型统一**：所有上层调用方共享 `CompletenessResult`。
- **缺失区间优先**：主流程以 `missing_ranges` 为补数依据，而非散落的逐日判断。

---

## 3. 总体架构

```text
Kline caller
  ↓
KlineCompletenessChecker.check()
  ↓
参数标准化
  ↓
周期分流
  ├─ LongPeriodChecker
  │    ↓
  │  交易日历生成各周期最后交易日
  │    ↓
  │  与数据库时间点集合比较
  │
  └─ ShortPeriodChecker
       ↓
     交易日历生成应有交易日集合
       ↓
     与数据库时间点集合比较

  ↓
CompletenessResult
```

---

## 4. 模块职责

### 4.1 统一入口

**文件**：`src/galaxy_db_bridge/database/services/kline_completeness_checker.py`

职责：

- 标准化 `interval` 与日期参数。
- 根据周期选择长周期或短周期检查器。
- 统一输出 `CompletenessResult`。

### 4.2 长周期检查器

**类**：`LongPeriodChecker`

职责：

- 处理 `month`、`season`、`year`。
- 按周期生成最后交易日集合。
- 比较数据库现有时间点与期望点差集。
- 输出缺失区间与覆盖率。

### 4.3 短周期检查器

**类**：`ShortPeriodChecker`

职责：

- 处理 `week`、`day` 与分钟线。
- 基于交易日历生成目标范围内应有交易日。
- 比较数据库现有时间点与交易日集合。
- 在无交易日范围内直接视为完整。

### 4.4 依赖服务

- `kline_service.query_kline_from_db()`：查询数据库现有 K 线时间点。
- `trading_calendar_service.get_trading_days()`：提供市场级交易日集合。

---

## 5. 结果模型设计

### 5.1 `CompletenessResult`

当前结果结构为：

- `is_complete`：是否完整。
- `missing_count`：缺失点数量。
- `total_count`：理论应有点数量。
- `coverage_ratio`：覆盖率。
- `missing_ranges`：缺失日期区间列表。
- `check_method`：当前使用的检查方法标识。

### 5.2 结果模型约束

- `missing_ranges` 是主流程的标准缺口表达。
- `coverage_ratio` 用于辅助判断与阈值比较。
- `check_method` 仅用于日志、排障和测试断言，不承载业务分支逻辑。

---

## 6. 输入标准化设计

### 6.1 周期参数

`KlineCompletenessChecker.check()` 支持：

- `Interval` 枚举实例。
- 可转换为 `Interval` 的字符串。

### 6.2 日期参数

支持以下输入：

- `date`
- `datetime`
- `%Y%m%d`
- `%Y-%m-%d`
- `%Y/%m/%d`

### 6.3 市场参数

- 若调用方显式传入 `market`，则直接使用。
- 若未传入，则根据 symbol 后缀推断：`.SH -> SSE`、`.SZ -> SZSE`、`.BJ -> BSE`。
- 无后缀时默认回落到 `SSE`。

---

## 7. 长周期检查设计

### 7.1 适用范围

- `Interval.MONTH`
- `Interval.SEASON`
- `Interval.YEAR`

### 7.2 检查方法

1. 查询数据库中的现有时间点。
2. 按周期边界拆分目标范围。
3. 对每个周期调用 `trading_calendar_service.get_trading_days()`。
4. 取每个周期的最后一个交易日作为期望时间点。
5. 计算期望点集合与现有集合的差集。
6. 合并缺失点为 `missing_ranges`。

### 7.3 关键语义

- 长周期完整性按“最后交易日”判断。
- 不再使用自然月末、季末、年末作为期望时间点。
- 若某周期没有交易日，则该周期不会产生期望点。

---

## 8. 短周期检查设计

### 8.1 适用范围

- `Interval.WEEK`
- `Interval.DAY`
- 所有分钟级周期

### 8.2 检查方法

1. 获取目标范围内应有的交易日列表。
2. 查询数据库中的现有时间点。
3. 计算交易日集合与现有集合的差集。
4. 将缺失的日期点合并为 `missing_ranges`。

### 8.3 关键语义

- 无交易日范围直接返回完整结果：`is_complete=True`、`total_count=0`。
- 非交易日不会进入缺口判断。
- `missing_ranges` 只表达应补数据的连续缺口区间。

---

## 9. 辅助接口设计

### 9.1 `get_missing_dates()`

职责：

- 基于 `missing_ranges` 展开为逐日列表。
- 适合调试与辅助场景。

约束：

- 该接口是兼容辅助能力，不应取代主流程对 `missing_ranges` 的直接消费。

### 9.2 `is_data_complete()`

职责：

- 基于 `coverage_ratio` 做快速阈值判断。
- 支持 `min_coverage` 作为最小覆盖率要求。

---

## 10. 与主流程的集成关系

### 10.1 Kline 命令层

命令层通过 `KlineCompletenessChecker.check()` 决定：

- 是否直接返回“已完整”。
- 是否进入同步流程。
- 缺失区间如何传递给后续补数逻辑。

### 10.2 Kline 同步层

同步层基于 `CompletenessResult.missing_ranges` 计算补数范围，避免再维护独立缺口语义。

### 10.3 兼容包装

旧接口如仍存在，只应作为 checker 的代理包装，不再承载独立判断规则。

---

## 11. 测试设计

### 11.1 核心测试文件

- `tests/unit/test_kline_completeness_checker.py`

### 11.2 联动测试文件

- `tests/kline/test_kline_command.py`
- `tests/unit/test_kline_non_trading_day.py`

### 11.3 核心验证目标

- 长周期是否按最后交易日判断完整性。
- 短周期是否只比较交易日。
- 无交易日范围是否返回完整。
- `get_missing_dates()` 与 `is_data_complete()` 是否符合当前结果模型。

---

## 12. 已知约束

- `get_missing_dates()` 会把区间展开为自然日序列，适合辅助用途，不适合重新定义主流程补数语义。
- 默认市场推断依赖 symbol 后缀；无后缀场景会回落到 `SSE`。
- 当前检查器直接依赖全局的 `kline_service` 与 `trading_calendar_service` 实例。

---

## 13. 结论

`kline_completeness_checker` 当前已经完成从“独立工具”到“K 线主流程单一规则来源”的收口。后续维护重点不再是新增另一套完整性逻辑，而是继续保持结果模型、周期语义和联动测试的一致性。
