# Coding Conventions

> Last updated: 2026-04-01

## Overview

The galaxy-db-sync project follows Python 3.13 conventions with strict type checking (mypy strict mode), Chinese documentation style, and comprehensive testing coverage. The codebase emphasizes clean architecture separation between application, domain, and infrastructure layers.

## Naming Patterns

### Files

- **Modules**: `snake_case.py` - All Python module files use lowercase with underscores
  - Examples: `command.py`, `kline.py`, `time_parser.py`, `symbol_validator.py`
- **Test files**: `test_<module>.py` or `<module>_test.py`
  - Examples: `test_kline_command.py`, `test_interval_boundary_checker.py`
- **Package structure**: Each package has `__init__.py` for exports
  - Example: `src/galaxy_db_sync/shared_kernel/__init__.py`

### Functions

- **Pattern**: `snake_case` with descriptive names
- **Private functions**: Prefix with underscore `_function_name`
- **Examples**:
  - `parse_symbols(value: str) -> list[tuple[str, str]]`
  - `_generate_expected_periods(interval, start_date, end_date)`
  - `validate_symbol_format(symbol: str) -> bool`

### Variables

- **Pattern**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE` at module level
- **Examples**:
  - `interval_str`, `start_date`, `valid_symbols`
  - `DEFAULT_START_DATE_BY_SECURITY_TYPE` (constant dict)

### Classes

- **Pattern**: `PascalCase`
- **Exception classes**: End with `Error`
- **Service classes**: End with `Service` or descriptive purpose
- **Examples**:
  - `KlineService`, `KlineCompletenessChecker`, `IntervalBoundaryChecker`
  - `GalaxyDBBridgeError`, `ValidationError`, `SymbolFormatError`
  - `CompletenessResult` (data class)

### Enums

- **Pattern**: `PascalCase` for enum class, `UPPER_CASE` for members
- **Examples**:
  ```python
  class Interval(Enum):
      MIN1 = "min1"
      DAY = "day"
      MONTH = "month"
      YEAR = "year"
  ```
  - File: `src/galaxy_db_sync/shared_kernel/enums/interval.py`

## Code Style

### Formatting Tools

- **Primary formatter**: Black (version >=26.1.0)
- **Line length**: 100 characters (configured in pyproject.toml)
- **Target version**: Python 3.13

### Linting

- **Tool**: Ruff (version >=0.8.0)
- **Rules selected**: `["E", "F", "I", "W", "UP", "B", "C4", "SIM"]`
  - E: pycodestyle errors
  - F: Pyflakes
  - I: isort
  - W: pycodestyle warnings
  - UP: pyupgrade
  - B: flake8-bugbear
  - C4: flake8-comprehensions
  - SIM: flake8-simplify

### Configuration Location

- File: `pyproject.toml` at `/home/laniakea/Development/galaxy-db-sync/pyproject.toml`
- Key sections:
  ```toml
  [tool.ruff]
  target-version = "py313"
  line-length = 100
  select = ["E", "F", "I", "W", "UP", "B", "C4", "SIM"]

  [tool.mypy]
  python_version = "3.13"
  warn_return_any = true
  warn_unused_configs = true
  strict = true
  ```

## Type Annotations

### Usage Pattern

- **Strict mode**: mypy strict mode is enabled, all functions must have type annotations
- **Return types**: Always specify return type, including `None` for functions with no return
- **Union types**: Use `Union[X, Y]` or `X | Y` (Python 3.10+ style)
- **Optional**: Use `Optional[T]` or `T | None`

### Examples

```python
# From src/galaxy_db_sync/shared_kernel/utils/symbol_validator.py
def infer_security_type(symbol: str) -> Optional[str]:
    """根据证券代码推断其类型"""
    ...

def parse_symbols(value: str) -> list[tuple[str, str]]:
    """解析 symbols 参数"""
    ...

# From src/galaxy_db_sync/database/services/kline.py
def query_kline_from_db(
    self,
    symbols: List[str],
    start_date: Optional[Union[str, int, datetime]] = None,
    end_date: Optional[Union[str, int, datetime]] = None,
    interval: str = "day",
) -> Dict[str, pd.DataFrame]:
    """从数据库查询 K 线数据"""
    ...
```

### Type Annotation Locations

- Function signatures: All parameters and return types
- Class attributes: Annotated in class body or `__init__`
- Module-level variables: When they serve as public interfaces

## Documentation Style

### Docstrings

- **Language**: Chinese (Simplified)
- **Format**: Triple-quoted strings with period ending
- **Sections**:
  - Brief description (required)
  - Args section with parameter descriptions
  - Returns section with return value description

### Examples

```python
# From src/galaxy_db_sync/database/services/kline.py
"""K 线数据服务层.

提供 K 线数据的数据库操作接口，包括查询、保存等功能。
"""

def query_kline_from_db(
    self,
    symbols: List[str],
    start_date: Optional[Union[str, int, datetime]] = None,
    end_date: Optional[Union[str, int, datetime]] = None,
    interval: str = "day",
) -> Dict[str, pd.DataFrame]:
    """从数据库查询 K 线数据.

    Args:
        symbols: 证券代码列表
        start_date: 开始日期
        end_date: 结束日期
        interval: K 线周期

    Returns:
        以证券代码为键的 K 线数据 DataFrame 字典
    """
