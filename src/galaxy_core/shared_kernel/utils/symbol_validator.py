"""向后兼容 re-export — symbol 验证已移至 domain.symbol.validator."""

from galaxy_core.domain.symbol.validator import (
    normalize_symbol,
    is_code_suffix_match,
    validate_symbol_format,
    SH_PREFIXES,
    SZ_PREFIXES,
    BJ_PREFIXES,
)

__all__ = [
    "normalize_symbol",
    "is_code_suffix_match",
    "validate_symbol_format",
    "SH_PREFIXES",
    "SZ_PREFIXES",
    "BJ_PREFIXES",
]
