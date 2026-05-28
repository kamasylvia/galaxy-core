# 研究：K线数据同步缺失检测与API调用优化

## 当前实现分析

### 缺失数据检测流程
1. `KlineCompletenessChecker.check()` → 对比数据库数据与期望交易日历
2. `KlineDataSyncService._group_by_missing_ranges()` → 合并缺失区间
3. `empty_query_service` → 跳过已确认空数据的区间
4. `amazing_data_client.get_kline()` → API 查询

### 已有优化策略
- `_merge_small_gaps`: 间隔<5天的缺失区间合并
- `_cluster_range_groups`: 跨证券合并重叠区间（gap<30天，max_range<180天）
- 激进合并：缺失区间>50时合并为单个大区间
- 空查询缓存：避免重复查询已知空数据区间

### 专注日线后的简化机会
- 移除 LongPeriodChecker（周线/月线/季线/年线检测逻辑）
- ShortPeriodChecker 简化为纯交易日对比
- 移除 interval_boundary_checker 的长周期边界调整

## 最小化API调用策略

### 当前瓶颈
- 单证券逐个区间调用 API
- 即使合并后，不同证券的缺失区间仍需分别查询

### 优化方向
1. **全量优先**: 当缺失比例高时（如>30%），直接用完整日期范围查询而非精确缺失区间
2. **证券批量**: 利用 `amazing_data_client.get_kline(code_list=[...])` 一次查询多只证券
3. **上市日感知**: 新上市证券上市前日期自动跳过，无需API验证
