# 交易日历任务台账（归档）

> 本文件只保留 **阶段归档与历史结论**。当前推进状态请看 `boards/trading_calendar/plan.md`，技术设计请看 `boards/trading_calendar/design.md`。

## 1. 文档职责

- `plan.md`：当前状态、维护边界、风险、下一步。
- `tasks.md`：历史阶段结果归档。
- `design.md`：当前采用的技术设计。

---

## 2. 历史阶段归档总览

| 阶段 | 主题 | 当前归档结论 |
| --- | --- | --- |
| Phase 1 | 数据模型与基础查询接口 | 已完成，模型、交易日查询与基础判断能力已建立 |
| Phase 2 | 外部数据源与缓存回补 | 已完成，已实现 DB-first + akshare fallback |
| Phase 3 | 完整日历持久化 | 已完成，已将交易日与非交易日共同缓存到数据库 |
| Phase 4 | 同步入口与 CLI 集成 | 已完成，服务层同步、批量同步与 `calendar` 命令已接入 |
| Phase 5 | 脚本与验证收口 | 已完成，独立脚本和基础测试基线已建立 |

---

## 3. 已沉淀为基线能力的内容

以下内容已经进入当前代码基线，不再作为独立推进项：

- `TradingCalendar` ORM 模型。
- `get_trading_days()`、`is_trading_day()`、`filter_trading_days()` 查询能力。
- `sync_calendar()`、`sync_current_year()`、`sync_years()` 同步能力。
- `check_and_update_yearly()` 年更检查。
- `AkshareMarket.get_normalized_market()` 市场代码标准化。
- `_fetch_from_akshare()`、`_generate_full_calendar()`、`_save_to_db()` 缓存与持久化流程。
- `application/calendar/command.py` CLI 入口。
- `scripts/fetch_trading_calendar_2010_2026.py` 独立批量同步脚本。

---

## 4. 当前归档视角

### 4.1 阶段目标

让交易日历模块成为项目内统一的交易日语义来源，并通过数据库缓存减少重复外部调用。

### 4.2 当前归档判断

- 状态：`已完成`
- 归档结论：
  - 交易日历查询已采用数据库优先、akshare 回补的主流程。
  - 缓存保存的不只是交易日，而是请求范围内完整日历。
  - 服务层已提供按年、当前年和多年份同步能力。
  - CLI `calendar` 命令与独立同步脚本都已接入现有服务层。
  - K 线完整性检查等上层模块已能直接复用交易日历结果。

### 4.3 收口后归档结论

- 交易日历已成为项目内的统一交易日查询基础设施。
- 当前设计把“查询、缓存补齐、完整日历持久化、同步入口”收敛在同一服务层中。
- 自动化测试基线已存在，但服务行为的高强度断言仍有继续补强空间。
- 当前文档分工已与 `boards/kline` 风格对齐。

---

## 5. 维护约定

后续维护本文件时，只做两类事情：

1. 服务边界、缓存语义或同步入口发生实质变化后，更新对应归档结论。
2. 若市场标准化、完整日历持久化或测试基线发生显著变化，同步更新第 4 节。

不要在本文件中重复写未完成式开发计划、逐项实现 checklist 或实时状态看板。
