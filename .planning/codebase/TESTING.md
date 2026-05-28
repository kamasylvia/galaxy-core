# Testing Patterns

> Last updated: 2026-04-01

## Overview

The galaxy-db-sync project uses pytest as its primary testing framework with unittest-style class organization for certain test suites. Tests are organized by type (unit, integration, kline) with fixtures defined in `conftest.py` files. The project emphasizes mocking external dependencies (database, API clients) to achieve fast, isolated unit tests.

## Test Framework

### Runner

- **Framework**: pytest (version >=9.0.2)
- **Alternative**: unittest.TestCase classes also supported
- **Config**: `pyproject.toml` section `[tool.pytest.ini_options]`

### Configuration

- File: `/home/laniakea/Development/galaxy-db-sync/pyproject.toml`
- Settings:
  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  python_files = ["test_*.py", "*_test.py"]
  ```

### Assertion Library

- **Primary**: pytest assertions (native Python assert)
- **unittest**: unittest.TestCase assertion methods (`self.assertEqual`, `self.assertTrue`, etc.)

### Run Commands

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_kline_completeness_checker.py

# Run specific test class
pytest tests/unit/test_kline_completeness_checker.py::TestLongPeriodChecker

# Run specific test method
pytest tests/unit/test_kline_completeness_checker.py::TestLongPeriodChecker::test_month_data_complete

# Run with verbose output
pytest -v

# Run unit tests only
pytest tests/unit/

# Run integration tests only
pytest tests/integration/

# Run with coverage (requires pytest-cov)
pytest --cov=src/galaxy_db_sync
```

## Test File Organization

### Directory Structure

```
tests/
├── __init__.py               # Package marker
├── unit/                     # Unit tests (fast, isolated)
│   ├── __init__.py
│   ├── conftest.py           # Unit test fixtures
│   ├── test_kline_completeness_checker.py
│   ├── test_trading_calendar_functionality.py
│   ├── test_kline_non_trading_day.py
│   ├── test_kline_command.py
│   └── shared_kernel/        # Tests for shared_kernel utilities
│       ├── __init__.py
│       └── utils/
│           ├── __init__.py
│           └── test_interval_boundary_checker.py
├── integration/              # Integration tests (database, API)
│   ├── __init__.py
│   ├── comprehensive_kline_test.py
│   └── test_timescale_integration.py
├── kline/                    # K-line specific tests
│   ├── test_kline_command.py
│   ├── comprehensive_acceptance_test.py
│   └── simple_kline_test.py
├── core/                     # Core functionality tests
│   ├── symbol_validator/
│   └── utils/
├── manual/                   # Manual/explore tests
│   ├── test_option_validation.py
│   └── test_option_api.py
└── simple_test.py            # Simple standalone tests
```

### Naming Conventions

- **Test files**: `test_<module>.py` or `<feature>_test.py`
- **Test classes**: `Test<Feature>` (PascalCase)
- **Test methods**: `test_<scenario>` (snake_case)

### Examples

```python
# Class naming from test_kline_completeness_checker.py
class TestCompletenessResult(unittest.TestCase):
    """CompletenessResult 数据类测试."""

class TestLongPeriodChecker(unittest.TestCase):
    """长周期检查器测试."""

class TestKlineCompletenessChecker(unittest.TestCase):
    """KlineCompletenessChecker 主类测试."""
```

## Test Structure

### Suite Organization (unittest style)

```python
# From tests/unit/test_kline_completeness_checker.py
class TestLongPeriodChecker(unittest.TestCase):
    """长周期检查器测试."""

    def setUp(self):
        """设置测试环境."""
        self.checker = LongPeriodChecker()

    @patch("galaxy_db_sync.database.services.kline_completeness_checker.trading_calendar_service")
    @patch("galaxy_db_sync.database.services.kline_completeness_checker.kline_service")
    def test_month_data_complete(self, mock_kline_service, mock_calendar_service):
        """测试月线数据完整的情况."""
        # Setup mocks
        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.index = [datetime(2024, 1, 2), datetime(2024, 2, 1), datetime(2024, 3, 1)]
        mock_kline_service.query_kline_from_db.return_value = {"000001.SZ": mock_df}

        # Execute test
        result = self.checker.check(
            symbol="000001.SZ",
            interval=Interval.MONTH,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
        )

        # Assertions
        self.assertTrue(result.is_complete)
        self.assertEqual(result.missing_count, 0)
        self.assertEqual(result.check_method, "long_period_continuity")
```

### Suite Organization (pytest style)

