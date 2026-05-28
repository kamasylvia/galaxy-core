# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Galaxy DB Bridge is a data ingestion tool that fetches market data from China Galaxy Securities' AmazingData API and persists it to PostgreSQL/TimescaleDB. It supports K-line (candlestick) data synchronization for Chinese A-shares, ETFs, and other securities.

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

# Run specific test file
pytest tests/kline/test_kline_command.py

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
# Initialize database tables
python -m galaxy_db_sync --init-db

# Fetch K-line data
galaxy-db-sync kline 600000.SH --interval day --start 20230101 --end 20231231

# Fetch with SecurityType (batch)
galaxy-db-sync kline SH_A --interval day --start 20230101 --end 20231231

# Fetch calendar data
galaxy-db-sync calendar --year 2024
```

## Architecture

### Layer Structure
```
src/galaxy_db_sync/
├── amazing_data/api/         # AmazingData SDK wrapper
│   ├── client.py             # Singleton API client with lazy initialization
│   └── lazy_client.py        # Lazy loading proxy
├── application/cli/          # CLI entry point
│   └── commands.py           # argparse-based command dispatcher
├── application/kline/        # K-line domain logic
│   ├── command.py            # CLI handler, completeness check, sync orchestration
│   ├── error.py              # Error types and error codes
│   └── result.py             # Result wrapper types
├── database/
│   ├── core/                 # Connection management
│   │   ├── connection.py     # SQLAlchemy session management (singleton)
│   │   └── timescale.py      # TimescaleDB hypertable setup
│   ├── models/               # SQLAlchemy ORM models
│   │   ├── kline.py          # K-line tables (one per interval)
│   │   └── trading_calendar.py
│   └── services/             # Data access layer
│       ├── kline.py          # K-line CRUD operations
│       ├── kline_data_sync.py # Batch sync with completeness check
│       ├── kline_completeness_checker.py # Missing data detection
│       ├── trading_calendar.py
│       └── empty_query.py    # Empty result cache to avoid repeated API calls
└── shared_kernel/
    ├── enums/                # Shared enumerations
    │   ├── interval.py       # K-line interval enum with SDK value mapping
    │   └── security_type.py  # Security type classification
    └── utils/                # Shared utilities
        ├── config_loader/    # TOML + env var configuration
        ├── symbol_validator.py
        ├── time_parser.py    # Date parsing with interval-aware defaults
        └── interval_boundary_checker.py # Long period boundary validation
```

### Key Design Patterns

1. **Singleton Pattern**: `DatabaseManager`, `AmazingDataClient` use singleton for connection reuse
2. **Lazy Initialization**: `LazyAmazingDataClient` defers SDK login until first use
3. **Table-per-Interval**: Each K-line interval has its own TimescaleDB hypertable (e.g., `kline_min1`, `kline_day`)
4. **Completeness-First Sync**: CLI checks database before fetching; only fetches missing ranges
5. **Empty Result Caching**: Avoids repeated API calls for date ranges with no data
6. **全异步数据库层**: 所有数据库交互必须使用 `async_db_manager` 和 `AsyncSession`，禁止同步 `db_manager` 在异步调用链中使用

### Data Flow
```
CLI Command → Command Handler → Completeness Check → (if incomplete) → Batch Sync
                                     ↓                                      ↓
                            Trading Calendar                        AmazingData API
                                     ↓                                      ↓
                            Missing Ranges                          K-line Data
                                     ↓                                      ↓
                            Empty Query Cache                       Database UPSERT
```

### K-line Query Workflow

K线查询的完整流程：

1. **用户发起查询或自动查询触发** — CLI 命令或 Scheduler 定时任务
2. **从数据库获取K线数据** — `KlineService.query_kline_from_db()`
3. **数据连续性检查** — 因为数据库只有交易日数据，需验证连续性
4. **交易日历比对** — 获取交易日历，按周期计算应参照的连续交易周期日期，与数据库数据比对，确认数据完整性
5. **空查询缓存检查** — 如有数据缺失，检查 `empty_query_result` 表：
   - 已登记 → 之前 API 查询返回空，不再重复调用
   - 未登记 → 标记为需要 API 查询
6. **API 查询真正缺失数据** — 只对通过步骤 3+5 检查的缺失区间调用 API：
   - 返回空 → 登记到空查询缓存表
   - 有数据 → 合并到同步列表
7. **数据同步到数据库** — `KlineService.save_kline_to_db()`

### Interval Mapping
The `Interval` enum in `shared_kernel/enums/interval.py` maps to AmazingData SDK's `Period` constants:
- `MIN1` (10000) through `YEAR` (10012)
- Always use `get_sdk_interval_value()` to resolve SDK constants at runtime—**never hardcode values**

### Configuration
- `config/settings.toml`: 生产环境配置（非敏感设置）
- `config/settings.dev.toml`: 开发环境配置（含 30 分钟自动同步）
- `.env`: 敏感凭证（数据库连接、API 凭证）— 不要提交

### Environment Selection
```bash
# 开发环境（30分钟自动同步）
GALAXY_CONFIG_ENV=dev python -m galaxy_db_sync.scheduler

# 生产环境（默认）
python -m galaxy_db_sync.scheduler
```

## Important Conventions

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

## Testing Notes

- Tests use `unittest.mock` heavily to avoid actual database/API calls
- K-line command tests in `tests/kline/test_kline_command.py` verify CLI argument parsing and completeness check flow
- Integration tests require actual database connection; unit tests should mock `db_manager.session`

## Development Workflow (gstack + GSD)

This project uses two AI workflow systems together:
- **gstack** — strategy reviews, QA testing, code review, shipping (`/autoplan`, `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`, `/qa`, `/review`, `/ship`)
- **GSD** — roadmapping, phase planning, execution, verification (`/gsd:plan-phase`, `/gsd:execute-phase`, `/gsd:verify-work`)
- **`/gstack-to-gsd`** — bridges gstack reviews into GSD and auto-triggers planning

**Lifecycle: Strategy -> Roadmap -> Bridge+Plan -> Build -> Verify -> Ship**

1. STRATEGY (gstack): `/autoplan` or individual reviews (`/plan-ceo-review` + `/plan-eng-review` + `/plan-design-review`)
2. ROADMAP: `/gstack-to-gsd roadmap` (CEO plan -> ROADMAP phases + REQUIREMENTS.md)
3. BRIDGE+PLAN: `/gstack-to-gsd phase N` (bridges eng+design reviews -> RESEARCH.md, then auto-triggers `/gsd:plan-phase N`)
4. BUILD (GSD): `/gsd:execute-phase N`
5. VERIFY (GSD): verification runs inside execute-phase; for manual testing use `/gsd:verify-work N`
6. SHIP (gstack): `/review` then `/ship`

**"What should I do next?" decision tree:**
- No CEO plan in `~/.gstack/projects/`? -> `/autoplan` or `/plan-ceo-review`
- CEO plan exists but phases not in `.planning/ROADMAP.md`? -> `/gstack-to-gsd roadmap`
- Phase in ROADMAP but no `PLAN.md`? -> `/gstack-to-gsd phase N` (bridges + plans in one step)
- Phase has `PLAN.md` but no `SUMMARY.md`? -> `/gsd:execute-phase N`
- Phase verified and all phases done? -> `/review` then `/ship`
- Unsure? -> `/gstack-to-gsd status` (shows unified state)

## Language Preference

- 使用中文与用户交互
- 代码注释、日志消息、错误提示使用中文

