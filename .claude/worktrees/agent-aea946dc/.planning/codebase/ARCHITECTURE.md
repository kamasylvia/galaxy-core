# Architecture

**Analysis Date:** 2026-04-01

## Project Vision

**galaxy-db-sync** 是一个将银河证券 AmazingData API 中所有金融数据同步到 PostgreSQL/TimescaleDB 数据库的统一数据桥梁。

**当前实现状态**: 仅完成了 K线数据同步和交易日历管理，后续将扩展支持更多数据类型（行情报价、财务数据、资金流向等）。

## Pattern Overview

**Overall:** Layered Architecture with Service-Oriented Design

**Key Characteristics:**
- Clear separation between CLI/Application, Database, External API, and Shared Kernel layers
- Singleton pattern for core managers (DatabaseManager, AmazingDataClient)
- Table-per-interval strategy for K-line data storage (12 separate tables)
- Lazy initialization for external API client to defer authentication
- Result pattern for structured error handling and response encapsulation

## Layers

### CLI/Application Layer
- Purpose: Command-line interface and application orchestration
- Location: `src/galaxy_db_sync/application/`
- Contains: CLI command parsers, command handlers, result types, error definitions
- Depends on: Database services, Shared kernel utilities, AmazingData client
- Used by: Entry point (`__main__.py`)

**Sub-modules:**
- `application/cli/commands.py`: Main CLI entry point with argparse-based command routing
- `application/kline/command.py`: K-line sync orchestration, completeness checking, batch sync
- `application/calendar/command.py`: Trading calendar management commands

### Database Layer
- Purpose: Data persistence, ORM models, and database operations
- Location: `src/galaxy_db_sync/database/`
- Contains: SQLAlchemy models, connection management, service classes
- Depends on: SQLAlchemy, TimescaleDB, Shared kernel enums
- Used by: Application layer services

**Sub-modules:**
- `database/core/connection.py`: Singleton `DatabaseManager` with connection pool management
- `database/core/timescale.py`: TimescaleDB hypertable creation
- `database/models/kline.py`: 12 interval-specific K-line tables (KlineMin1 through KlineYear)
- `database/models/trading_calendar.py`: Trading calendar model (shared-date, no market field)
- `database/services/kline.py`: K-line query/save operations, bulk upsert
- `database/services/kline_data_sync.py`: API-to-database sync orchestration
- `database/services/kline_completeness_checker.py`: Data completeness validation
- `database/services/trading_calendar.py`: Trading calendar CRUD operations

### External API Layer (AmazingData)
- Purpose: Integration with Galaxy Securities AmazingData SDK
- Location: `src/galaxy_db_sync/amazing_data/api/`
- Contains: Client wrapper, lazy initialization proxy
- Depends on: AmazingData SDK (local wheel), configuration loader
- Used by: Application layer, Database sync services

**Key components:**
- `amazing_data/api/client.py`: `AmazingDataClient` singleton with login/logout, query methods
- `amazing_data/api/lazy_client.py`: `LazyAmazingDataClient` for deferred initialization

### Shared Kernel Layer
- Purpose: Cross-cutting utilities, enums, exceptions, and domain primitives
- Location: `src/galaxy_db_sync/shared_kernel/`
- Contains: Enums, exception hierarchy, validators, parsers, config loader
- Depends on: Minimal external dependencies
- Used by: All other layers

**Sub-modules:**
- `shared_kernel/enums/interval.py`: Interval enum with SDK-to-database mapping
- `shared_kernel/enums/security_type.py`: Security type classification (SH_A, SZ_ETF, etc.)
- `shared_kernel/enums/akshare.py`: Akshare-compatible constants
- `shared_kernel/exceptions/`: Hierarchical exception classes (API, validation, cache errors)
- `shared_kernel/utils/symbol_validator.py`: Security code format validation, type inference
- `shared_kernel/utils/time_parser.py`: Date parsing, padding, default date resolution
- `shared_kernel/utils/interval_boundary_checker.py`: Week/Month/Season/Year boundary validation
- `shared_kernel/utils/config_loader/`: TOML configuration loading with section access
- `shared_kernel/utils/infisical_config.py`: Infisical secret management integration

## Data Flow

### K-line Sync Flow

1. CLI receives command: `galaxy kline "SH_A" --interval day --start 20200101 --end 20250101`
2. `handle_kline_command()` validates parameters and resolves default dates
3. Symbol validation expands SecurityType to actual symbol list
4. Completeness checker queries database for existing data coverage
5. Missing ranges are identified and grouped by date interval
6. API client fetches data for missing ranges in batches
7. KlineService performs bulk upsert to appropriate interval table
8. Sync result is returned with success/failure statistics

**Completeness Check Flow:**
```
CompletenessResult
├── is_complete: bool
├── coverage_ratio: float
├── missing_count: int
├── total_count: int
├── missing_ranges: List[Tuple[date, date]]
└── existing_ranges: List[Tuple[date, date]]
```

### Trading Calendar Flow

