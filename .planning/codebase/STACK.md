# Technology Stack

**Analysis Date:** 2026-04-01

## Project Vision

**galaxy-db-sync** 是银河证券 AmazingData API 的统一数据同步桥梁，目标是将 API 中的所有金融数据同步到 PostgreSQL/TimescaleDB。

**当前实现**: K线数据同步（12种周期）+ 交易日历管理
**未来扩展**: 行情报价、财务数据、资金流向、板块数据等

## Languages

**Primary:**
- Python 3.13 - Main application language (strict version constraint: `>=3.13,<3.14`)
- Version file: `.python-version` contains `3.13`

**Secondary:**
- None - Single-language project

## Runtime

**Environment:**
- Python 3.13 interpreter
- Virtual environment managed via `uv` (recommended in README)

**Package Manager:**
- `uv` - Modern Python package manager (recommended v0.1+)
- `pip` - Standard pip also supported
- Lockfile: Not present (no requirements.lock or uv.lock detected)

## Frameworks

**Core:**
- SQLAlchemy 2.0+ - ORM and database abstraction layer
- Click 8.0+ - CLI framework for command-line interface
- Alembic 1.13.1+ - Database migration tool

**Testing:**
- pytest 9.0.2+ - Test runner and framework

**Build/Dev:**
- setuptools 61.0+ - Build backend
- Hatch - Build frontend configuration (in pyproject.toml)

**Code Quality:**
- Ruff 0.8.0+ - Fast Python linter/formatter (targets py313, line-length 100)
- MyPy 1.0.0+ - Static type checker (strict mode enabled)
- Black 26.1.0+ - Code formatter

## Key Dependencies

**Critical:**
- `AmazingData 1.0.26` - Proprietary SDK for Galaxy Securities data API
  - Installed from local wheel: `wheels/AmazingData-1.0.26-cp313-none-any.whl`
  - Requires `tgw` wheel dependency: `wheels/tgw-1.0.8.5-py3-none-any.whl`
- `psycopg2-binary 2.9.5+` - PostgreSQL database adapter
- `pandas 2.0.0+` - Data manipulation for K-line processing
- `numpy 1.24.0+` - Numerical computing support

**Infrastructure:**
- `requests 2.25.0+` - HTTP client for API calls and Infisical integration
- `python-dotenv 1.0.0+` - Environment variable loading from `.env`

## Configuration

**Environment:**
- TOML-based configuration: `config/settings.toml`
- Environment variables via `.env` (not committed)
- Secrets management via Infisical HTTP API (optional)
- Config loader implementation: `src/galaxy_db_sync/shared_kernel/utils/config_loader/config.py`

**Build:**
- `pyproject.toml` - Modern Python project configuration
- `alembic.ini` - Database migration configuration
- Entry points defined:
  - `galaxy` → `galaxy_db_sync.__main__:main`
  - `galaxy-db-sync` → `galaxy_db_sync.application.cli.commands:main`

**Key Configuration Sections (`config/settings.toml`):**
- `[amazing_data]` - API connection settings (credentials via env vars)
- `[database]` - PostgreSQL connection pool settings
- `[sync]` - Data synchronization parameters (batch_size, default_start_year)
- `[logging]` - Log level, file path, rotation settings

## Platform Requirements

**Development:**
- Python 3.13 runtime
- PostgreSQL 18+ (recommended)
- Galaxy Securities AmazingData API account credentials
- `uv` package manager (recommended)

**Production:**
- PostgreSQL/TimescaleDB for time-series data storage
- Network access to Galaxy Securities API server (IP and port configured via env)
- Optional: Infisical secrets management service

## Database Technology

**Primary Database:**
- PostgreSQL with TimescaleDB extension
- TimescaleDB hypertables for K-line time-series data
- 12 interval-specific tables: `kline_min1` through `kline_year`
- Connection pool: size 10, max_overflow 20, timeout 30s

**ORM:**
- SQLAlchemy 2.0 declarative models
- Model definitions: `src/galaxy_db_sync/database/models/kline.py`
- Database manager: `src/galaxy_db_sync/database/core/connection.py`
- TimescaleDB integration: `src/galaxy_db_sync/database/core/timescale.py`

**Migrations:**
- Alembic for schema migrations
- Migration scripts in `alembic/versions/`

---

*Stack analysis: 2026-04-01*