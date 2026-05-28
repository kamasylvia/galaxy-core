---
status: verifying
trigger: "kline-api-skip-when-db-has-data"
created: "2026-04-16T00:00:00Z"
updated: "2026-04-16T00:01:00Z"
---

## Current Focus

hypothesis: 月线/季线/周线完整性检查比较逻辑错误 - 用第一个交易日比较而非周期标识
test: 已修复 - 改用月份/季度/ISO周来比较
expecting: 用户验证 - 确认月线查询在数据完整时不再重复调用 API
next_action: 等待用户验证修复效果

## Symptoms

expected: 直接返回数据库数据（检查数据库已有数据后跳过同步）
actual: 调用了 API 并同步数据（即使数据库有数据仍然调用 API）
errors: 无错误，只是行为不对
reproduction: CLI 手动查询命令（月线: start=2025, end=202603）
started: 刚发现，不清楚是否曾经正常工作过

## Eliminated

(暂无)

## Evidence

- timestamp: 2026-04-16T00:00:01Z
  checked: command.py 第 176-178 行 get_valid_symbols_from_input
  found: valid_symbols 来自 get_valid_symbols_from_input(input_symbol_list, full_start_for_codes, full_end_for_codes)
  implication: 需要确认该函数是否返回与输入相同的 symbols

- timestamp: 2026-04-16T00:00:02Z
  checked: command.py 第 215-239 行完整性检查循环
  found: 对 valid_symbols 中每个 symbol 调用 kline_completeness_checker.check()
  implication: 完整性检查覆盖 valid_symbols

- timestamp: 2026-04-16T00:00:03Z
  checked: command.py 第 274-278 行跳过逻辑
  found: all_data_complete = incomplete_count == 0 and empty_count == 0; 若 True 则 return 0
  implication: 跳过逻辑存在，但 empty_count 或 incomplete_count 非零时会触发同步

- timestamp: 2026-04-16T00:00:15Z
  checked: 完整性检查同步 vs 异步版本对比
  found: 同步版本查询 trade_time <= datetime.combine(end_date, datetime.max.time()) = 23:59:59.999999
         异步版本查询 trade_time <= parse_date_for_interval(..., is_end=True) = 00:00:00
  implication: 根本原因确认！异步版本查询无法捕获带时间组件的 trade_time

- timestamp: 2026-04-16T00:00:18Z
  checked: 修复后的 parse_date_for_interval 函数行为
  found: is_end=True 时返回 datetime.combine(base_dt.date(), datetime.max.time()) = 23:59:59.999999
         is_end=False 时返回 datetime.strptime(date_str[:8], "%Y%m%d") = 00:00:00
  implication: 修复后与同步版本行为一致

- timestamp: 2026-04-16T00:00:19Z
  checked: 带时间组件的 trade_time 查询匹配测试
  found: trade_time=2025-01-31 09:30:00 <= end_dt=2025-01-31 23:59:59.999999 = True
  implication: 修复后数据库查询能正确匹配带时间组件的记录

- timestamp: 2026-04-16T00:00:30Z
  checked: 最近3次月线查询日志 (230526.log, 221548.log, 110457.log)
  found: 每次都是 "完整 1319, 部分缺失 145, 无数据 6"，每次都调用 22 次 API 保存 136 条记录
  implication: 日线修复后月线仍有问题 - 完整性检查仍然认为数据缺失

- timestamp: 2026-04-16T00:00:45Z
  checked: kline_completeness_checker.py 第 196-206 行比较逻辑
  found: 年线用年份比较（正确），但月线/季线/周线用 first_trading_day 比较（错误）
         数据库存储的月线 trade_time 可能是月末日期，而 expected_first_trading_days 是第一个交易日
  implication: 根本原因！月线数据永远无法匹配 first_trading_day

## Resolution

root_cause_1: parse_date_for_interval 函数对日线/短周期在 is_end=True 时返回 00:00:00，导致异步完整性检查无法匹配带时间组件的记录
fix_1: 修改 parse_date_for_interval 函数，对短周期当 is_end=True 时返回 datetime.max.time()
files_changed_1: [src/galaxy_db_sync/database/services/kline.py]

root_cause_2: 月线/季线/周线完整性检查用 expected_first_trading_days 和 existing_dates 比较具体日期，但数据库存储的 trade_time 可能是月末或其他日期而非第一个交易日，导致永远匹配不上
fix_2: 修改 kline_completeness_checker.py 的 check 和 check_async 方法：
        - 月线：改用 (year, month) 比较
        - 季线：改用 (year, quarter) 比较
        - 周线：改用 ISO week (year, week_number) 比较
files_changed_2: [src/galaxy_db_sync/database/services/kline_completeness_checker.py]

verification: 待用户验证 - 运行月线查询命令确认不再重复调用 API