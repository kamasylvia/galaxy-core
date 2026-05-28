# Galaxy DB Bridge - K线数据同步指令

## 概述

K线数据同步指令 (`kline`) 是 Galaxy DB Bridge 的核心功能之一，用于从 AmazingData API 获取股票、基金等证券的历史K线数据，并将其同步到本地数据库中。该功能支持增量更新，只获取数据库中缺失的数据，提高了效率并减少了不必要的API调用。

## 功能特性

- **多证券类型支持**：支持股票、ETF、指数等多种证券类型
- **多时间周期**：支持从1分钟到年线的各种K线周期
- **增量同步**：只获取数据库中缺失的数据，避免重复下载
- **完整性优先**：先检查数据库覆盖情况，仅在不完整时调用 API
- **结果摘要输出**：CLI 主输出为同步摘要，而不是直接打印完整 K 线明细

## 命令语法

```bash
python -m galaxy_db_bridge kline [OPTIONS] SYMBOLS
```

### 参数说明

#### 必选参数

- `SYMBOLS`：证券代码，支持以下格式：
  - 单个代码：`"600000.SH"`
  - 代码列表：`"[600000.SH, 000001.SZ]"` 或 `"600000.SH,000001.SZ"`
  - SecurityType：`"SH_A"`, `"SZ_ETF"`, `"EXTRA_STOCK_A"` 等
  - 混合列表：`"[600000.SH, SH_ETF]"`

#### 可选参数

- `--interval`：K线周期，默认为 `day`
  - 可选值：`min1`, `min3`, `min5`, `min10`, `min15`, `min30`, `min60`, `min120`, `day`, `week`, `month`, `season`, `year`

- `--start`：开始日期/时间
  - 年线：4 位数字 (YYYY)
  - 季线/月线：6 位数字 (YYYYMM)
  - 日线/周线：8 位数字 (YYYYMMDD)
  - 小时/两小时线：10 位数字 (YYYYMMDDHH)
  - 分钟线：12 位数字 (YYYYMMDDHHMM)
  - 未传入时按证券类型使用 AmazingData 数据起点
    - 股票 / 指数 / 债券 / 场内基金：`20130101`
    - 期权：`20150101`
    - 港股通：`20230101`
    - 中金所期货：`20100401`
    - 大商所期货：`20130601`
    - 郑商所期货：`20110101`
    - 上期所 / 上海国际能源交易中心期货：`20190801`

- `--end`：结束日期/时间
  - 格式同 `--start`
  - 默认为昨天

## 使用示例

### 1. 同步单个股票的日线数据

```bash
python -m galaxy_db_bridge kline "600000.SH"
```

### 2. 同步多个ETF的日线数据

```bash
python -m galaxy_db_bridge kline "[510050.SH, 510300.SH, 512100.SH]"
```

### 3. 同步特定时间段的数据

```bash
python -m galaxy_db_bridge kline --start 20200101 --end 20231231 --interval day "600000.SH"
```

### 4. 同步所有ETF数据

```bash
python -m galaxy_db_bridge kline "SZ_ETF"
```

### 5. 同步不同周期的数据

```bash
python -m galaxy_db_bridge kline --interval week "000001.SZ"
```

## 数据库结构

系统为不同的时间周期创建独立的表，以提高查询性能：

- `kline_min1`：1分钟K线数据
- `kline_min5`：5分钟K线数据
- `kline_day`：日线数据
- `kline_week`：周线数据
- `kline_month`：月线数据
- `kline_season`：季线数据
- `kline_year`：年线数据

每个表包含以下字段：

- `id`：主键ID
- `symbol`：证券代码
- `trade_time`：交易时间
- `open`：开盘价
- `high`：最高价
- `low`：最低价
- `close`：收盘价
- `volume`：成交量
- `amount`：成交额
- `security_type`：证券类型

## 工作原理

1. **参数解析**：解析命令行参数，验证证券代码、时间周期和日期范围的有效性
2. **代码展开与时间归一化**：展开 `SecurityType`，并在缺省 `--start` 时按证券类型推导默认起点
3. **完整性检查**：优先检查数据库是否已完整覆盖目标区间
4. **API调用**：仅针对缺失的数据范围调用 AmazingData API 获取数据
5. **数据同步**：将获取到的数据保存到数据库中
6. **结果输出**：返回同步摘要，说明成功代码数、同步记录数与失败代码

## 错误处理

- **参数错误**：无效的证券代码、日期格式或时间周期
- **数据错误**：证券已退市或在指定日期范围内无数据
- **API错误**：网络问题或API限流
- **已知SDK问题**：AmazingData SDK中的已知bug，系统会提供友好的错误信息

## 性能优化

- 仅在数据库缺失数据时调用API，减少不必要的网络请求
- 按需获取数据，避免下载不需要的时间范围
- 使用数据库索引加速查询操作
- 支持批量处理多个证券代码

## 注意事项

1. **API限制**：注意AmazingData API的调用频率限制
2. **数据完整性**：系统会自动处理数据去重，确保数据库中不会有重复数据
3. **日期格式**：严格按照指定格式输入日期，避免解析错误
4. **证券类型**：支持期权类型；未传入 `--start` 时会按证券类型自动推导默认起点

## 已知问题

- AmazingData SDK中存在K线查询bug，错误信息为 `'NoneType' object cannot be interpreted as an integer`，在 `./AmazingData/query_api\market_data.py`, line 170。系统已实现相应的错误处理机制。
