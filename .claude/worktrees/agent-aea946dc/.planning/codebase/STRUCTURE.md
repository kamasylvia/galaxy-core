# Codebase Structure

**Analysis Date:** 2026-04-01

## Directory Layout

```
galaxy-db-sync/
├── src/galaxy_db_sync/       # Main source package
│   ├── amazing_data/           # External API integration layer
│   ├── application/            # CLI and application orchestration
│   ├── database/               # Database models and services
│   └── shared_kernel/          # Cross-cutting utilities and domain primitives
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── kline/                  # K-line specific tests
├── scripts/                    # Utility and debugging scripts
├── config/                     # Configuration files
├── docs/                       # Documentation
│   ├── galaxy-db-sync/       # Project documentation
│   └── AmazingData/            # AmazingData SDK documentation (PDF/Markdown)
├── spec/                       # Feature specifications
├── plans/                      # Planning documents
│   ├── todo/                   # Pending tasks
│   └── completed/              # Completed phases
├── alembic/                    # Database migrations
├── wheels/                     # Local wheel packages (AmazingData SDK)
├── logs/                       # Runtime log files
└── cache/                      # API cache directory
```

## Directory Purposes

### Source Package (`src/galaxy_db_sync/`)

**`amazing_data/`**
- Purpose: AmazingData SDK integration
- Contains: API client wrapper, lazy client proxy
- Key files: `api/client.py` (AmazingDataClient singleton), `api/lazy_client.py`

**`application/`**
- Purpose: CLI commands and application flow orchestration
- Contains: Command parsers, handlers, result types, error definitions
- Key files:
  - `cli/commands.py` - Main CLI entry with argparse routing
  - `kline/command.py` - K-line sync orchestration (29KB, main sync logic)
  - `kline/result.py` - Result pattern types (KlineQueryResult, KlineItemResult)
  - `kline/error.py` - Error codes and KlineError class
  - `calendar/command.py` - Trading calendar commands

**`database/`**
- Purpose: Data persistence and ORM
- Contains: SQLAlchemy models, connection management, service classes
- Key files:
  - `core/connection.py` - DatabaseManager singleton (connection pool)
  - `core/timescale.py` - TimescaleDB hypertable setup
  - `models/kline.py` - 12 interval-specific K-line tables (BaseKline + subclasses)
  - `models/trading_calendar.py` - TradingCalendar model
  - `services/kline.py` - K-line CRUD operations (34KB, largest service)
  - `services/kline_data_sync.py` - API-to-database sync
  - `services/kline_completeness_checker.py` - Data completeness validation (24KB)
  - `services/trading_calendar.py` - Calendar CRUD

**`shared_kernel/`**
- Purpose: Shared domain primitives, utilities, exceptions
- Contains: Enums, validators, parsers, config loader, exceptions
- Key files:
  - `enums/interval.py` - Interval enum with SDK mapping
  - `enums/security_type.py` - Security type classification
  - `enums/akshare.py` - Akshare-compatible constants
  - `exceptions/*.py` - Hierarchical exception classes
  - `utils/symbol_validator.py` - Symbol validation (35KB, comprehensive validation)
  - `utils/time_parser.py` - Date parsing and resolution (22KB)
  - `utils/interval_boundary_checker.py` - Boundary validation (16KB)
  - `utils/config_loader/*.py` - TOML configuration loading
  - `utils/infisical_config.py` - Secret management integration

### Test Suite (`tests/`)

**`unit/`**
- Purpose: Unit tests for isolated component testing
- Contains: Mock-based tests for services, validators, parsers
- Key files:
  - `test_kline_completeness_checker.py` - Completeness checker tests (18KB)
  - `test_fetch_trading_calendar.py` - Calendar fetch tests
  - `test_security_type_inference.py` - Symbol type inference tests
  - `test_date_logic.py` - Date parsing tests
  - `conftest.py` - Shared fixtures

**`integration/`**
- Purpose: Integration tests with real database/API
- Contains: End-to-end sync tests

**`kline/`**
- Purpose: K-line specific functional tests
- Contains: K-line sync scenario tests
- Key files: `test_kline_command.py`

### Utility Scripts (`scripts/`)

**Purpose:** Debugging, monitoring, one-off operations

**Key categories:**
- Batch operations: `batch_sync_kline.py`
- Data verification: `check_kline_data.py`, `verify_kline_data_distribution.py`
- Calendar management: `sync_trading_calendar.py`, `check_trading_calendar_integrity.py`
- Debug helpers: `debug/debug_date_format.py`, `debug/debug_time_conversion.py`
- Performance monitoring: `performance_monitor.py`, `performance_watcher.py`
- Cleanup utilities: `cleanup_incomplete_long_period_kline.py`

### Configuration (`config/`)

**`settings.toml`**
- Purpose: Main application configuration
- Contains: Non-sensitive settings (pool sizes, timeouts, log settings)
- Sensitive values loaded from environment variables

### Documentation (`docs/`)

**`galaxy-db-sync/`**
- Purpose: Project-specific documentation
- Key files: `kline.md` - K-line sync documentation

**`AmazingData/`**
- Purpose: AmazingData SDK reference documentation
- Contains: PDF manuals and Markdown API references

### Specifications (`spec/`)

**Purpose:** Feature design documents and task tracking

