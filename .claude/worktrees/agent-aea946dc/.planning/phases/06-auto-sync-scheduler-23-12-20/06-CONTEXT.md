# Phase 6: Auto Sync Scheduler - Context

**Gathered:** 2026-04-12 (extended 2026-04-13)
**Status:** Extended - daily integrity check added

<domain>
## Phase Boundary

创建自动同步调度服务，在特定时间自动触发 K 线数据和交易日历的同步，无需手动执行 CLI 命令。

**核心功能:**
1. 每个交易周期最后一天 23:00 → 同步该周期的 K 线数据（日线及以上周期）
2. 每年 12月20日 → 同步下一年的交易日历
3. 每天 00:00 → 检查下一年日历是否已同步（从 12月20日到 12月31日）

**扩展功能 (新增):**
4. 交易日 17:00 → 检查数据库完整性，发现缺失自动补同步
5. K-line 同步完成后 → 验证同步结果，确保数据完整

不在本 phase 内：
- 分钟级数据的实时同步
- 用户手动触发的 CLI 命令（现有功能保持不变）
- 监控告警系统的完整实现（仅记录日志）

</domain>

<decisions>
## Implementation Decisions

### 调度框架
- **D-01:** 使用自定义 asyncio 循环实现调度器
  - 与现有 async 架构一致（`TradingCalendarService`, `KlineService` 已异步化）
  - 无额外依赖（schedule 库、APScheduler）
  - 触发时机基于交易日历动态计算，APScheduler cron 无法直接表达

### 触发时机计算
- **D-02:** 扩展 `IntervalBoundaryChecker` 实现周期最后交易日检测
  - 新增 `is_last_trading_day_of_period(interval, today)` 方法
  - 复用现有 `_get_week_end_date()` / `_get_month_end_date()` 等边界计算逻辑
  - 日历同步触发时机为固定日期（12月20日、每日00:00），无需特殊检测

### 错误处理
- **D-03:** 重试 + 记录策略
  - 同步失败后重试 3 次
  - 重试间隔递增：5分钟 → 15分钟 → 60分钟
  - 全部失败后记录错误日志，等待下次调度周期触发
  - 不发送告警通知（仅日志记录）

### 配置方式
- **D-04:** TOML 配置文件
  - 复用现有 `config/settings.toml`
  - 新增 `[scheduler]` section 配置调度参数
  - 配置项：触发时间、重试策略、同步范围、日志级别

### 每日完整性检查 (扩展)
- **D-19:** 双触发机制：交易日 17:00 + 同步完成后
  - 交易日 17:00：日间检查，交易结束前验证数据完整性
  - 同步完成后触发：等待 K-line 同步（23:00起）完成后再执行检查，可能在非交易日
  - 检查逻辑基于交易日历，非自然日

- **D-20:** 检查范围由配置文件 `[scheduler.check_intervals]` 指定
  - 灵活可控，可单独启用/禁用特定周期的检查
  - 配置格式示例：`check_intervals = ["day", "week"]`

- **D-21:** 发现缺失后自动触发补同步
  - 复用现有 `KlineSyncJob` 逻辑执行补救同步
  - 补同步使用相同重试策略（D-03）

- **D-22:** 新建 `completeness_check_log` 表记录检查详情
  - 与 `sync_state` 表分离，语义清晰
  - 字段：检查时间、检查范围、缺失数、修复结果
  - 便于后续分析检查历史和缺失率趋势

### Claude's Discretion
- 调度器入口文件位置（建议 `src/galaxy_db_sync/application/scheduler/`）
- 状态持久化表结构设计（建议复用现有数据库，新增 `sync_state` 表）
- 多周期同步的执行顺序（日线优先还是并行执行）
- 日志输出的具体格式
- 完整性检查 Job 类命名（建议 `CompletenessCheckJob`）

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 周期边界检测
- `src/galaxy_db_sync/shared_kernel/utils/interval_boundary_checker.py` — 周期边界检查器，需扩展 `is_last_trading_day_of_period()` 方法
- `src/galaxy_db_sync/shared_kernel/enums/interval.py` — Interval 枚举定义

### 交易日历服务
- `src/galaxy_db_sync/database/services/trading_calendar.py` — 已有 `sync_calendar()` 方法，可复用日历同步逻辑
- `src/galaxy_db_sync/application/calendar/command.py` — 日历同步 CLI 入口，逻辑可参考

### K 线同步服务
- `src/galaxy_db_sync/application/kline/command.py` — K 线 CLI 入口，`handle_kline_command_async()` 可复用
- `src/galaxy_db_sync/application/kline/sync_orchestrator.py` — 同步编排逻辑
- `src/galaxy_db_sync/database/services/kline_data_sync.py` — K 线数据同步服务

### 完整性检查 (扩展新增)
- `src/galaxy_db_sync/database/services/kline_completeness_checker.py` — K 线完整性检查器，核心逻辑可复用
- `src/galaxy_db_sync/application/scheduler/kline_sync_job.py` — K 线同步 Job，补同步逻辑可复用

### 配置框架
- `src/galaxy_db_sync/shared_kernel/utils/config_loader/config.py` — TOML 配置加载器
- `config/settings.toml` — 现有配置文件，需新增 `[scheduler]` section

### 项目级指令
- `CLAUDE.md` — 项目架构、命名约定、测试命令与开发约束

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `IntervalBoundaryChecker` — 已有完整的周期边界判断逻辑，可扩展触发检测
- `TradingCalendarService.sync_calendar()` — 日历同步逻辑已实现
- `handle_kline_command_async()` — K 线同步 CLI 入口，核心逻辑可复用
- `config_loader` — TOML 配置加载框架已就绪
- `KlineCompletenessChecker` — 完整性检查器，支持所有周期，核心逻辑可直接复用
- `KlineSyncJob` — K 线同步 Job，补同步逻辑可复用
- `AutoSyncScheduler` — 调度器框架，可扩展完整性检查触发点

### Established Patterns
- 所有服务已异步化（使用 `asyncio.to_thread` 包装同步 SDK 调用）
- CLI 入口使用 `asyncio.run()` 驱动异步命令
- 周期命名统一使用 `interval`（除 SDK 字面参数 `period`）
- 配置通过 TOML 文件 + `get_section()` 加载
- 调度器使用自定义 asyncio 循环（每分钟轮询）

### Integration Points
- 调度器模块已存在（`application/scheduler/`）
- 配置文件需扩展 `[scheduler]` section 添加 `check_intervals`
- 需新增 `completeness_check_log` 数据库表
- 需新增 `CompletenessCheckJob` 类

</code_context>

<specifics>
## Specific Ideas

- 触发时间：周期同步 23:00，日历同步 00:00
- 日历同步起始日期：每年 12月20日
- 日历同步检查窗口：12月20日 至 12月31日
- 重试次数：3 次
- 重试间隔：5分钟 → 15分钟 → 60分钟（递增）
- **完整性检查触发 (新增):** 交易日 17:00 + 同步完成后
- **检查范围 (新增):** 配置文件 `[scheduler.check_intervals]` 指定
- **补救策略 (新增):** 自动触发补同步

</specifics>

<deferred>
## Deferred Ideas

- 分钟级数据实时同步 — 超出当前需求范围
- 监控告警系统（邮件、短信、Webhook） — 仅日志记录，告警系统另行规划
- 用户手动触发的覆盖机制（如强制同步） — 现有 CLI 命令已满足

</deferred>

---

*Phase: 06-auto-sync-scheduler*
*Context gathered: 2026-04-12*
*Extended: 2026-04-13 — daily integrity check added*