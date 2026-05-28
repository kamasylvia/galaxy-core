# Phase 4: Async CLI Entry Point - Research

**Researched:** 2026-04-06
**Domain:** CLI 异步入口与端到端收口
**Confidence:** HIGH

## Summary

CLI 边界目前仍完全同步：`src/galaxy_db_sync/application/cli/commands.py` 直接调用 `handle_kline_command(args)`，而 `src/galaxy_db_sync/application/kline/command.py` 也仍以同步流程驱动数据库初始化、完整性检查和同步编排。Phase 4 的任务不是简单包一层 `asyncio.run()`，而是把前 3 个 phase 的 async 能力安全串起来，同时保持 CLI 参数、输出摘要与退出码兼容。

## Current State

- `commands.py:137` 当前直接 `return handle_kline_command(args)`
- `command.py` 当前流程仍显式初始化同步 `db_manager` 并调用同步 orchestrator
- CLI 仍承担日期推导、symbol 校验、完整性检查、摘要输出等职责

## Architecture Findings

### Pattern 1: Thin sync shell around async core
CLI 入口可以保留同步的 argparse 主函数，但应在分发命令时使用 `asyncio.run(handle_kline_command_async(args))` 驱动 async 核心。

### Pattern 2: Preserve user-visible behavior
async 化不应改变：
- 参数解析方式
- 成功/失败返回码
- 日志和摘要的主要结构
- 现有调用入口名称

### Pattern 3: End-to-end phase
只有当前 3 个 phase 能串起来之后，CLI phase 才有意义。因此它天然依赖前 3 phase 完成。

## Test Requirements

- `kline` 命令入口的异步调用路径
- 退出码与日志摘要的兼容性验证
- 端到端从 CLI → command → orchestrator → database/client 的主链路验证
- 若 `calendar` 命令不在本次 async scope，需显式保持原样并避免误改

## Key Decisions

- **Decision 1:** `argparse` 入口保持同步，异步能力从命令处理函数边界开始
  - **Rationale:** 这样改动最小，也最符合 Python CLI 常规模式
- **Decision 2:** 仅切换 async 改造范围内的命令链路
  - **Rationale:** 避免把不相关命令一起卷入改造
- **Decision 3:** 兼容性验证是本 phase 的第一验收标准
  - **Rationale:** 用户当前使用方式不能因为 async 改造而变化

## Failure Modes

- 在已有事件循环环境中误用 `asyncio.run()` 导致嵌套问题
- CLI 层仍残留同步 orchestrator / 同步 DB 调用，导致链路半异步
- 输出摘要或错误码变化，破坏现有使用脚本
- 顺手误改 `calendar` 等不在 scope 内的命令

## Patterns to Follow

- 在 `commands.py` 保持 `main()` 结构稳定，只替换命令调度边界
- 为 `handle_kline_command_async()` 提供薄兼容层，必要时保留同步 wrapper
- 端到端测试优先验证用户可见行为，而不是只测内部 await 调用

## Files of Interest

- `src/galaxy_db_sync/application/cli/commands.py`
- `src/galaxy_db_sync/application/kline/command.py`
- `src/galaxy_db_sync/application/kline/sync_orchestrator.py`
- `src/galaxy_db_sync/database/core/connection.py`

## Recommended Planning Focus

1. 新增 async command handler
2. CLI dispatch 改为 `asyncio.run(...)`
3. 保持日志/退出码兼容
4. 做端到端回归验证
