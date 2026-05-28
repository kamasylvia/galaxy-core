# 研究：项目文件架构规范化

## 当前结构

```
src/galaxy_db_sync/
├── amazing_data/          # API 客户端
├── application/           # 应用层
│   ├── cli/              # CLI 入口
│   ├── kline/            # K线命令处理
│   ├── calendar/         # 日历命令处理
│   ├── scheduler/        # 调度器
│   └── grpc/             # gRPC 服务
├── database/             # 数据库层
│   ├── core/             # 连接管理
│   ├── models/           # ORM 模型
│   └── services/         # 数据访问层
├── shared_kernel/        # 共享核心
│   ├── enums/            # 枚举
│   ├── exceptions/       # 异常
│   └── utils/            # 工具函数
└── gen/                  # protobuf 生成代码
```

## 识别的问题

1. **双连接管理**: `database/core/connection.py` (同步) + `async_connection.py` (异步) 并存
   - 同步连接在异步路径中应已废弃，但文件仍存在

2. **同步/异步方法并存**: 
   - `kline_completeness_checker.py`: `check()` + `check_async()`，代码重复
   - `LongPeriodChecker`: 同步 `_generate_expected_periods()` + 异步 `_generate_expected_periods_async()`
   - 专注日线后可大幅简化

3. **全局单例依赖**:
   - `kline_service = KlineService()` 全局实例
   - `kline_data_sync_service = KlineDataSyncService()` 全局实例
   - 不利于测试和依赖注入

4. **命名不一致**:
   - `missing_data_tracker.py` vs `completeness_check_log_manager.py`
   - `empty_query.py` 功能名不够清晰

5. **代码重复**:
   - `BatchSyncResult` 有重复 `@dataclass` 装饰器
   - 多处 `_merge_to_ranges` / `_merge_dates_to_ranges` 实现

## 重构方向

1. 移除废弃的同步数据库连接文件
2. 清理同步版本的 checker 方法（保留异步版本）
3. 统一合并区间工具函数
4. 改善模块命名
5. 减少全局单例，提升可测试性