```

### Module Headers

- Each module starts with a docstring describing its purpose
- Example from `src/galaxy_db_sync/application/kline/command.py`:
  ```python
  """K 线命令模块.

  此模块提供 `kline` CLI 主流程，并保留面向程序内调用的查询兼容入口。
  当前命令层主语义已统一为：先做完整性检查，再按缺失区间触发同步。
  """
  ```

### Inline Comments

- Use for complex logic explanations
- Language: Chinese
- Place above the code being explained

## Import Organization

### Order (per Ruff/isort)

1. Standard library imports
2. Third-party imports (pandas, sqlalchemy, AmazingData)
3. Local application imports (from `galaxy_db_sync.*`)

### Examples

```python
# Standard library
import argparse
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Third-party
import AmazingData as ad
import pandas as pd

# Local application
from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.shared_kernel.enums.interval import Interval
from .error import KlineError, KlineErrorCode
from .result import KlineItemResult, KlineQueryResult, KlineSyncResult
```

### Path Style

- Use absolute imports for cross-package references
- Use relative imports within same package (`from .error import ...`)
- No implicit relative imports

## Error Handling

### Exception Hierarchy

- Base: `GalaxyDBBridgeError` at `src/galaxy_db_sync/shared_kernel/exceptions/base.py`
- Domain-specific exceptions inherit from base
- Categories:
  - `ConfigurationError` - Configuration issues
  - `ValidationError` - Input validation failures
  - `SymbolFormatError`, `SymbolNotFoundError` - Symbol validation
  - `SecurityTypeError` - Security type issues

### Pattern

```python
# From src/galaxy_db_sync/shared_kernel/exceptions/validation.py
class ValidationError(GalaxyDBBridgeError):
    """验证错误基类"""

    def __init__(
        self, message: str, field: str = None, value: str = None, *args, **kwargs
    ):
        super().__init__(message, *args)
        self.field = field
        self.value = value
```

### Error Raising

- Raise specific exceptions with descriptive messages
- Include context (field name, value) where applicable
- Example:
  ```python
  raise ValueError(f"不支持的周期: {interval}")
  raise SymbolFormatError(symbol, message=f"证券代码格式错误: {symbol}")
  ```

### Error Handling in Services

- Log errors before re-raising or handling
- Use try-except with specific exception types
- Example from `src/galaxy_db_sync/application/kline/command.py`:
  ```python
  try:
      ...
  except Exception as e:
      logger.error(f"命令执行失败: {e}")
      import traceback
      traceback.print_exc()
      return 1
  ```

## Logging

### Framework

- **Standard library**: `logging` module
- **Logger naming**: `logging.getLogger(__name__)`

### Pattern

```python
# At module level
logger = logging.getLogger(__name__)

# Usage
logger.info(f"将获取 {len(valid_symbols)} 个证券的 K 线数据")
logger.warning(f"获取 {sec_type} 的代码列表时出错: {e}")
logger.error(f"命令执行失败: {e}")
```

### Log Levels

- `INFO`: Normal operation milestones, sync completion
- `WARNING`: Recoverable issues, fallback operations
- `ERROR`: Failures that stop operation
- `DEBUG`: Detailed flow (less common in production)

### Log Messages

- Include context values in f-strings
- Chinese language for user-facing logs
- English acceptable for technical debug logs

## Module Design

### Exports

- Use `__init__.py` to expose public interfaces
- Example from `src/galaxy_db_sync/shared_kernel/__init__.py`:
  ```python
  from .enums import Interval, SecurityType
  from .exceptions import GalaxyDBBridgeError, ValidationError
  ```

### Service Instances

- Create singleton service instances at module level
- Example from `src/galaxy_db_sync/database/services/kline.py`:
  ```python
  # Global service instance
  kline_service = KlineService()
  ```

### Class Organization

- Service classes: `class XxxService`
- Data classes: For structured results (e.g., `CompletenessResult`)
- Interface classes: For testable abstractions (e.g., `KlineDBInterface`)

## Function Design

### Size Guideline

- Functions should be focused on single responsibility
- Large functions acceptable for data transformation pipelines
- Break into helper functions when logic becomes complex

### Parameters

- Use type hints for all parameters
- Default values for optional parameters
- Example pattern:
  ```python
  def check(
      self,
      symbol: str,
      interval: Union[str, Interval],
      start_date: Union[str, date, datetime],
      end_date: Union[str, date, datetime],
  ) -> CompletenessResult:
  ```

### Return Values

- Return structured objects for complex results (data classes)
- Return primitives for simple operations
- Return `None` explicitly when no value to return

## Key Conventions Summary

| Aspect | Convention |
|--------|-----------|
| Language | Python 3.13 |
| Naming | snake_case (functions/vars), PascalCase (classes) |
| Line length | 100 characters |
| Type checking | mypy strict mode |
| Docstrings | Chinese, Args/Returns sections |
| Imports | isort order, absolute for cross-package |
| Exceptions | Hierarchical, inherit from `GalaxyDBBridgeError` |
| Logging | `logging.getLogger(__name__)`, Chinese messages |
| Services | Singleton instance pattern at module level |