1. CLI receives calendar command
2. TradingCalendarService queries existing calendar data
3. Missing years are identified
4. AmazingData API fetches trading day calendar
5. Data is merged with existing calendar (no market field, shared-date model)

**State Management:**
- Database connection pool managed by singleton `DatabaseManager`
- AmazingData session managed by singleton `AmazingDataClient` with lazy init
- Trading calendar cached in database, no in-memory state

## Key Abstractions

### Interval Enum
- Purpose: Bridge between AmazingData SDK period constants and database table names
- Examples: `src/galaxy_db_sync/shared_kernel/enums/interval.py`
- Pattern: Enum with bidirectional mapping (SDK value <-> database value)

```python
# SDK value 10008 maps to database interval "day"
Interval.from_sdk_period_value(10008)  # Returns Interval.DAY
Interval.DAY.to_sdk_period_value()     # Returns 10008
```

### Kline Model (Table-per-Interval)
- Purpose: Separate tables for each K-line interval for optimized querying
- Examples: `src/galaxy_db_sync/database/models/kline.py`
- Pattern: Abstract base class `BaseKline` with 12 concrete subclasses

```python
# Dynamic table selection via INTERVAL_MODEL_MAP
INTERVAL_MODEL_MAP = {
    Interval.MIN1.value: KlineMin1,
    Interval.DAY.value: KlineDay,
    Interval.YEAR.value: KlineYear,
    # ... 12 total
}
```

### TradingCalendar (Shared-Date Model)
- Purpose: Single trading calendar table without market-specific entries
- Examples: `src/galaxy_db_sync/database/models/trading_calendar.py`
- Pattern: Unique constraint on `trade_date` only (no market field)

```python
class TradingCalendar(Base):
    trade_date = Column(Date, nullable=False)
    is_trading_day = Column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("trade_date", name="uq_trade_date"),)
```

### CompletenessResult
- Purpose: Encapsulate data completeness analysis for sync orchestration
- Examples: `src/galaxy_db_sync/database/services/kline_completeness_checker.py`
- Pattern: Dataclass with coverage metrics and missing range detection

### Result Pattern (KlineQueryResult)
- Purpose: Structured response with success/error per-symbol breakdown
- Examples: `src/galaxy_db_sync/application/kline/result.py`
- Pattern: Container for `KlineItemResult` objects with success/error states

## Entry Points

### CLI Entry Point
- Location: `src/galaxy_db_sync/__main__.py`
- Triggers: `python -m galaxy_db_sync` or `galaxy` command
- Responsibilities: Routes to `application/cli/commands.py:main()`

### Installed Command Entry
- Location: Defined in `pyproject.toml` as `galaxy-db-sync`
- Triggers: `galaxy-db-sync kline ...` or `galaxy-db-sync calendar ...`
- Responsibilities: argparse-based subcommand routing

### Module API Entry
- Location: `src/galaxy_db_sync/__init__.py`
- Triggers: `from galaxy_db_sync import ...`
- Responsibilities: Exports `AmazingDataClient`, `DatabaseManager`, `ConfigLoader`

## Error Handling

**Strategy:** Hierarchical exception classes with typed error codes

**Patterns:**
- Base exception: `GalaxyDBBridgeError`
- Category exceptions: `ValidationError`, `APIError`, `CacheError`, `ConfigurationError`
- Specific exceptions: `SymbolFormatError`, `APITimeoutError`, `CacheConnectionError`
- Result pattern: `KlineItemResult.from_error()` for structured error responses
- Error codes: `KlineErrorCode` enum (SDK_BUG_ERROR, NO_DATA_FOUND, INVALID_CODE)

**Exception hierarchy:**
```
GalaxyDBBridgeError
├── ConfigurationError
├── ValidationError
│   ├── SymbolFormatError
│   ├── SymbolNotFoundError
│   └── SecurityTypeError
├── APIError
│   ├── APITimeoutError
│   ├── APIRateLimitError
│   ├── APIConnectionError
│   └── APIResponseError
└── CacheError
    ├── CacheConnectionError
    └── CacheOperationError
```

## Cross-Cutting Concerns

**Logging:**
- Configured via `config/settings.toml` [logging] section
- Supports separate log files per execution run (`enable_separate_log_files = true`)
- Pattern: `./logs/{date}/{time}.log`

**Validation:**
- Symbol format validation via regex patterns in `symbol_validator.py`
- Date range validation with interval-specific precision checks
- Interval boundary validation for week/month/season/year periods

**Authentication:**
- AmazingData credentials via environment variables (`GALAXY_USERNAME`, `GALAXY_PASSWORD`)
- Database credentials via environment variables (`DB_HOST`, `DB_USER`, `DB_PASSWORD`)
- Infisical integration for secret management (`infisical_config.py`)

**Configuration:**
- TOML-based configuration in `config/settings.toml`
- Environment variable overrides for sensitive values
- Section-based access via `get_section()`

---

*Architecture analysis: 2026-04-01*