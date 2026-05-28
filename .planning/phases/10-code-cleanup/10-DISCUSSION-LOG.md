# Phase 10: 代码清理与架构规范化 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-28
**Phase:** 10-代码清理与架构规范化
**Areas discussed:** 同步 db_manager 清理策略, 区间合并函数统一位置, empty_query 重命名范围

---

## 同步 db_manager 清理策略

| Option | Description | Selected |
|--------|-------------|----------|
| 一次性全部移除 | 删除 connection.py，清空 __init__.py 同步导出，所有文件改只导入 async_db_manager。干净彻底，但改动面大。 | ✓ |
| 保留 __init__.py 兼容层 | 保留 database/core/__init__.py 的同步导出供外部使用，仅清理内部 services 和 commands 的同步引用。改动面小，但遗留同步入口。 | |

**User's choice:** 一次性全部移除
**Follow-up:** 进一步确认是否一并清理所有 services 的同步方法（超出 ARCH-02 明确列出的 checker 范围）。用户选择"一并清理所有 services 的同步方法"，仅保留 async 版本。

---

## 区间合并函数统一位置

| Option | Description | Selected |
|--------|-------------|----------|
| shared_kernel/utils/date_range_utils.py | 放到共享工具层，作为通用日期范围合并工具。优点：职责清晰，可被任何模块复用。缺点：database services 需导入 shared_kernel。 | ✓ |
| database/services/_utils.py 或类似内部模块 | 放到 database/services 内部公共模块。优点：与使用方同层，导入简洁。缺点：非通用工具，复用范围受限。 | |

**User's choice:** shared_kernel/utils/date_range_utils.py

---

## empty_query 重命名范围

| Option | Description | Selected |
|--------|-------------|----------|
| 仅改文件名，内部类/变量名保留 | 最小改动。文件名改，但 EmptyQueryResultService、empty_query_service、EmptyQueryResult 保持原样。风险低，但命名不一致。 | |
| 文件名 + 类名 + 变量名全改，模型/表名保留 | service 和变量同步改，但数据库模型 EmptyQueryResult 和表 empty_query_results 不改，避免迁移。 | |
| 全部同步改，包括模型和表名 | 最一致，但涉及数据库迁移脚本（改表名）和大量引用替换。风险最高。 | ✓ |

**User's choice:** 全部同步改，包括模型和表名

---

## Claude's Discretion

None — all decisions made by user.

## Deferred Ideas

None — discussion stayed within phase scope.