```python
# From tests/unit/shared_kernel/utils/test_interval_boundary_checker.py
class TestWeekIntervalComplete:
    """测试周线周期边界判断。"""

    def test_current_week_not_complete(self, mock_trading_calendar):
        """当前周未结束。"""
        today = date(2025, 3, 26)
        checker = IntervalBoundaryChecker(trading_calendar=mock_trading_calendar)

        assert checker.is_interval_complete(Interval.WEEK, date(2025, 3, 24), today) is False
        assert checker.is_interval_complete(Interval.WEEK, date(2025, 3, 26), today) is False
```

### Patterns

- **Setup**: Use `setUp()` for unittest or fixtures for pytest
- **Teardown**: Implicit (fixtures handle cleanup) or `tearDown()` for unittest
- **Assertion**: `self.assertEqual/assertTrue` for unittest, `assert` for pytest

## Mocking

### Framework

- **Tool**: `unittest.mock` (MagicMock, patch)
- **Import**: `from unittest.mock import MagicMock, patch`

### Patterns

```python
# Patching module-level dependencies
@patch("galaxy_db_sync.database.services.kline_completeness_checker.trading_calendar_service")
@patch("galaxy_db_sync.database.services.kline_completeness_checker.kline_service")
def test_month_data_complete(self, mock_kline_service, mock_calendar_service):
    ...

# Patching with context manager
with (
    patch("galaxy_db_sync.application.kline.command.parse_symbols") as mock_parse,
    patch("galaxy_db_sync.application.kline.command.get_valid_symbols_from_input") as mock_get_valid,
    patch("galaxy_db_sync.application.kline.command.kline_completeness_checker.check") as mock_check,
):
    mock_parse.return_value = [("symbol", "600000.SH")]
    mock_get_valid.return_value = ["600000.SH"]
    ...

# Creating mock objects
mock_df = MagicMock()
mock_df.empty = False
mock_df.index = [datetime(2024, 1, 2)]

# Mocking method return values
mock_kline_service.query_kline_from_db.return_value = {"000001.SZ": mock_df}
```

### What to Mock

- **Database services**: `kline_service`, `trading_calendar_service`, `db_manager`
- **External API clients**: `amazing_data_client`
- **Service instances**: Module-level singleton services
- **Config**: `get_config`, `get_section`

### What NOT to Mock

- **Pure functions**: Date parsing, symbol validation logic
- **Data classes**: `CompletenessResult`, `Interval` enum
- **Simple utilities**: String manipulation, type conversion

## Fixtures and Factories

### Fixture Definition

```python
# From tests/unit/conftest.py
@pytest.fixture
def mock_trading_calendar():
    """Create a mock trading calendar for testing.

    Returns a mock that simulates a standard trading calendar:
    - Weekdays (Mon-Fri) are trading days
    - Weekends (Sat-Sun) are not trading days
    """
    calendar = MagicMock()

    def is_trading_day(d: date) -> bool:
        """Simple trading day logic: weekdays are trading days."""
        return d.weekday() < 5  # 0-4 are Mon-Fri

    def get_previous_trading_day(d: date) -> date:
        """Get the previous trading day."""
        prev_day = d - timedelta(days=1)
        while not is_trading_day(prev_day):
            prev_day -= timedelta(days=1)
        return prev_day

    calendar.is_trading_day.side_effect = is_trading_day
    calendar.get_previous_trading_day.side_effect = get_previous_trading_day

    return calendar
```

### Fixture with Holidays

```python
@pytest.fixture
def mock_trading_calendar_with_holidays():
    """Create a mock trading calendar with specific holidays."""
    calendar = MagicMock()

    holidays = {
        date(2025, 1, 1),   # New Year's Day
        date(2025, 2, 17),  # Presidents Day
        date(2025, 4, 18),  # Good Friday
    }

    def is_trading_day(d: date) -> bool:
        if d in holidays:
            return False
        return d.weekday() < 5

    calendar.is_trading_day.side_effect = is_trading_day
    calendar.holidays = holidays

    return calendar
```

### Test Data

```python
# Creating DataFrame for test data
import pandas as pd

db_df = pd.DataFrame(
    {"close": [10.0]},
    index=pd.to_datetime(["2024-01-02"]),
)

api_df = pd.DataFrame(
    {"close": [11.0]},
    index=pd.to_datetime(["2024-01-03"]),
)

# Creating CompletenessResult
from galaxy_db_sync.database.services.kline_completeness_checker import CompletenessResult

result = CompletenessResult(
    is_complete=True,
    missing_count=0,
    total_count=100,
    coverage_ratio=1.0,
    missing_ranges=[],
    check_method="test_method",
)
```

### Fixture Location

- Unit tests: `tests/unit/conftest.py`
- Integration tests: `tests/conftest.py` (project-level)
- Shared fixtures: Define in nearest common `conftest.py`

