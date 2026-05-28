# External Integrations

**Analysis Date:** 2026-04-01
**API Documentation Source:** `docs/AmazingData/Markdown/AmazingData开发手册/`

## APIs & External Services

**Galaxy Securities AmazingData API (中国银河证券星耀数智服务平台):**

SDK: `AmazingData` package (local wheel: `AmazingData-1.0.26-cp313-none-any.whl`)
Client: `src/galaxy_db_sync/amazing_data/api/client.py`

### API 数据分类与实现状态

| 数据分类 | 子类型 | 实现状态 | API 接口文档 |
|---------|-------|---------|-------------|
| **行情数据** | | | `2.2 数据详情.md` |
| | Level-1快照 (股票/指数/债券/ETF) | ❌ 待开发 | `3.5.3 实时行情数据` |
| | Level-1快照 (期权) | ❌ 待开发 | `3.5.3 实时行情数据` |
| | Level-1快照 (期货) | ❌ 待开发 | `3.5.3 实时行情数据` |
| | K线数据 (12种周期) | ✅ 已实现 | 当前实现 |
| | 港股通行情快照 | ❌ 待开发 | `3.5.3.7 港股通实时快照` |
| **历史行情数据** | | | `3.5.4 历史行情数据` |
| | 历史快照 | ❌ 待开发 | `3.5.4.1 历史快照` |
| **基础数据** | | | `3.5.2 基础数据` |
| | 每日最新证券信息 | ❌ 待开发 | `3.5.2.1 每日最新证券信息` |
| | 每日最新代码表（沪深北） | ❌ 待开发 | `3.5.2.2` |
| | 每日最新代码表（期货） | ❌ 待开发 | `3.5.2.3` |
| | 每日最新代码表（期权） | ❌ 待开发 | `3.5.2.4` |
| | 复权因子（后复权） | ❌ 待开发 | `3.5.2.5` |
| | 复权因子（单次） | ❌ 待开发 | `3.5.2.6` |
| | 历史代码表 | ❌ 待开发 | `3.5.2.7` |
| | 交易日历 | ✅ 已实现 | `3.5.2.8 交易日历` |
| | 证券基础信息 | ❌ 待开发 | `3.5.2.9` |
| | 历史证券信息 | ❌ 待开发 | `3.5.2.10` |
| | 北交所新旧代码对照 | ❌ 待开发 | `3.5.2.11` |
| **财务数据** | | | `3.5.5 财务数据` |
| | 资产负债表 | ❌ 待开发 | `3.5.5.1` |
| | 现金流量表 | ❌ 待开发 | `3.5.5.2` |
| | 利润表 | ❌ 待开发 | `3.5.5.3` |
| | 业绩快报 | ❌ 待开发 | `3.5.5.4` |
| | 业绩预告 | ❌ 待开发 | `3.5.5.5` |
| **股东股本数据** | | | `3.5.6 股东股本数据` |
| | 十大股东 | ❌ 待开发 | `3.5.6.1` |
| | 股东户数 | ❌ 待开发 | `3.5.6.2` |
| | 股本结构 | ❌ 待开发 | `3.5.6.3` |
| | 股权冻结质押 | ❌ 待开发 | `3.5.6.4` |
| | 限售股解禁 | ❌ 待开发 | `3.5.6.5` |
| **股东权益数据** | | | `3.5.7 股东权益数据` |
| | 分红数据 | ❌ 待开发 | `3.5.7.1` |
| | 配股数据 | ❌ 待开发 | `3.5.7.2` |
| **融资融券数据** | | | `3.5.8 融资融券数据` |
| | 融资融券成交汇总 | ❌ 待开发 | `3.5.8.1` |
| | 融资融券交易明细 | ❌ 待开发 | `3.5.8.2` |
| **交易异动数据** | | | `3.5.9 交易异动数据` |
| | 龙虎榜 | ❌ 待开发 | `3.5.9.1` |
| | 大宗交易 | ❌ 待开发 | `3.5.9.2` |
| **期权数据** | | | `3.5.10 期权数据` |
| | 期权基本资料 | ❌ 待开发 | `3.5.10.1` |
| | 期权标准合约属性 | ❌ 待开发 | `3.5.10.2` |
| | 期权月合约属性变动 | ❌ 待开发 | `3.5.10.3` |
| **ETF数据** | | | `3.5.11 ETF数据` |
| | ETF每日申赎数据 | ❌ 待开发 | `3.5.11.1` |
| | ETF基金份额 | ❌ 待开发 | `3.5.11.2` |
| | ETF每日收盘iopv | ❌ 待开发 | `3.5.11.3` |
| **交易所指数数据** | | | `3.5.12 交易所指数数据` |
| | 指数成分股 | ❌ 待开发 | `3.5.12.1` |
| | 指数成分股日权重 | ❌ 待开发 | `3.5.12.2` |
| **行业指数数据** | | | `3.5.13 行业指数数据` |
| | 行业指数基本信息 | ❌ 待开发 | `3.5.13.1` |
| | 行业指数成分股 | ❌ 待开发 | `3.5.13.2` |
| **可转债数据** | | | `3.5.14 可转债数据` |
| | (待查阅文档) | ❌ 待开发 | `3.5.14` |
| **国债收益率数据** | | | `3.5.15 国债收益率数据` |
| | (待查阅文档) | ❌ 待开发 | `3.5.15` |

### 行情数据覆盖范围

