# 字段命名规范

## 命名策略

- `symbol` 保留为内部字段名（所有表），API 层 `code`/`MARKET_CODE` 由 adapter 映射到 `symbol`
- 周期命名：AmazingData API 使用 `period`，业务代码使用 `interval`，adapter 做映射

## 字段映射

### K 线数据 (BaseKline / 13 tables)

| 内部字段 | API 字段 | 说明 |
|----------|----------|------|
| `symbol` | `code` / `MARKET_CODE` | 证券代码 (组合主键之一) |
| `trade_time` | `trade_time` | K 线周期开始时间 (组合主键之一) |
| `open` | `open` | 开盘价 |
| `high` | `high` | 最高价 |
| `low` | `low` | 最低价 |
| `close` | `close` | 收盘价 |
| `volume` | `volume` | 成交量 |
| `amount` | `amount` | 成交额 |
| `security_type` | N/A | 内部字段，adapter 推断 |
| `created_at` | N/A | 内部审计字段 |
| `updated_at` | N/A | 内部审计字段 |

### stock_basic (证券基础信息)

| 内部字段 | API 字段 | 说明 |
|----------|----------|------|
| `symbol` | `MARKET_CODE` | 证券代码 |
| `security_name` | `SECURITY_NAME` | 证券简称 |
| `comp_name` | `COMP_NAME` | 公司全称 |
| `pinyin` | `PINYIN` | 拼音简称 |
| `list_date` | `LISTDATE` | 上市日期 |
| `delist_date` | `DELISTDATE` | 退市日期 |
| `security_type` | N/A | 内部字段 |

### stock_status (历史证券信息)

| 内部字段 | API 字段 | 说明 |
|----------|----------|------|
| `symbol` | `MARKET_CODE` | 证券代码 |
| `trade_date` | `TRADE_DATE` | 交易日期 |
| `preclose` | `PRECLOSE` | 前收盘价 |
| `high_limited` | `HIGH_LIMITED` | 涨停价 |
| `low_limited` | `LOW_LIMITED` | 跌停价 |
| `is_st_sec` | `IS_ST_SEC` | 是否 ST |
| `is_susp_sec` | `IS_SUSP_SEC` | 是否停牌 |
| `is_xr_sec` | `IS_XR_SEC` | 是否除权 |
| `is_wd_sec` | `IS_WD_SEC` | 是否除息 |

### backward_factor (后复权因子)

| 内部字段 | API 字段 | 说明 |
|----------|----------|------|
| `symbol` | N/A (column name = stock code) | 证券代码 |
| `trade_date` | index | 交易日期 |
| `factor` | values | 后复权因子值 |

### trading_calendar (交易日历)

| 内部字段 | API 返回 | 说明 |
|----------|----------|------|
| `trade_date` | list[datetime] | 交易日期 |
| `is_trading_day` | N/A | 内部字段 |

## Adapter 层职责

- Provider Adapter 负责将 API 返回的 DataFrame 列名映射到内部字段名
- API 返回大写字段名 (MARKET_CODE, LISTDATE, IS_ST_SEC 等)
- Adapter 防御性取值：先尝试 API 原始名称，再 fallback 到内部名称
- Store Adapter 负责将 domain 值对象映射到数据库字段名
