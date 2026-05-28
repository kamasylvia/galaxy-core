# 交易日历技术设计文档

> 本文件只描述 **当前采用的技术设计与实现约束**。当前推进状态请看 `boards/trading_calendar/plan.md`，阶段归档请看 `boards/trading_calendar/tasks.md`。

## 1. 目标

`trading_calendar` 用于提供项目内统一的交易日语义，支撑：

- 范围内交易日查询。
- 单日是否为交易日判断。
- 日期列表中的交易日过滤。
- 按年或按范围同步交易日历数据。
- K 线完整性检查与数据同步场景的交易日判定。

当前设计目标：

- 优先使用数据库缓存，减少外部调用。
- 在缓存不足时从 akshare 回补数据。
- 将请求范围内的完整日历（含非交易日）写回数据库。
- 让服务层、CLI 和独立脚本复用同一套同步语义。

---

## 2. 设计原则

- **数据库优先**：查询先读数据库缓存。
- **按需回补**：缓存不足时才调用 akshare。
- **完整日历持久化**：保存请求范围内全部日期，而不只保存交易日。
- **市场口径统一**：通过市场标准化函数统一输入市场代码。
- **上层透明复用**：K 线、CLI 与脚本都复用同一服务层。

---

## 3. 总体架构

```text
Caller
  ↓
TradingCalendarService
  ├─ 查询数据库缓存
  │    ├─ 覆盖充分 → 直接返回
  │    └─ 覆盖不足 → 调用 akshare
  │                     ↓
  │               生成完整日历
  │                     ↓
  │               写回数据库缓存
  │
  └─ 同步接口
       ├─ sync_calendar(year)
       ├─ sync_current_year()
       └─ sync_years(start_year, end_year)
```

---

## 4. 模块职责

### 4.1 数据模型

**文件**：`src/galaxy_db_bridge/database/models/trading_calendar.py`

职责：

- 定义 `trading_calendar` 表结构。
- 通过 `(market, trade_date)` 唯一约束保证单市场单日期唯一。
- 保存 `is_trading_day` 与 `year` 等字段，支撑查询与同步。

### 4.2 服务层

**文件**：`src/galaxy_db_bridge/database/services/trading_calendar.py`

职责：

- 提供查询、过滤、同步、年更等核心业务能力。
- 封装缓存判断与外部回补逻辑。
- 负责把外部交易日列表转为完整日历并持久化。

### 4.3 市场标准化

**文件**：`src/galaxy_db_bridge/shared_kernel/enums/akshare.py`

职责：

- 将 `SSE` / `SH` / `上交所` 等不同形式映射到统一市场代码。
- 为服务层提供统一输入口径。

### 4.4 CLI 与脚本入口

- `src/galaxy_db_bridge/application/calendar/command.py`
- `scripts/fetch_trading_calendar_2010_2026.py`

职责：

- 复用服务层同步能力。
- 提供命令行与批量脚本入口。

---

## 5. 数据模型设计

### 5.1 核心字段

`TradingCalendar` 当前核心字段包括：

- `id`
- `market`
- `trade_date`
- `is_trading_day`
- `year`
- `created_at`
- `updated_at`

### 5.2 关键约束

- 唯一约束：`(market, trade_date)`。
- `year` 字段用于按年删除、重建和统计同步数据。

---

## 6. 查询与缓存设计

### 6.1 `get_trading_days()`

职责：

- 获取指定日期范围内的交易日列表。

处理流程：

1. 标准化市场代码。
2. 查询数据库中的完整日历记录。
3. 判断数据库是否已完整覆盖请求范围。
4. 若覆盖不足，则调用 `_fetch_from_akshare()`。
5. 将回补结果通过 `_save_to_db()` 写入数据库。
6. 重新查询并返回交易日列表。

### 6.2 `is_trading_day()`

职责：

- 查询单日是否为交易日。

处理流程：

1. 先查数据库。
2. 若不存在，则仅针对该日调用外部数据源并补齐缓存。
3. 再从数据库确认并返回结果。

### 6.3 `filter_trading_days()`

职责：

- 从给定日期列表中过滤出交易日。

处理流程：

1. 先查数据库中已知交易日。
2. 对未覆盖日期范围做一次外部回补。
3. 重新查询并返回过滤后的交易日列表。

---

## 7. 外部数据源设计

### 7.1 数据来源

当前使用：

