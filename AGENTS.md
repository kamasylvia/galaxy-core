# AGENTS.md

> **本文档是项目约定主源(架构/DI/命名/命令/测试约定)。**

---

## Project Overview

galaxy-core is a data ingestion and storage core: it fetches market data from China Galaxy Securities' AmazingData API, persists it to PostgreSQL/TimescaleDB, and serves it via a DB-backed OpenBB provider. K-line (candlestick) sync covers Chinese A-shares, ETFs, and other securities. Frontend lives in galaxy-web (Finanalyzer fork).

> **架构目标(2026-09-28 重构立项,2026-10-21 前端切 Finanalyzer)**:OpenBB Platform 后端(本项目提供 DB-backed provider)+ Finanalyzer 前端(galaxy-web fork openbb-hka)。
> 数据源仍是 AmazingData(采集管道不变)。

**Current Version Focus:** `EXTRA_ETF` (沪深两市 ETF）。当前版本数据库已包含 ETF 的 K-line、stock_basic、backward_factor 数据。A 股（`EXTRA_STOCK_A`）的 stock_basic、stock_status、backward_factor 也已同步，为未来版本预留。stock_status 仅支持 A 股，ETF 无此数据。

## Proto / gRPC Integration

This repository consumes protobuf schemas from `galaxy-web/proto/`.
Generated Python code goes to `src/galaxy_core/gen/` (gitignored).

To regenerate stubs after proto changes:
```bash
cd ../galaxy-web && just gen-python
```

The gRPC server entrypoint is `src/galaxy_core/application/grpc/server.py`.
Service implementations live in `src/galaxy_core/application/grpc/`.

## Development Commands

### Setup
```bash
# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate  # Linux/macOS

# Install dependencies (including private AmazingData SDK)
uv pip install wheels/*.whl
uv pip install -e ".[dev,format]"
```

### Testing
```bash
# Run all tests
pytest tests/

# Run unit tests only
pytest tests/unit/

# Run integration tests only
pytest tests/integration/

# Run specific test file
pytest tests/unit/kline/test_kline_command.py

# Run with verbose output
pytest tests/ -v
```

### Code Quality
```bash
ruff check .      # Lint check
ruff format .     # Code formatting
mypy src/         # Type checking
```

### CLI Usage
```bash
# Initialize database tables (run Alembic migrations + create hypertables)
galaxy-core init-db

# Recreate all tables (dangerous: will drop existing data)
galaxy-core init-db --recreate

# Fetch K-line data
galaxy-core kline 600000.SH --interval day --start 20230101 --end 20231231

# Fetch with SecurityType (batch)
galaxy-core kline SH_A --interval day --start 20230101 --end 20231231

# Fetch calendar data
galaxy-core calendar --year 2024
```

## Architecture

### Layer Structure
```
src/galaxy_core/
├── domain/                        # 纯业务逻辑层（无外部依赖）
│   ├── value_objects.py           # Interval, SecurityType, KlineBar 等值对象
│   ├── completeness/              # 完整性检查纯函数
│   ├── date_range/                # 日期范围解析和合并
│   ├── interval/                  # 周期边界计算
│   ├── ports/                     # Protocol-based 端口接口
│   │   ├── kline_provider.py      # KlineProviderPort
│   │   ├── kline_store.py         # KlineStorePort
│   │   ├── calendar_provider.py   # CalendarProviderPort
│   │   ├── calendar_store.py      # CalendarStorePort
│   │   ├── empty_cache_store.py   # EmptyCacheStorePort
│   │   └── reference_provider.py  # ReferenceProviderPort
│   └── symbol/                    # 标的验证和类型推断
├── services/                      # 应用服务层（通过端口接口注入依赖）
│   ├── kline_data_service.py      # KlineDataService
│   ├── calendar_data_service.py   # CalendarDataService
│   └── reference_data_service.py  # ReferenceDataService
├── di/                            # 依赖注入容器
│   └── container.py               # injector AppModule + create_injector()
├── amazing_data/
│   └── api/
│       ├── client.py              # AmazingData SDK 客户端（单例）
│       ├── lazy_client.py         # 延迟加载代理
│       └── adapters/              # Provider 适配器（SDK → async）
│           ├── kline_provider_adapter.py
│           ├── calendar_provider_adapter.py
│           └── reference_provider_adapter.py
├── application/
│   ├── cli/commands.py            # CLI 命令（通过 DI 获取服务）
│   ├── scheduler/                 # 自动同步调度器
│   └── grpc/server.py             # gRPC 服务端
├── database/
│   ├── core/                      # 连接管理
│   │   ├── async_connection.py    # AsyncDatabaseManager（单例）
│   │   ├── connection.py          # DatabaseManager（同步，遗留）
│   │   └── timescale.py           # TimescaleDB hypertable 设置
│   ├── models/                    # SQLAlchemy ORM 模型
│   └── services/                  # 数据访问层
│       ├── kline.py               # K-line CRUD
│       ├── missing_data_tracker.py # 缺失数据跟踪与同步
│       ├── empty_query_cache.py   # 空查询缓存（独立于 empty_query.py）
│       ├── completeness_check_log_manager.py # 完整性检查日志
│       ├── kline_completeness_checker.py
│       ├── trading_calendar.py
│       ├── empty_query.py         # 空查询缓存
│       └── adapters/              # Store 适配器（DB → async）
│           ├── kline_store_adapter.py
│           ├── calendar_store_adapter.py
│           └── empty_cache_store_adapter.py
└── shared_kernel/
    ├── enums/                     # 兼容性重导出（canonical 在 domain/value_objects.py）
    ├── exceptions/                # 异常层次结构
    └── utils/                     # 工具函数
        ├── config_loader/         # TOML + env var 配置
        ├── time_parser.py
        └── ...
```

### Key Design Patterns

1. **依赖注入 (DI)**: `injector` 框架管理 service/adapter 生命周期，`AppModule` 统一绑定。基础设施类（`AsyncDatabaseManager`、`AmazingDataClient`）保留旧 `__new__` 单例但由 DI 统一注入，应用层不直接使用全局单例
2. **Protocol-based Ports**: Python `Protocol` 定义接口契约（6 个端口），解耦 domain 与 infrastructure
3. **Adapter 模式**: Provider adapters（SDK → async）+ Store adapters（DB → async），实现端口接口
4. **Lazy Initialization**: `LazyAmazingDataClient` 延迟 SDK 登录直到首次使用
5. **Table-per-Interval**: 每个 K-line 周期独立 hypertable（`kline_min1`, `kline_day` 等）
6. **Completeness-First Sync**: 先检查数据库再获取，仅同步缺失范围
7. **Empty Result Caching**: 避免重复 API 调用
8. **Async 边界集中化**: `asyncio.to_thread()` 仅在 adapter 层使用，业务代码全异步
9. **全异步数据库层**: 所有数据库交互使用 `AsyncSession`

### Data Flow
```
CLI / Scheduler / gRPC
        ↓
┌─ Application Layer ─────────────────────────────┐
│  Services (KlineDataService, CalendarDataService) │
│       ↓ uses                    ↓ uses           │
│  KlineProviderPort        KlineStorePort          │
└───────┬──────────────────────────┬───────────────┘
        ↓                          ↓
┌─ Adapter Layer ──────────────────────────────────┐
│  KlineProviderAdapter       KlineStoreAdapter     │
│  (asyncio.to_thread)        (AsyncSession)        │
└───────┬──────────────────────────┬───────────────┘
        ↓                          ↓
  AmazingData API              PostgreSQL/TimescaleDB
```

### K-line Query Workflow

K线查询的完整流程：

1. **用户发起查询或自动查询触发** — CLI 命令或 Scheduler 定时任务
2. **从数据库获取K线数据** — `KlineDataService` 通过 `KlineStorePort` 查询
3. **数据连续性检查** — 因为数据库只有交易日数据，需验证连续性
4. **交易日历比对** — 获取交易日历，按周期计算应参照的连续交易周期日期，与数据库数据比对，确认数据完整性
5. **空查询缓存检查** — 如有数据缺失，检查 `empty_query_result` 表：
   - 已登记 → 之前 API 查询返回空，不再重复调用
   - 未登记 → 标记为需要 API 查询
6. **API 查询真正缺失数据** — 只对通过步骤 3+5 检查的缺失区间调用 API：
   - 返回空 → 登记到空查询缓存表
   - 有数据 → 合并到同步列表
7. **数据同步到数据库** — `KlineDataService` 通过 `KlineStorePort` 保存

### Interval Mapping
`Interval` 枚举 canonical 定义在 `domain/value_objects.py`，`shared_kernel/enums/interval.py` 为兼容性重导出。
- `MIN1` (10000) through `YEAR` (10012)
- Always use `get_sdk_interval_value()` to resolve SDK constants at runtime—**never hardcode values**

### Configuration
- `config/settings.toml`: 生产环境配置（非敏感设置）
- `config/settings.dev.toml`: 开发环境配置（含 30 分钟自动同步）
- **凭证管理（2026-07-06 回退到 SDK 路线）**：用 **infisical SDK + `.env` 文件** + Machine Identity：
  - `.env` 文件（项目根，`.gitignore` 已忽略）：含 `INFISICAL_CLIENT_ID/SECRET/PROJECT_ID` 三项 MI 凭证（SDK 启动用）+ 业务凭证 `GALAXY_*/DB_*`（SDK 拉取失败时兜底）。模板见 `.env.example`
  - 生产 systemd: `EnvironmentFile=<项目根>/.env` + `ExecStart=...python -m galaxy_core.application.scheduler`（无 CLI 包装，scheduler 进程内 `InfisicalConfig.initialize()` 自取 access_token 拉业务 secrets）
  - 开发命令: 无需前缀，直接 `uv run pytest` / `uv run galaxy-core ...`（SDK 自动从 `.env` 读 MI 凭证 → 拉 secrets）
  - 代码: `shared_kernel/utils/infisical_config.py` 的 `get_env()` 优先 Infisical → 其次 `os.environ`（含 `.env` 灌入值）→ 默认值。`ConfigLoader._apply_env_overrides` 和 `AsyncDatabaseManager.initialize` 统一走 `get_env`
  - 详见 `AGENTS.md` infisical 集成段
- `cache/`: API 本地缓存目录（如 `cache/basedata/`），存放 SDK 下载的 HDF5 等临时文件。该目录已加入 `.gitignore`，不应提交到版本控制

### AmazingData API 调用约定
- **API 不支持并发**：AmazingData SDK 客户端是单例，所有 API 调用必须**严格串行**（`asyncio.gather` 并发多个 `get_*` 调用会卡死或超时）。并发只能在 DB 层（多条 `save_*` 可 `asyncio.gather`）。
- **本地缓存机制**：`get_industry_daily` / `get_industry_weight` / `get_index_constituent` 等带 `is_local` 参数的 API，首次调用会下载全量数据到 `cache/`（HDF5），耗时可达数分钟到数十分钟；之后有缓存则秒回。回填历史数据时，超时设置：首次下载 ≥ 1 小时，有缓存 ≥ 30 分钟。
- **API 侧分批（内存预算模型，2026-07-10）**：SDK 调用必须分批，分批大小由 `shared_kernel/utils/chunking.py` 的内存预算模型决定，**不得硬编码 chunk_size**。
  - **核心公式**：`chunk_size = api_batch_rows / 每_symbol_行数`。`每_symbol_行数 = 窗口天数 / 周期单位交易日数`。调一个配置 `api_batch_rows`（默认 158 万 ≈ 2.5GB 内存水位）线性控制所有数据类型的内存。
  - **自适应行为**：全量大窗口（如 day 13 年）→ chunk ≈ 320（分批防 OOM）；增量小窗口（如 day 1 天）→ chunk ≈ 158 万（等于不分批，不浪费 API 调用）；稀疏周期（week/month）→ chunk 自动放大（数据少可多拉）。
  - **三类数据**：① 日度行情类（K线/fundflow per-symbol/industry_daily）走 `resolve_kline_chunk_size` 或 `resolve_daily_chunk_size`；② 成分股展开类（industry_weight）走 `resolve_weight_chunk_size`（独立小基准 20）；③ 稀疏类（financial/stock_basic/constituent）**不分批**，整组传安全（数据密度低）。
  - **配置**：`[sync.batch] api_batch_rows = 1580000`（内存预算）+ `weight_chunk_size = 20`（成分股）+ `fundflow_chunk_size = 100`（fundflow per-symbol）+ `db_upsert = 100`（DB 写入批）。
- **无效代码降级（2026-07-10）**：SDK 对退市/不存在代码在 month/season/year/margin_detail 等周期/接口会**严重卡顿**（实测 5 有效 + 1 无效 = 10x 慢甚至无限挂起）。adapter 层降级策略：① 预分类（`get_stock_list` 取有效代码集合，分有效/无效）；② 试探单只无效代码（10s 超时）；③ 秒回 → 全量，超时 → 只用有效。INDEX 类型 `get_stock_list` 会阻塞，跳过降级直接全量。见 `kline_provider_adapter._resolve_effective_codes` 和 `fund_flow_provider_adapter._filter_invalid_codes`。
- **SDK 阻塞超时**：所有 `asyncio.to_thread` 包装的 SDK 调用必须用 `asyncio.wait_for(timeout=self._api_timeout)` 包裹（默认 600s），防止 SDK 端挂起冻结事件循环。超时即 raise → `sync_with_retry` 重试。见 `kline_provider_adapter` / `reference_provider_adapter`。
- **universe 获取（2026-07-11）**：获取证券代码列表（universe）必须用 `get_hist_code_list`（SDK 历史代码表），**不用 `get_stock_list`**（调 `get_code_info`，在 CLI/scheduler 中不稳定）。K线 CLI、fundflow job、financial service 统一走 `reference_provider.get_hist_code_list(security_type, start_date, end_date, local_path)`。
- **fundflow per-symbol 分批**：fundflow 三表（long_hu_bang/block_trading/margin_detail）是事件驱动（非纯日度），内存预算模型不适用。用固定 `fundflow_chunk_size = 100`（实测 >200 只 SDK 严重变慢）。**不分段**（分段导致 SDK 累积限流，45 次调用比 1 次更慢）。margin_detail 对无效代码 10x 慢，走 `_filter_invalid_codes` 降级。
- **dividend 特殊处理（2026-07-11）**：dividend 的 reporting_period 是分红公告日（非季度末 0331/0630/0930/1231），`_build_period_groups` 对 dividend 用 `last + 1 天` 而非 `_next_period`。dividend 的 SDK 返回格式是 `dict[str, Series]`（列名→Series），`_normalize_to_dict` 检测并转置为 DataFrame。

### Environment Selection
```bash
# 开发环境（30分钟自动同步）
GALAXY_CONFIG_ENV=dev python -m galaxy_core.application.scheduler

# 生产环境（默认）
python -m galaxy_core.application.scheduler
```

## Important Conventions

### 字段命名规范
- `symbol` 保留为内部字段名，API 层 `code`/`MARKET_CODE` 由 adapter 映射
- stock_status 布尔字段带 `_sec` 后缀：`is_st_sec`, `is_susp_sec`, `is_xr_sec`, `is_wd_sec`
- `list_date`/`delist_date` 而非 `list_day`/`delist_day`
- Adapter 层做 API 字段名（大写）到内部字段名（snake_case）的映射
- 详见 `docs/naming-conventions.md`

### K-line Interval Naming
- Use `interval` for data cycle naming throughout the codebase, except for the literal `period` argument required by `ad.query_kline` SDK call
- The wrapper `AmazingDataClient.query_kline()` accepts `interval` internally

### Default Start Date Resolution
- Different security types have different data availability start dates
- Long periods (week/month/season/year) use special end date logic to avoid incomplete periods

### Trading Calendar
- `TradingCalendar` model has no `market` field—it's a shared calendar for all A-share markets
- Uniqueness is on `trade_date` only

### Database Models
- All K-line tables inherit from `BaseKline` abstract class
- Each table has `(symbol, trade_time)` unique constraint
- TimescaleDB hypertables are created automatically on `init_database()`

### Logging
- 生产日志只由 `galaxy-core scheduler`（守护进程）和 `galaxy-core <command>`（手动 CLI）产生，写入 `logs/{YYYYMMDD}/{HHMMSS}.log`。**文件名时间与日志行内 asctime 均为北京时间**（`shared_kernel/utils/constants.py` 的 `now_cst()` + `logging.Formatter.converter` 按 CST 转换；服务器系统时区为 UTC，见 AGENTS.md §3 2026-06-25 审计）。
- **一个日志文件 = 一个进程实例**，不是一条日志一个文件。审计"应有几条日志"等于"应有几个进程启动"。
- 测试**严禁**写入生产 `logs/`、`cache/`、`data/` 目录——见下方 Testing Notes。
- 生产配置（`settings.toml`）无 `auto_sync_interval_minutes`，只有定时触发：**00:10 K线**（每个交易日后一天，沪深 A 股 + ETF + 指数）+ **00:00 日历检查**（仅 12/20-12/31 真同步下一年交易日历，`CalendarSyncJob.run` 非 12 月立即 return 空转，见 `calendar_sync_job.py:45`）；开发配置（`settings.dev.toml`）有 30 分钟周期同步。**触发时刻按北京时间解释**：`scheduler.py` 用 `_now_cst()`（`ZoneInfo("Asia/Shanghai")`）取当前时间做触发判断，服务器系统时区虽为 UTC 但配置中的时刻统一理解为北京时间（见 AGENTS.md §3 2026-06-25 审计）。

### 数据库时区语义（2026-07-17 timestamptz 改造）

业务时间列与审计列均为 `TIMESTAMPTZ`（`DateTime(timezone=True)`），但语义区分：

| 列类 | 存储语义 | 举例 |
|---|---|---|
| **业务时间列**（trade_time / trade_date / list_date / delist_date） | 北京 wall-clock 对应的 instant | `2026-07-16 00:00:00+08`（北京 7/16 零点）|
| **审计列**（created_at / updated_at） | UTC instant | `2026-07-16 16:10:00+00`（UTC）|

**写入侧**：parse 入口统一用 `shared_kernel/utils/constants.py:localize_cst()` attach CST tzinfo（SDK 字面值是北京 wall-clock）。
**读取侧**：`async_connection.py` 的 `connect_args={"server_settings": {"TimeZone": "Asia/Shanghai"}}` 让 session 读出的 aware datetime 直接显示为北京 wall-clock；`.date()` 提取即北京日期。Python 侧如需显式取北京日期用 `dt.astimezone(CST).date()`。

**未改造的列**（有意保留）：
- String(8) 列（reporting_period / ann_date / in_date / out_date 等 8 表）—— 字符串 YYYYMMDD，无 tz 概念
- `last_sync_date.last_sync_date`（Date）—— 语义是「日期」非「时刻」（注意：该表 `updated_at` 已升 timestamptz，见下）

审计列 / 运行时间列（created_at / updated_at / started_at / completed_at）全部 `TIMESTAMPTZ` + 存 UTC instant（migration `23_biz_timestamptz` + `24_audit_timestamptz` 补齐）。

详见 AGENTS.md 2026-07-17 审计 + migration `23_biz_timestamptz` / `24_audit_timestamptz`。

### Alembic Migrations
- **保持单 head**。多 head 会让 `alembic upgrade head` 行为不确定。
- 新 migration 的 `down_revision` 必须指向**当前 head**，不是写 migration 那天的旧 revision。
- 提交前跑 `uv run alembic heads`，确认只输出一行。
- 同仓库内、单 DB → rebase 线性化（改 `down_revision`）；跨环境多部署 → `alembic merge`。

## Testing Notes

- Tests use `unittest.mock` heavily to avoid actual database/API calls
- Test directory structure: `tests/unit/` for unit tests, `tests/integration/` for integration tests
- K-line command tests in `tests/unit/kline/test_kline_command.py` verify CLI argument parsing and completeness check flow
- Integration tests require actual database connection; unit tests should mock `db_manager.session`
- Run unit tests: `pytest tests/unit/`
- Run integration tests: `pytest tests/integration/`
- Run all tests: `pytest tests/`

### 测试隔离（强制）
- **测试不得写入生产目录** `./logs/`、`./cache/`、`./data/`。文件输出类测试一律用 pytest `tmp_path` fixture。
- 复现"配置驱动的文件路径"行为时，把生产相对路径（如 `./logs/{date}/{time}.log`）替换为 `str(tmp_path) + "/{date}/{time}.log"`。
- 提交前检查清单：
  - [ ] `git status` 不应出现 `logs/`、`cache/`、`data/` 下新增文件
  - [ ] `pytest tests/` 跑完后 `logs/$(date +%Y%m%d)/` 文件数不增长

## Git Workflow

This is an independent Git repository hosted on Azure DevOps.

### Branch Rule
- **All changes must be committed to the `main` branch**.
- Before committing, verify: `git branch --show-current` outputs `main`.

### Commit Principles
1. **Minimize commit count** — merge logically related changes into one commit. Split only when a single change exceeds ~500 lines or spans unrelated modules.
2. **Detailed commit messages** — explain motivation, impact scope, and verification in the body.
3. **Commit format:** `<type>(<scope>): <imperative description>` (max 72 chars for title)

| Type | Use for |
|------|---------|
| `feat` | New functionality |
| `fix` | Bug fix |
| `refactor` | Internal restructuring (no external behavior change) |
| `docs` | Documentation updates |
| `test` | Test additions or updates |
| `chore` | Build, tooling, config changes |
| `perf` | Performance improvements |

### Pre-Commit Checklist
- [ ] `pytest tests/ -x` passes
- [ ] `ruff check .` clean
- [ ] `mypy src/` no new errors
- [ ] No sensitive files (`.env`, credentials) committed

### Example
```
refactor(database): remove sync methods from kline_completeness_checker

移除 KlineCompletenessChecker 的所有同步方法（check, get_missing_dates,
is_data_complete），仅保留异步版本。同步方法在 Phase 07 异步化后
已无人使用。

验证：pytest tests/unit/test_kline_completeness_checker.py -x 通过

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

## Language Preference

- 使用中文与用户交互
- 代码注释、日志消息、错误提示使用中文



---

## 1. 日志排查模板（运维 SOP）

上文 Logging 节定义了"日志文件=进程实例"的约定，排查步骤：

1. `ls logs/{date}/*.log` 列出当日所有进程（`{date}`/`{time}` 文件名时间 = 北京时间，见 §3 2026-06-25 审计）
2. 每个文件 `head -1` 看首行 logger 名分类：
   - `tests.*` → 测试污染（**违规**，违反上文 Testing Notes 测试隔离约定）
   - `galaxy_core.database.core.async_connection` → CLI/同步任务
   - `__main__` → scheduler 启动
   - 空文件 → 进程启动即崩
3. 生产配置（`settings.toml`）无周期同步，只有定时触发：**00:10 K线**（北京时间，交易日后一天）+ **00:00 日历检查**（北京时间，仅 12/20-12/31 真同步下一年日历，非 12 月 `CalendarSyncJob.run` 立即 return 空转，见 `calendar_sync_job.py:45`）。日志行内 asctime 也是北京时间。如果当天日志时间分散且不在整点，基本是手动启动或测试。

---

## 2. Scheduler 守护（systemd user service）

### 现状（2026-06-16 已修复，2026-06-25 时区校正）
- 生产 `settings.toml` 无 `auto_sync_interval_minutes` → 纯定时：**00:10 K线** + **00:00 日历检查**（仅 12/20-12/31 真同步，余空转）。**触发时刻按北京时间解释**（`scheduler.py` 的 `_now_cst()`，服务器系统时区为 UTC，见 §3 2026-06-25 审计）。
- 守护由 systemd user service `galaxy-core.service` 负责，unit 文件见 `docs/galaxy-core.service`，部署副本在 `~/.config/systemd/user/galaxy-core.service`。
- 进程由 `Restart=on-failure` + `StartLimitBurst=5` 守护，崩溃 10s 后自动重启。
- 日志进 journald：`journalctl --user -u galaxy-core.service`，同时按进程实例写 `logs/{date}/{time}.log`。

### 部署步骤（新机器）
```bash
cp docs/galaxy-core.service ~/.config/systemd/user/
# 编辑 unit：WorkingDirectory / EnvironmentFile / ExecStart 改为实际路径
# 非 NixOS：删除 Environment=LD_LIBRARY_PATH 行
systemctl --user daemon-reload
systemctl --user enable --now galaxy-core.service
# 开机自启（不登录也跑）：
sudo loginctl enable-linger <user>
```

### SDK 会话每日刷新 timer（2026-09-08 起,强制）
- `galaxy-core-refresh.timer`:每日 **北京 11:50**(服务器 TZ=UTC,即 03:50)oneshot `reset-failed + restart` 主服务——12:00 K线链前 10 分钟换新 TGW 会话。
- 根因:AmazingData SDK 长会话 **3-4 天后 query 类接口静默返空**(2026-09-04/09-08 两次实证,事件类接口不受影响),timer 保证会话最长 24h,永不到失效期。
- 部署副本 `~/.config/systemd/user/galaxy-core-refresh.{service,timer}`,service 内容(**NixOS 路径**,2026-09-09 纠错:`/usr/bin/systemctl` 在 NixOS 不存在,曾致首触 203/EXEC):
  ```
  [Service]
  Type=oneshot
  ExecStart=/run/current-system/sw/bin/systemctl --user reset-failed galaxy-core.service
  ExecStart=/run/current-system/sw/bin/systemctl --user restart galaxy-core.service
  ```
  timer:`OnCalendar=*-*-* 03:50:00 UTC` + `OnCalendar=*-*-* 16:05:00 UTC`(北京 00:05,日志午夜轮转偶发断流的兜底重建,2026-09-11 加)+ `Persistent=true`。
- 新机器部署**必须同步部署此 timer**,且部署后**手动 `systemctl --user start` 触发一次验证**(看主服务 ActiveEnterTimestamp 是否更新),否则 3-4 天后日线/行业日行情/margin_detail 断档复发。

### NixOS 坑
systemd user service **不继承** shell 的 nix-ld 环境。必须显式：
```
Environment=LD_LIBRARY_PATH=/run/current-system/sw/share/nix-ld/lib
```
否则 numpy/pandas import 失败（`libstdc++.so.6: cannot open shared object file`）。

### 代理注意
- 不要假设 scheduler 在跑。验证：
  ```bash
  systemctl --user status galaxy-core.service
  ps -p $(systemctl --user show galaxy-core.service -p MainPID --value)
  ```
  PID 文件 `data/logs/scheduler.pid` 记录的是启动 PID，不保证进程存活——以 `systemctl status` 为准。
- 改 scheduler 代码后：`systemctl --user restart galaxy-core.service`，看 `journalctl --user -u galaxy-core -f` 确认启动。

---

## 3. Agent 工作模式规约

### 3.1 Subagent 写权限边界（强制）

**subagent（Explore 类型等只读 agent）禁止用 bash heredoc / `cat > file` / 重定向绕过写权限。**

原因：
1. 只读是设计，非 bug — 沙箱隔离 subagent 的破坏面。
2. heredoc 绕过失去 Edit 工具的 `old_string` 唯一性校验 → 易误改。
3. harness 不跟踪 bash 写的文件 → file-state 失同步 → 后续 Edit 报"file modified since read"。
4. heredoc 内容含 `$(...)` / 反引号即 shell 执行 → 注入风险。

**正确模式**：
- subagent 把完整产出作 final message 返回。
- **父 agent**（有 Write/Edit 工具）落盘。
- 若 subagent 需写中间文件（如 outline），父 agent 接管 Write 调用。

**反例**（禁止）：
```bash
# subagent 内 — 禁止
cat > docs/example-notes.md << 'EOF'
...
EOF
```

**正例**（要求）：
```
# subagent final message：
"完整产出内容如下:[verbatim text]"
# 父 agent：
Write(file_path="docs/example-notes.md", content=<verbatim>)
```

### 3.2 大 phase 规划用 chunked mode

单 phase 新增 > 20 文件 / > 5 plan 时，单次 planner subagent 必超时（600s cap）。**强制 chunked**：
1. outline planner 先行（只写 `NN-PLAN-OUTLINE.md` 表格，小内容 ~2min）。
2. 单 plan 逐个 spawn（~3-5min/plan，独立可 resume）。
3. 父 agent 用 Write 落盘每个 plan（subagent 只读，见 §4.1）。

### 3.3 plan 文件命名（gate 兼容）

`check.decision-coverage-plan` 正则要求文件名以 `-PLAN.md` 结尾。多 plan phase 命名：
- `NN-MM-PLAN.md`（phase-plan-PLAN，如 `02-01-PLAN.md`）。
- 禁止 `NN-PLAN-MM-topic.md`（不匹配正则，gate 报 0 covered）。

---

## 维护

- 约定(架构/DI/命名/命令/测试)+ 排查 SOP → **本文件**（公开仓唯一事实源，内部台账不公开）
