# Phase 08: 重构 K 线表主键 - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

将所有 K 线表（13 个表，从 kline_min1 到 kline_year）的主键从自增 `id` 改为 `(symbol, trade_time)` 组合主键。

当前状态：
- `BaseKline` 定义 `id: Mapped[int]` 作为自增主键
- 所有 13 个 K 线表子类继承 `BaseKline`
- 已存在 `(symbol, trade_time)` UniqueConstraint 约束
- TimescaleDB hypertables 使用 `trade_time` 作为时间列
- 代码中仅一处引用 `model.id`（`kline.py:295` 用于计数）

不在本 phase 内：
- TradingCalendar 表的 id 主键（独立表，不受影响）
- 其他数据库表的修改
- 数据内容的变更

</domain>

<decisions>
## Implementation Decisions

### 数据迁移策略
- **D-01:** 直接重建表策略
  - 先备份现有数据到临时表
  - 删除旧表（包括 hypertable）
  - 创建新表（组合主键，无 id 列）
  - 从备份恢复数据
  - 重新创建 hypertable
  - 简单直接，适合可接受短暂停服的场景

### TimescaleDB 处理
- **D-02:** 迁移后重新创建 hypertable
  - 删除旧表时 hypertable 自动删除
  - 创建新表后调用 `create_hypertable()`
  - 使用相同的 `trade_time` 时间列
  - 与 D-01 迁移策略一致

### 索引调整策略
- **D-03:** 移除冗余索引
  - 组合主键 `(symbol, trade_time)` 自动创建索引
  - 移除单独的 `symbol` 和 `trade_time` 索引
  - TimescaleDB 在 `trade_time` 上有内置索引
  - 简化表结构，减少索引维护开销

### 回滚方案
- **D-04:** 备份表 + 回滚脚本
  - 迁移前创建完整数据备份表
  - 提供回滚脚本：从备份恢复原始表结构
  - 备份表命名：`kline_{interval}_backup_{timestamp}`
  - 迁移成功后可选择保留或删除备份表

### Claude's Discretion
- 迁移脚本的具体实现方式（SQLAlchemy migration vs 原生 SQL）
- 迁移执行时机（手动触发 vs 调度器集成）
- 备份表的保留策略（保留多久）
- 迁移脚本存放位置
- 单元测试和集成测试的具体覆盖范围

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 数据模型
- `src/galaxy_db_sync/database/models/kline.py` — K 线表模型定义，需修改 BaseKline 和所有子类
- `src/galaxy_db_sync/shared_kernel/enums/interval.py` — Interval 枚举，定义所有支持的周期

### TimescaleDB
- `src/galaxy_db_sync/database/core/timescale.py` — hypertable 创建函数，迁移后需调用

### 数据服务
- `src/galaxy_db_sync/database/services/kline.py` — K 线服务，第 295 行引用 `model.id` 需修改

### 项目级指令
- `CLAUDE.md` — 项目架构、命名约定、测试命令与开发约束
- `.planning/PROJECT.md` — 项目核心原则与约束

### 前序 Phase
- `.planning/phases/07-full-async-database-layer/07-CONTEXT.md` — 异步数据库层完成，迁移脚本需异步兼容

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `create_hypertable()` 函数 — 可复用创建新 hypertable
- `INTERVAL_MODEL_MAP` 字典 — 所有 13 个 K 线表模型的映射
- 异步数据库管理器 `async_db_manager` — 迁移脚本可使用

### Established Patterns
- 所有数据库操作已异步化（Phase 7）
- CLI 入口使用 `asyncio.run()` 驱动异步命令
- 周期命名统一使用 `interval`
- TimescaleDB hypertable 创建模式已建立

### Integration Points
- `BaseKline` 抽象类 — 主键定义的源头
- 13 个 K 线表子类 — 继承 BaseKline
- `kline.py:295` — 唯一引用 `model.id` 的代码，需改为 `select(func.count())`

</code_context>

<specifics>
## Specific Ideas

- 备份表命名格式：`kline_{interval}_backup_{YYYYMMDD_HHMMSS}`
- 迁移脚本需支持异步执行（使用 `async_db_manager`）
- 迁移顺序：按表大小从小到大（min 表先迁移，year 表最后）
- 迁移完成后验证：检查数据条数一致、主键约束生效、hypertable 创建成功

</specifics>

<deferred>
## Deferred Ideas

None — 讨论保持在 phase 范围内

</deferred>

---

*Phase: 08-k-id-symbol-trade-time*
*Context gathered: 2026-04-23*