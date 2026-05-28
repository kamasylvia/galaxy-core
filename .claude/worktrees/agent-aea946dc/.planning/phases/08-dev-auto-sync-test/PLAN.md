# Phase 08: 开发环境自动同步测试

**Goal**: 在开发环境中验证自动同步功能正常工作，确认 30 分钟间隔触发、数据完整性检查、日志清理等功能

**Depends on**: Phase 07 (async database layer complete)

**Created**: 2026-04-22

## 测试环境配置

### 配置文件
使用 `GALAXY_CONFIG_ENV=dev` 加载 `settings.dev.toml`：
- `auto_sync_interval_minutes = 30` — 每 30 分钟自动同步
- `enabled_intervals = ["day", "week"]` — 只同步日线和周线（减少测试时间）
- `security_type = "EXTRA_ETF"` — 只测试 ETF 证券

### 启动方式
```bash
GALAXY_CONFIG_ENV=dev python -m galaxy_db_sync.scheduler
```

## 测试场景

### 1. 首次启动测试
- 启动 scheduler，确认首次同步立即触发
- 观察日志确认同步流程：
  - 完整性检查
  - 缺失范围识别
  - API 调用（预期 ~3 次）
  - 数据保存
  - 完整性验证

### 2. 间隔同步测试
- 等待 30 分钟，确认第二次同步触发
- 验证：
  - 日志显示 "Triggering interval-based sync"
  - 完整性检查识别已有的数据
  - 只同步新缺失的范围

### 3. 日志清理测试
- 运行多次同步，产生多个日志目录
- 等待超过 backup_count 天（或手动修改配置测试）
- 确认旧日志目录被清理

### 4. 数据完整性验证
- 同步完成后，检查数据库：
  - 数据条数符合预期
  - 无明显缺失日期
  - 周线数据按 ISO 周存储

## 验收标准

| 指标 | 预期值 | 验证方法 |
|-----|-------|---------|
| API 调用次数 | ≤ 5 次/同步 | 查看日志 |
| 同步触发间隔 | 30 分钟 ± 1 分钟 | 查看日志时间戳 |
| 日志清理 | 保留 5 天 | 查看 logs/ 目录 |
| 数据完整性 | > 95% | 完整性检查输出 |

## 测试执行步骤

### Step 1: 环境准备
```bash
# 确认数据库连接正常
source .venv/bin/activate
python -c "from galaxy_db_sync.database.core.connection import db_manager; db_manager.initialize(); print('DB OK')"

# 确认配置加载正确
GALAXY_CONFIG_ENV=dev python -c "
from galaxy_db_sync.shared_kernel.utils.config_loader import get_section
config = get_section('scheduler')
print(f'auto_sync_interval: {config.get(\"auto_sync_interval_minutes\")} min')
"
```

### Step 2: 启动 Scheduler
```bash
GALAXY_CONFIG_ENV=dev python -m galaxy_db_sync.scheduler
```

### Step 3: 监控日志
```bash
# 查看最新日志
tail -f logs/$(date +%Y%m%d)/*.log
```

### Step 4: 数据验证
```bash
# 同步完成后检查数据
GALAXY_CONFIG_ENV=dev python -c "
import asyncio
from galaxy_db_sync.database.core.async_connection import async_db_manager
from galaxy_db_sync.database.services.kline_completeness_checker import kline_completeness_checker
from datetime import date

async def check():
    async_db_manager.initialize()
    result = await kline_completeness_checker.check_async(
        '511930.SH', 'week', date(2024, 1, 1), date(2026, 4, 10)
    )
    print(f'完整性: {result.coverage_ratio:.2%}')
    print(f'缺失: {result.missing_count}/{result.total_count}')

asyncio.run(check())
"
```

## 风险与应对

| 风险 | 影响 | 应对措施 |
|-----|-----|---------|
| API 限流 | 同步失败 | 增加间隔时间或减少证券数量 |
| 数据库连接断开 | 无法保存 | 确认连接池配置，添加重试逻辑 |
| 日志目录权限问题 | 无法写入 | 确认 logs/ 目录权限 |

## 时间计划

- Day 1: 环境准备 + 首次同步测试
- Day 2: 间隔同步测试 + 日志清理测试
- Day 3: 数据完整性验证 + 问题修复

---

**Status**: Planning
**Estimated duration**: 3 days