## Coverage

### Requirements

- **Enforcement**: No strict coverage threshold enforced in config
- **Expectation**: Comprehensive coverage for core business logic
- **Focus areas**: Completeness checker, command handling, date validation

### View Coverage

```bash
# Run with coverage report
pytest --cov=src/galaxy_db_sync --cov-report=term-missing

# Generate HTML coverage report
pytest --cov=src/galaxy_db_sync --cov-report=html
```

## Test Types

### Unit Tests

- **Location**: `tests/unit/`
- **Scope**: Individual functions, classes, methods
- **Approach**: Mock all external dependencies
- **Speed**: Fast (no database/API calls)
- **Examples**:
  - `test_kline_completeness_checker.py` - Tests completeness logic with mocked services
  - `test_interval_boundary_checker.py` - Tests boundary checking logic
  - `test_kline_non_trading_day.py` - Tests non-trading day behavior

### Integration Tests

- **Location**: `tests/integration/`
- **Scope**: Multi-component interactions
- **Approach**: Real database connections, may use actual API
- **Speed**: Slower (real I/O)
- **Examples**:
  - `comprehensive_kline_test.py` - Full workflow testing
  - `test_timescale_integration.py` - TimescaleDB integration

### Kline Tests

- **Location**: `tests/kline/`
- **Scope**: K-line data specific functionality
- **Examples**:
  - `test_kline_command.py` - CLI command testing

### Manual/Exploratory Tests

- **Location**: `tests/manual/`
- **Purpose**: Development exploration, option validation
- **Note**: Not part of regular test suite

## Common Patterns

### Async Testing

- Not currently used (project is synchronous)

### Error Testing

```python
# Testing exception raising
def test_normalize_date_invalid(self):
    """测试无效日期格式."""
    with self.assertRaises(ValueError):
        self.checker._normalize_date("invalid")

# Testing exception with message
def test_get_sdk_interval_value_raises_when_sdk_constant_missing(self):
    """测试缺失 ad.constant 时直接报错."""
    fake_ad = SimpleNamespace()

    with patch("galaxy_db_sync.application.kline.command.ad", fake_ad):
        with self.assertRaisesRegex(RuntimeError, "missing ad.constant"):
            get_sdk_interval_value(IntervalOption.DAY)
```

### Parameterized Testing

```python
# Manual parameterization (no pytest.mark.parametrize in unittest)
def test_is_long_period(self):
    """测试长周期判断."""
    self.assertTrue(self.checker._is_long_period(Interval.MONTH))
    self.assertTrue(self.checker._is_long_period(Interval.SEASON))
    self.assertTrue(self.checker._is_long_period(Interval.YEAR))
    self.assertFalse(self.checker._is_long_period(Interval.WEEK))
    self.assertFalse(self.checker._is_long_period(Interval.DAY))
```

### Mocking External SDK

```python
# Mocking AmazingData SDK constants
fake_period = SimpleNamespace(
    min1=SimpleNamespace(value=10100),
    day=SimpleNamespace(value=10108),
    ...
)
fake_ad = SimpleNamespace(constant=SimpleNamespace(Period=fake_period))

with patch("galaxy_db_sync.application.kline.command.ad", fake_ad):
    self.assertEqual(get_sdk_interval_value(IntervalOption.DAY), 10108)
```

## CI/CD Testing

### Current Status

- **CI Pipeline**: Not configured (no `.github/` directory)
- **Recommendation**: Add GitHub Actions or similar CI

### Recommended CI Setup

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - run: pip install uv && uv sync
      - run: uv run pytest tests/unit/ -v
      - run: uv run pytest tests/ --cov=src
```

## Test Best Practices

1. **Isolate unit tests**: Mock database and API dependencies
2. **Use descriptive test names**: `test_<scenario>` pattern
3. **Test edge cases**: Invalid inputs, empty data, boundary dates
4. **Test error paths**: Ensure exceptions are raised correctly
5. **Keep tests focused**: One assertion concept per test method
6. **Use fixtures wisely**: Reusable mock objects in `conftest.py`
7. **Document test purpose**: Docstring explains what is being tested

## Key Testing Summary

| Aspect | Pattern |
|--------|---------|
| Framework | pytest + unittest.TestCase |
| Location | `tests/unit/`, `tests/integration/`, `tests/kline/` |
| Mocking | `unittest.mock.patch`, `MagicMock` |
| Fixtures | `conftest.py` with `@pytest.fixture` |
| Assertions | pytest `assert` or unittest methods |
| Coverage | Optional, focus on core logic |
| Naming | `test_<module>.py`, `Test<Class>` |