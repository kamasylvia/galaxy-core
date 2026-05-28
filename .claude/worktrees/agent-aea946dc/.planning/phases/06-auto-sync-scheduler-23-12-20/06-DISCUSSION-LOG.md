# Phase 6: Auto Sync Scheduler - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-12 (extended 2026-04-13)
**Phase:** 06-auto-sync-scheduler
**Areas discussed:** 调度框架选择, 触发时机计算, 错误处理策略, 配置方式, 每日完整性检查(扩展)

---

## 调度框架选择

| Option | Description | Selected |
|--------|-------------|----------|
| schedule 库 | 轻量级、无额外依赖。适合简单固定间隔调度 | |
| APScheduler | 功能完整（持久化、动态添加任务、多种触发器） | |
| 自定义 asyncio 循环 | 基于 asyncio 的自定义循环，配合 IntervalBoundaryChecker 计算触发时间 | ✓ |

**User's choice:** 自定义 asyncio 循环
**Notes:** 与现有 async 架构一致，无额外依赖，触发时机基于交易日历动态计算，APScheduler cron 无法直接表达"周期最后交易日 23:00"

---

## 触发时机计算

| Option | Description | Selected |
|--------|-------------|----------|
| 扩展 IntervalBoundaryChecker | 新增 is_last_trading_day_of_period() 方法，复用现有边界计算逻辑 | ✓ |
| 新建专用检测器 | 创建 SyncTriggerDetector 专门检测触发时机，职责分离 | |

**User's choice:** 扩展 IntervalBoundaryChecker
**Notes:** 复用 `_get_week_end_date()` 等已有方法，代码一致，减少重复

---

## 错误处理策略

| Option | Description | Selected |
|--------|-------------|----------|
| 重试 + 记录 | 失败后重试 3 次，间隔递增，全部失败后记录错误日志 | ✓ |
| 跳过 + 记录 | 失败后立即跳过，仅记录错误日志 | |
| 告警 + 人工介入 | 失败后发送通知，不重试，等待人工介入 | |

**User's choice:** 重试 + 记录
**Notes:** 重试次数 3，间隔 5/15/60 分钟，全部失败后等待下次调度

---

## 配置方式

| Option | Description | Selected |
|--------|-------------|----------|
| TOML 配置文件 | 复用 config/settings.toml，新增 [scheduler] section | ✓ |
| CLI 参数 | 通过 CLI 参数配置，适合临时调试 | |
| TOML + CLI 覆盖 | TOML 配置为主，CLI 参数可覆盖 | |

**User's choice:** TOML 配置文件
**Notes:** 与项目配置框架一致，复用 `get_section()` 加载

---

## Claude's Discretion

- 调度器入口文件位置
- 状态持久化表结构设计
- 多周期同步的执行顺序
- 日志输出的具体格式

---

## Deferred Ideas

- 分钟级数据实时同步 — 超出当前需求范围
- 监控告警系统 — 仅日志记录，告警系统另行规划

---

## 每日完整性检查 (扩展 2026-04-13)

### 触发时机 (完整性检查)

| Option | Description | Selected |
|--------|-------------|----------|
| 同步后验证 | 在 K-line 同步(23:00)完成后运行，验证同步结果 | |
| 日间检查 | 早上08:00检查，为当日交易做准备 | |
| 夜间检查 | 凌晨06:00检查，夜间任务完成后 | |

**User's choice:** 交易日 17:00 + 同步完成后触发
**Notes:** 
- 检查逻辑基于交易日历，非自然日
- 同步在交易日 23:00 开始，检查紧随其后，可能在非交易日
- 双触发机制：交易日 17:00 日间检查 + 同步完成后验证

---

### 检查范围

| Option | Description | Selected |
|--------|-------------|----------|
| 仅当天同步周期 | 只检查当天同步的周期（如日线查当日），效率最高 | |
| 配置文件筛选 | 检查配置文件中指定的 intervals 列表，灵活可控 | ✓ |
| 全量检查 | 检查所有证券的所有周期，耗时最长 | |

**User's choice:** 配置文件筛选
**Notes:** 配置 `[scheduler.check_intervals]` 指定检查的周期列表

---

### 补救策略

| Option | Description | Selected |
|--------|-------------|----------|
| 自动补同步 | 发现缺失后自动触发补同步，使用现有 KlineSyncJob 逻辑 | ✓ |
| 仅记录日志 | 仅记录缺失信息到日志和状态表，不自动同步 | |
| 发送告警 | 记录缺失并发送告警通知（需要告警系统支持） | |

**User's choice:** 自动补同步
**Notes:** 复用现有 `KlineSyncJob` 逻辑执行补救同步，使用相同重试策略

---

### 状态跟踪

| Option | Description | Selected |
|--------|-------------|----------|
| 新建检查日志表 | 新建 completeness_check_log 表记录每次检查详情 | ✓ |
| 复用 sync_state 表 | 复用现有 sync_state 表，增加 check_result 字段 | |

**User's choice:** 新建检查日志表
**Notes:** 
- 与 `sync_state` 表分离，语义清晰
- 字段：检查时间、检查范围、缺失数、修复结果
- 便于后续分析检查历史和缺失率趋势

---

*Discussion logged: 2026-04-12*
*Extended: 2026-04-13 — daily integrity check added*