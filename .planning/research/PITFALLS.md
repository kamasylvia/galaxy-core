# 研究：重构常见陷阱

## 代码级陷阱

1. **删除同步方法时遗漏调用点**
   - `LongPeriodChecker.check()` 被 scheduler 或其他模块调用
   - 需全局检查同步 `check()` 调用点

2. **移除长周期支持时破坏数据库模型**
   - `KlineWeek`, `KlineMonth`, `KlineSeason`, `KlineYear` 模型可能被其他代码引用
   - 移除周期枚举值 `Interval.WEEK/MONTH/SEASON/YEAR` 会影响序列化/反序列化

3. **IntervalBoundaryChecker 依赖**
   - scheduler 和其他模块可能依赖长周期边界检查
   - 需检查 `is_long_interval()` 调用点

4. **README 与实际代码不同步**
   - 过去 README 已严重过时
   - 重构后需建立 README 更新机制

## 流程级陷阱

1. **最小提交原则 vs 批量重构**
   - 用户要求"最小数量提交，每个提交尽量详细"
   - 但重构涉及大量文件变更
   - 策略：按功能模块分批提交，而非一次性大提交

2. **.planning 与代码再次漂移**
   - 当前已存在 drift
   - 重构后需同步更新 .planning