| 品种 | 数据类型 | 数据起点 | 交易所 | 实时订阅 |
|-----|---------|---------|--------|---------|
| 股票 | Level-1快照、K线 | 2013年至今 | 上交所、深交所、北交所 | ✅ |
| 指数 | Level-1快照、K线 | 2013年至今 | 上交所、深交所、北交所 | ✅ |
| 债券 | Level-1快照、K线 | 2013年至今 | 上交所、深交所 | ✅ |
| 场内基金 | Level-1快照、K线 | 2013年至今 | 上交所、深交所 | ✅ |
| 期权 | Level-1快照、K线 | 2015年至今 | 上交所ETF期权、深交所ETF期权 | ✅ |
| 港股通 | 港股通快照 | 2023年至今 | 上交所、深交所 | ✅ |
| 期货 | Level-1快照、K线 | 2010/2013/2011/2019 | 中金所、大商所、郑商所、上期所 | ✅ |

### Auth Configuration

**AmazingData Auth:**
- Username/password authentication
- Login via `ad.login()` SDK function
- Session-based authentication (maintained by SDK)
- Lazy client initialization pattern: `src/galaxy_db_sync/amazing_data/api/lazy_client.py`
- Environment variables:
  - `GALAXY_USERNAME` - API username
  - `GALAXY_PASSWORD` - API password
  - `GALAXY_HOST` - Server IP address
  - `GALAXY_PORT` - Server port number

**Infisical Secrets Management:**
- Optional secrets management via Infisical HTTP API
- Implementation: `src/galaxy_db_sync/shared_kernel/utils/infisical_config.py`
- Auth: Universal Auth (Client ID + Client Secret)
  - `INFISICAL_CLIENT_ID` - Client identifier
  - `INFISICAL_CLIENT_SECRET` - Client secret
  - `INFISICAL_PROJECT_ID` - Project/workspace ID
  - `INFISICAL_URL` - Server URL (default: `https://app.infisical.com`)
- Environment support: `dev`, `staging`, `production`

## Data Storage

**Databases:**
- PostgreSQL/TimescaleDB
  - Connection via SQLAlchemy
  - Connection string built from env vars: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
  - Client: `src/galaxy_db_sync/database/core/connection.py`
  - Models: SQLAlchemy ORM in `src/galaxy_db_sync/database/models/`
  - Time-series optimization via TimescaleDB hypertables

**File Storage:**
- Local filesystem for:
  - AmazingData cache: `./cache/` (configurable via `amazing_data.local_path`)
  - Log files: `./logs/{date}/{time}.log`
  - Private SDK wheels: `wheels/` directory

**Caching:**
- Local file cache for AmazingData historical code lists
- Configurable path via `GALAXY_CACHE_PATH` env var or `amazing_data.local_path` config

## Authentication & Identity

**AmazingData Auth:**
- Username/password authentication
- Login via `ad.login()` SDK function
- Session-based authentication (maintained by SDK)
- Lazy client initialization pattern: `src/galaxy_db_sync/amazing_data/api/lazy_client.py`

**Infisical Auth:**
- Universal Auth (OAuth-like flow)
- Access token cached in `InfisicalConfig._access_token`
- Token refresh handled by class singleton

**Database Auth:**
- PostgreSQL credentials from environment
- Connection pool with pre-ping validation

## Monitoring & Observability

**Error Tracking:**
- None detected - uses standard Python logging

**Logs:**
- File-based logging with configurable rotation
- Log levels: INFO (default), DEBUG (optional)
- Pattern: `./logs/{date}/{time}.log` when `enable_separate_log_files=true`
- Rotation: 50MB max size, 5 backup files (traditional mode)
- Implementation: `src/galaxy_db_sync/application/cli/commands.py` (`setup_logging()`)

## CI/CD & Deployment

**Hosting:**
- Not specified - appears to be local/development deployment

**CI Pipeline:**
- None detected (no `.github/` directory)
- No CI configuration files found

## Environment Configuration

**Required env vars (from `.env.example`):**

AmazingData API:
- `GALAXY_USERNAME` - Required
- `GALAXY_PASSWORD` - Required
- `GALAXY_HOST` - Required
- `GALAXY_PORT` - Required

PostgreSQL:
- `DB_HOST` - Required (default: localhost)
- `DB_PORT` - Required (default: 5432)
- `DB_NAME` - Required (default: quant_db)
- `DB_USER` - Required (default: quant_user)
- `DB_PASSWORD` - Required

Project:
- `PROJECT_ROOT_PATH` - Project root directory path

Optional:
- `GALAXY_CACHE_PATH` - Local cache path
- `LOG_FILE_PATH` - Log file location
- `DEBUG` - Enable debug output
- `DB_ECHO` - Print SQL statements

Infisical (optional):
- `INFISICAL_CLIENT_ID`
- `INFISICAL_CLIENT_SECRET`
- `INFISICAL_PROJECT_ID`
- `INFISICAL_URL`

**Secrets location:**
- `.env` file (local, not committed to git)
- Infisical cloud service (optional alternative)
- `.env.infisical` template provided

## Webhooks & Callbacks

**Incoming:**
- None - This is a data ingestion tool, not a service

**Outgoing:**
- None - Data flows from AmazingData to PostgreSQL only

## Data Flow Architecture

**Primary Flow:**
```
AmazingData API (Galaxy Securities)
        |
        v
[ AmazingDataClient ] --> [ KlineDataSyncService ]
        |                           |
        v                           v
[ Pandas DataFrame ] --> [ SQLAlchemy ORM ]
                                    |
                                    v
                        PostgreSQL/TimescaleDB
```

**Configuration Flow:**
```
.env + config/settings.toml --> ConfigLoader --> Application Services
        |
        v (optional)
Infisical API --> secrets injection --> Environment
```

---

*Integration audit: 2026-04-01*