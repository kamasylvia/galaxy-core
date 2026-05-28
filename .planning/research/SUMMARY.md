# 研究总结：v1.1 重构

## 关键发现

### 缺失数据检测优化
- 当前已有 `_merge_small_gaps`、`_cluster_range_groups`、激进合并等策略
- 专注日线后，可移除 `LongPeriodChecker`，大幅简化 `KlineCompletenessChecker`
- API 调用最小化核心：用完整日期范围批量查询多只证券，依赖 UPSERT 去重

### 文件架构问题
- `database/core/connection.py`（同步）与 `async_connection.py`（异步）并存，同步版应已废弃
- `kline_completeness_checker.py` 同步/异步方法代码重复
- 多处全局单例实例不利于测试
- `BatchSyncResult` 有重复装饰器 bug

### 重构风险
- 移除长周期支持需检查所有 `Interval.WEEK/MONTH/SEASON/YEAR` 引用
- 删除同步 checker 方法需确认无调用点
- README 需与实际代码保持同步

## 建议阶段划分
1. **Phase 1**: 清理废弃代码（同步连接、同步 checker、长周期支持）
2. **Phase 2**: 规范化文件架构（重命名、合并工具函数、改善单例）
3. **Phase 3**: 优化日线同步逻辑（简化完整性检查、优化 API 调用）
4. **Phase 4**: 重写 README 与文档同步
