# 交易日历当前推进计划

> 本文件只负责 **当前进度管理**。历史归档请看 `boards/trading_calendar/tasks.md`，技术设计请看 `boards/trading_calendar/design.md`。

## 1. 当前结论

- **当前阶段**：核心能力已完成，进入稳定维护。
- **当前焦点**：保持“数据库优先 + akshare 回补 + 完整日历缓存”这条主语义稳定。
- **当前判断**：`trading_calendar.py` 已具备查询、过滤、按年同步、批量同步和年更检查能力，并已被 K 线完整性判断和 CLI `calendar` 命令复用。

---

## 2. 当前状态看板

| 事项 | 状态 | 说明 |
| --- | --- | --- |
| 数据模型 | 已完成 | `TradingCalendar` 已包含 `market`、`trade_date`、`is_trading_day`、`year` 与唯一约束 |
| 查询服务 | 已完成 | `get_trading_days()` / `is_trading_day()` / `filter_trading_days()` 已可用 |
| 数据源接入 | 已完成 | 已接入 `ak.tool_trade_date_hist_sina()` 作为外部交易日来源 |
| 完整日历缓存 | 已完成 | `_save_to_db()` 会生成并保存交易日 + 非交易日的完整日历 |
| 同步能力 | 已完成 | 已支持 `sync_calendar()`、`sync_current_year()`、`sync_years()` |
| 年更机制 | 已完成 | `check_and_update_yearly()` 已存在 |
| CLI 接入 | 已完成 | `application/calendar/command.py` 已提供 `calendar` 命令 |
| 测试基线 | 部分完成 | 自动化覆盖已有，但部分验证仍以脚本式测试存在 |

---

## 3. 当前结论后的维护重点

### 3.1 已完成收口项

- `get_trading_days()` 已采用数据库优先查询，不足时再回补 akshare 并刷新缓存。
- `is_trading_day()` 与 `filter_trading_days()` 已共享同一套缓存补齐思路。
- `_generate_full_calendar()` 与 `_save_to_db()` 已不只保存交易日，还保存请求范围内的非交易日。
- `sync_calendar()`、`sync_current_year()`、`sync_years()` 已提供手动与批量同步能力。
- `application/calendar/command.py` 已支持年份参数校验与逐年同步。
- K 线完整性检查已通过 `trading_calendar_service.get_trading_days()` 复用交易日历结果。

### 3.2 当前维护边界

- 后续若改缓存策略，应优先维护 `trading_calendar.py`，不要在调用方重新实现“缺缓存就拉外部数据”的逻辑。
- 后续若改市场代码规则，应同步检查 `AkshareMarket.get_normalized_market()` 与 `_save_to_db()` 中的市场归一化行为。
- 后续若改同步范围或脚本，必须同步检查 `scripts/fetch_trading_calendar_2010_2026.py`、CLI 命令和相关测试。

### 3.3 当前验证结果

- 自动化测试文件：
  - `tests/unit/test_fetch_trading_calendar.py`
- 辅助性脚本 / 手工验证文件：
  - `tests/unit/test_trading_calendar_functionality.py`
  - `tests/unit/test_market_mapping.py`
  - `tests/unit/test_full_calendar.py`
- 当前基线结论：脚本、服务导入、年份范围和基础同步入口已有验证；服务行为的断言式自动化覆盖仍偏弱。

### 3.4 文档维护要求

- `plan.md` 继续只保留当前状态、维护边界和风险。
- `tasks.md` 只保留阶段归档与历史结论。
- `design.md` 只描述当前实际采用的 DB-first + full-calendar-cache 方案，不再保留未完成式计划描述。

---

## 4. 当前推荐维护顺序

### Maintenance A：保持缓存主语义稳定

- [x] 查询优先读数据库。
- [x] 缓存不足时回补 akshare。
- [x] 保存时写入完整日历而非仅交易日。

### Maintenance B：保持同步入口一致

- [x] 服务层已统一提供按年与批量同步能力。
- [x] CLI `calendar` 命令已复用服务层同步逻辑。
- [x] 独立脚本 `fetch_trading_calendar_2010_2026.py` 已复用 `sync_years()`。

### Maintenance C：持续补强验证

- [x] 基础脚本导入与年份范围已有自动化覆盖。
- [x] 市场映射与完整日历生成已有辅助验证脚本。
- [x] 文档分工已与 `boards/kline` 风格对齐。

---

## 5. 验收标准

以下条目全部满足后，可继续视为“已完成、仅维护”：

- [x] 交易日、是否交易日和交易日过滤接口均可用。
- [x] 缓存不足时可自动从 akshare 补齐并写回数据库。
- [x] 数据库中保存的是请求范围内完整日历，而不只是交易日。
- [x] 已支持按年同步、批量同步和 CLI 同步入口。
- [x] K 线相关模块已可复用该服务提供的交易日结果。
- [x] 三份文档职责已与 `boards/kline` 对齐。

---

## 6. 后续维护风险

### 风险 1：市场归一化规则不一致

- 当前查询层使用 `AkshareMarket.get_normalized_market()`，保存层又会把 `SSE/SZSE/BSE` 统一落成 `SSE`。若后续修改其中一侧而不同步另一侧，可能导致查询与存储口径分叉。

### 风险 2：测试口径偏脚本化

- 当前不少交易日历验证文件仍以打印和人工观察为主，若核心逻辑变动，自动化断言可能不足以第一时间发现问题。

### 风险 3：缓存覆盖判断被绕过

- 若调用方自行拼接外部回补逻辑，容易破坏“数据库优先 + 完整日历覆盖判断”的当前语义。

---

## 7. 后续更新模板

### 本轮目标

- 目标 1：保持缓存与同步语义一致。
- 目标 2：补充关键服务行为的自动化验证。

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
