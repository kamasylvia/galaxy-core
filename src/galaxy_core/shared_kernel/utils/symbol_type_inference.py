"""向后兼容 re-export — 证券类型推断已移至 domain.symbol.type_inference."""

from galaxy_core.domain.symbol.type_inference import (
    DS_FUTURE_PREFIXES,
    ETF_PREFIXES,
    SH_ETF_PREFIXES,
    SH_OPTION_PREFIXES,
    SN_FUTURE_PREFIXES,
    SQ_FUTURE_PREFIXES,
    SZ_ETF_PREFIXES,
    SZ_OPTION_PREFIXES,
    ZJ_FUTURE_PREFIXES,
    ZS_FUTURE_PREFIXES,
    filter_most_precise_security_types,
    get_all_possible_security_types,
    get_security_type_hierarchy,
    infer_security_type,
    is_etf_symbol,
)

__all__ = [
    "infer_security_type",
    "is_etf_symbol",
    "get_all_possible_security_types",
    "get_security_type_hierarchy",
    "filter_most_precise_security_types",
    "ZJ_FUTURE_PREFIXES",
    "SQ_FUTURE_PREFIXES",
    "DS_FUTURE_PREFIXES",
    "ZS_FUTURE_PREFIXES",
    "SN_FUTURE_PREFIXES",
    "ETF_PREFIXES",
    "SH_ETF_PREFIXES",
    "SZ_ETF_PREFIXES",
    "SH_OPTION_PREFIXES",
    "SZ_OPTION_PREFIXES",
]