**Key directories:**
- `kline/` - K-line sync specifications
- `kline_completeness_checker/` - Completeness checker design
- `trading_calendar/` - Calendar management specs
- `symbol_validator/` - Symbol validation specs
- `interval_boundary_checker/` - Boundary validation specs

### Database Migrations (`alembic/`)

**Purpose:** SQLAlchemy/Alembic database schema migrations

**Key files:**
- `alembic.ini` - Alembic configuration
- `env.py` - Migration environment setup
- `versions/` - Migration version files

## Key File Locations

### Entry Points

| File | Purpose |
|------|---------|
| `src/galaxy_db_sync/__main__.py` | Module entry (`python -m galaxy_db_sync`) |
| `src/galaxy_db_sync/__init__.py` | Package exports and version |
| `src/galaxy_db_sync/application/cli/commands.py` | CLI command routing |

### Configuration

| File | Purpose |
|------|---------|
| `config/settings.toml` | Application configuration (TOML) |
| `pyproject.toml` | Project metadata, dependencies, tool configs |
| `.env.example` | Environment variable template |
| `.env.infisical.example` | Infisical secret template |

### Core Logic

| File | Purpose |
|------|---------|
| `src/galaxy_db_sync/database/core/connection.py` | Database connection management |
| `src/galaxy_db_sync/database/models/kline.py` | K-line ORM models (12 tables) |
| `src/galaxy_db_sync/database/services/kline.py` | K-line database operations |
| `src/galaxy_db_sync/application/kline/command.py` | K-line sync orchestration |
| `src/galaxy_db_sync/shared_kernel/utils/symbol_validator.py` | Symbol validation |

### Testing

| File | Purpose |
|------|---------|
| `tests/unit/conftest.py` | Test fixtures |
| `tests/unit/test_kline_completeness_checker.py` | Completeness tests |

## Naming Conventions

### Files
- Python modules: snake_case (e.g., `kline_data_sync.py`)
- Test files: `test_<module>.py` (e.g., `test_kline_completeness_checker.py`)
- Config files: lowercase with extension (e.g., `settings.toml`)
- Spec documents: lowercase with extension (e.g., `spec-design-completeness-checker.md`)

### Directories
- Package directories: snake_case (e.g., `shared_kernel`, `kline_data_sync`)
- Test directories: lowercase (e.g., `unit`, `integration`)
- Documentation: lowercase (e.g., `galaxy-db-sync`, `AmazingData`)

### Classes
- Services: PascalCase with "Service" suffix (e.g., `KlineService`, `TradingCalendarService`)
- Models: PascalCase (e.g., `KlineDay`, `TradingCalendar`)
- Exceptions: PascalCase with "Error" suffix (e.g., `SymbolFormatError`)
- Enums: PascalCase (e.g., `Interval`, `SecurityType`)

### Variables/Functions
- Functions: snake_case (e.g., `resolve_default_start_date`, `parse_symbols`)
- Variables: snake_case (e.g., `completeness_result`, `missing_ranges`)
- Constants: UPPER_SNAKE_CASE (e.g., `INTERVAL_MODEL_MAP`)

## Where to Add New Code

### New Feature (K-line related)
- Primary implementation: `src/galaxy_db_sync/application/kline/` (command flow)
- Database operations: `src/galaxy_db_sync/database/services/kline.py`
- Tests: `tests/unit/` for unit tests, `tests/kline/` for functional tests

### New Feature (General)
- Application orchestration: `src/galaxy_db_sync/application/<feature>/`
- Database models: `src/galaxy_db_sync/database/models/<model>.py`
- Database services: `src/galaxy_db_sync/database/services/<service>.py`
- CLI commands: Add parser in `application/cli/commands.py`

### New Utility/Helper
- Shared utilities: `src/galaxy_db_sync/shared_kernel/utils/<name>.py`
- Enums: `src/galaxy_db_sync/shared_kernel/enums/<name>.py`
- Exceptions: `src/galaxy_db_sync/shared_kernel/exceptions/<name>.py`

### New Database Table
1. Create model in `src/galaxy_db_sync/database/models/<name>.py`
2. Export from `src/galaxy_db_sync/database/models/__init__.py`
3. Create service in `src/galaxy_db_sync/database/services/<name>.py`
4. Add Alembic migration in `alembic/versions/`

### New Test
- Unit tests: `tests/unit/test_<module>.py`
- Integration tests: `tests/integration/test_<module>.py`
- Fixtures: `tests/unit/conftest.py`

## Special Directories

### `wheels/`
- Purpose: Local wheel packages for AmazingData SDK
- Contains: `AmazingData-1.0.26-cp313-none-any.whl`
- Generated: No (vendored dependency)
- Committed: Yes

### `logs/`
- Purpose: Runtime log files
- Structure: `{date}/{time}.log` when `enable_separate_log_files = true`
- Generated: Yes (runtime)
- Committed: No (in `.gitignore`)

### `cache/`
- Purpose: API response cache
- Contains: AmazingData local cache files
- Generated: Yes (runtime)
- Committed: No

### `.planning/`
- Purpose: Planning and analysis documents
- Contains: `codebase/` for architecture/stack documents
- Generated: Yes (by GSD agents)
- Committed: Yes

### `alembic/versions/`
- Purpose: Database schema migration history
- Contains: numbered migration scripts
- Generated: Yes (`alembic revision`)
- Committed: Yes

---

*Structure analysis: 2026-04-01*