- `ak.tool_trade_date_hist_sina()`

### 7.2 处理方式

- 将返回结果转换为 `date`。
- 只保留请求范围内的交易日。
- 若外部调用失败，记录日志并返回空列表。

### 7.3 关键约束

- 当前外部数据源返回的是全市场交易日历，服务层通过标准化市场代码维持统一接口。
- 外部数据源异常时不会直接伪造结果，而是回落为空列表并由调用方承接后果。

---

## 8. 完整日历持久化设计

### 8.1 `_generate_full_calendar()`

职责：

- 基于请求范围和交易日列表生成 `(date, is_trading_day)` 序列。
- 把非交易日也显式写入完整日历。

### 8.2 `_save_to_db()`

职责：

- 根据请求范围或交易日边界生成完整日历。
- 删除对应年份的旧数据。
- 批量写入新的完整日历记录。

### 8.3 当前实现约束

- `_save_to_db()` 当前会把 `SSE`、`SZSE`、`BSE` 统一落库为 `SSE`。
- 这意味着查询层的市场标准化与保存层的市场归并需要一起理解和维护。

---

## 9. 同步流程设计

### 9.1 `sync_calendar(year, market)`

职责：

- 手动同步指定年份日历。

流程：

1. 生成该年份起止日期。
2. 从 akshare 获取交易日。
3. 删除该年旧数据。
4. 重新生成完整日历并写入数据库。
5. 返回交易日数量。

### 9.2 `sync_current_year(market)`

职责：

- 复用 `sync_calendar()` 同步当前年份。

### 9.3 `sync_years(start_year, end_year, market)`

职责：

- 异步逐年同步多个年份。
- 使用 `asyncio.to_thread()` 包装同步方法，避免阻塞事件循环。
- 返回 `total` / `added` / `updated` / `skipped` 统计信息。

### 9.4 `check_and_update_yearly(market)`

职责：

- 在 12 月 31 日触发下一年度同步。
- 当前为基于系统日期的条件式年更检查。

---

## 10. CLI 与脚本设计

### 10.1 CLI 命令

**文件**：`src/galaxy_db_bridge/application/calendar/command.py`

能力：

- 提供 `calendar` 子命令。
- 支持 `--start-year` 与 `--end-year`。
- 做年份范围校验。
- 逐年调用 `trading_calendar_service.sync_calendar()`。

### 10.2 独立脚本

**文件**：`scripts/fetch_trading_calendar_2010_2026.py`

能力：

- 直接调用 `TradingCalendarService.sync_years()`。
- 固定同步 2010-2026 年范围。
- 输出统计信息并在失败时退出。

---

## 11. 与 K 线模块的集成关系

### 11.1 Kline 完整性检查

`kline_completeness_checker.py` 当前通过 `trading_calendar_service.get_trading_days()`：

- 为长周期生成各周期最后交易日。
- 为短周期生成应有交易日集合。

### 11.2 集成约束

- 若交易日历结果异常，K 线完整性判断会直接受到影响。
- 因此交易日历模块应继续被视为上层时间语义的基础设施，而不是辅助脚本。

---

## 12. 测试设计

### 12.1 自动化测试

- `tests/unit/test_fetch_trading_calendar.py`

覆盖内容：

- 脚本可导入。
- 年份范围常量。
- `main()` 对 `sync_years()` 的调用。
- 脚本 shebang 与 main guard。

### 12.2 辅助性脚本验证

- `tests/unit/test_trading_calendar_functionality.py`
- `tests/unit/test_market_mapping.py`
- `tests/unit/test_full_calendar.py`

这些文件更偏向人工观察与调试式验证，说明当前对服务本体行为的断言式自动化覆盖仍有补强空间。

---

## 13. 已知约束

- 保存层当前会把国内市场统一写成 `SSE`，这与查询层支持多种市场别名的行为需要一起理解。
- 若 `_fetch_from_akshare()` 返回空列表，某些查询场景可能无法补齐非交易日缓存。
- 当前测试体系里，服务本体的大量行为仍主要依靠脚本式验证而非严格断言。

---

## 14. 结论

`trading_calendar` 当前已经完成从“计划中的支持模块”到“项目基础时间语义服务”的转变。后续维护重点不再是补齐基础接口，而是保持缓存语义、市场口径和上层复用关系稳定，并逐步把脚本式验证补强为更稳固的自动化断言。
