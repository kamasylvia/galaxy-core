# Phase 08: 重构 K 线表主键 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 08-k-id-symbol-trade-time
**Areas discussed:** 数据迁移策略, TimescaleDB 处理, 索引调整策略, 回滚方案

---

## 数据迁移策略

| Option | Description | Selected |
|--------|-------------|----------|
| 直接重建表 | 先备份、删除旧表、创建新表、恢复数据、重建 hypertable。简单直接，适合可接受短暂停服。 | ✓ |
| 创建新表并迁移 | 创建新表、迁移数据、切换。复杂度高，适合数据量大且不可停服场景。 | |
| 保留 id 列仅移除主键约束 | 不符合当前目标，除非有特殊需求。 | |

**User's choice:** 直接重建表（推荐）
**Notes:** 用户选择简单直接的策略，接受短暂停服。

---

## TimescaleDB 处理

| Option | Description | Selected |
|--------|-------------|----------|
| 迁移后重新创建 hypertable | 删除旧表后重建新表时，重新调用 create_hypertable()。与迁移策略一致。 | ✓ |
| 尝试原地修改主键 | 探索不删除 hypertable 的方式。可能不被 TimescaleDB 支持。 | |

**User's choice:** 迁移后重新创建 hypertable（推荐）
**Notes:** 与直接重建表策略保持一致。

---

## 索引调整策略

| Option | Description | Selected |
|--------|-------------|----------|
| 移除冗余索引 | 组合主键已提供唯一性，TimescaleDB 在 trade_time 上有索引。简化表结构。 | ✓ |
| 保留单独的 symbol 索引 | 可能加速某些查询。如果现有查询模式需要，可保留。 | |

**User's choice:** 移除冗余索引（推荐）
**Notes:** 简化表结构，组合主键已提供必要索引支持。

---

## 回滚方案

| Option | Description | Selected |
|--------|-------------|----------|
| 备份表 + 回滚脚本 | 迁移前创建完整备份表，提供回滚脚本。安全优先。 | ✓ |
| 依赖外部备份 | 假设数据库有定期备份。风险较高。 | |
| 不备份，接受重新同步 | 数据量小或可从 API 重新获取。风险取决于数据获取成本。 | |

**User's choice:** 备份表 + 回滚脚本（推荐）
**Notes:** 安全优先，迁移前备份所有数据。

---

## Claude's Discretion

- 迁移脚本的具体实现方式（SQLAlchemy migration vs 原生 SQL）
- 迁移执行时机（手动触发 vs 调度器集成）
- 备份表的保留策略（保留多久）
- 迁移脚本存放位置
- 单元测试和集成测试的具体覆盖范围

---

## Deferred Ideas

None — 讨论保持在 phase 范围内