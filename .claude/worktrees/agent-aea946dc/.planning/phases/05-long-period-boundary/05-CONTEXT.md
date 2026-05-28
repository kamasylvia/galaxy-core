# Phase 5: Long Period Boundary Truncation - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

实现长周期（周/月/季/年）数据同步时的智能日期截取策略，确保只同步完整的、稳定的数据周期，自动处理上市日期和未结束周期的边界情况。

</domain>

<decisions>
## Implementation Decisions

### 不完整上市周期处理
- **D-01:** 只取完整周期，舍弃不完整周期
  - 上市日期落在周期中间时，自动舍弃该周期，从下一个完整周期开始同步
  - 例：20140601 上市，请求 2013-2016 年线 → 同步 2015-2016，舍弃 2014

### 未结束周期处理
- **D-02:** 自动截断到上一个完整周期
  - 例：当前 2026年4月，请求 --end 2026 时，自动截断到 2025-12-31

### 日志与用户反馈
- **D-03:** 输出日志提示舍弃原因
  - 例："2014年上市日期落在年中，已舍弃不完整年，从 2015 年开始同步"
- **D-06:** 部分调整有数据时，同步有效部分并输出跳过理由
  - 例："跳过 2013-2014（上市前或不完整），同步 2015-2016"

### 显式覆盖策略
- **D-04:** 不允许显式覆盖，始终自动调整
  - 即使显式指定 --start 20140601 --end 20141231，也自动调整到完整周期范围
  - 确保数据一致性，避免用户意外获取不完整周期数据

### 完整周期判定
- **D-05:** 第一个完整周期从下一周期首个交易日开始
  - 例：20140601 上市 → 第一个完整年从 20150102（首个交易日）开始
- **D-07:** 统一处理所有长周期（周/月/季/年），都舍弃首尾不完整周期
- **D-08:** 按实际交易日判断，首个交易日即视为完整
  - 例：20140102 上市（1月1日非交易日）→ 2014 年视为完整年

### Claude's Discretion
- 日志输出的具体格式和措辞
- 警告信息的详细程度（是否显示具体日期）

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 长周期边界检查
- `src/galaxy_db_sync/shared_kernel/utils/interval_boundary_checker.py` — 周期边界检查器，判断周期是否结束，计算边界日期
- `src/galaxy_db_sync/shared_kernel/utils/time_parser.py` — 日期解析、精度校验、默认日期推导

### 同步编排
- `src/galaxy_db_sync/application/kline/command.py` — CLI 入口，处理上市日期调整逻辑
- `src/galaxy_db_sync/application/kline/sync_orchestrator.py` — 同步编排，调用完整性检查和批量同步
- `src/galaxy_db_sync/database/services/kline_data_sync.py` — 长周期 end_date 自动调整逻辑（第 180-191 行）

### 测试参考
- `tests/unit/shared_kernel/utils/test_interval_boundary_checker.py` — 周期边界检查器测试

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `IntervalBoundaryChecker` — 已有完整的周期边界判断逻辑
  - `is_interval_complete()` — 判断周期是否已结束
  - `get_last_complete_interval_end()` — 获取最后一个已结束周期的结束日期
  - `get_interval_end_date()` — 获取周期内最后一个交易日

### Established Patterns
- 上市日期调整已在 `command.py` 第 281-290 行实现（调整 start_date）
- 长周期 end_date 自动截断已在 `kline_data_sync.py` 第 180-191 行实现

### Integration Points
- 新逻辑需要在以下位置集成：
  1. `time_parser.py` — 添加 `get_first_complete_period_start()` 函数
  2. `command.py` — 修改上市日期调整逻辑，使用新的完整周期判定
  3. `kline_data_sync.py` — 添加日志输出

### 需要新增的功能
- `IntervalBoundaryChecker.is_period_complete_for_listing()` — 判断上市后首个完整周期
- `IntervalBoundaryChecker.get_first_complete_period_start()` — 获取上市后首个完整周期开始日期
- 日志输出模块 — 输出舍弃原因和调整信息

</code_context>

<specifics>
## Specific Ideas

- "2014年上市，请求 2013-2016 年线 → 跳过 2013（上市前）、2014（不完整），同步 2015-2016"
- 统一处理周/月/季/年，都按"舍弃首尾不完整周期"策略
- 不允许用户通过显式日期覆盖此策略，确保数据一致性

</specifics>

<deferred>
## Deferred Ideas

- 日线/分钟线的"不完整周期"处理 — 本次不涉及，日线按上市日期截断即可
- 用户配置开关（如 --allow-incomplete） — 暂不支持，保持策略一致性

</deferred>

---
*Phase: 05-long-period-boundary*
*Context gathered: 2026-04-09*