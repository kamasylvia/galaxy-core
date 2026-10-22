"""证券输入解析纯函数.

从 shared_kernel/utils/symbol_input_resolver.py 提取 parse_symbols。
不依赖任何外部库（仅依赖 domain.value_objects 和 domain.symbol.validator）。
"""

from galaxy_core.domain.value_objects import SecurityType
from galaxy_core.domain.symbol.validator import (
    validate_symbol_format,
    normalize_symbol,
)


def parse_symbols(value: str | list[str]) -> list[tuple[str, str]]:
    """解析 symbols 参数.

    支持格式:
    - 单代码: "600000.SH" 或 "600000" (自动补全后缀)
    - 列表: "[600000.SH, 000001.SZ]" 或 "600000,000001"
    - SecurityType: "SH_A", "SZ_ETF" 等
    - 混合列表: "[600000, SH_ETF]" (代码和SecurityType混合)
    """
    if isinstance(value, list):
        value = ",".join(value)
    value = value.strip()

    # 检查是否是列表格式 [symbol1, symbol2, ...]
    if value.startswith("[") and value.endswith("]"):
        content = value[1:-1].strip()
        if not content:
            return []
        items = [s.strip() for s in content.split(",") if s.strip()]
    else:
        items = [s.strip() for s in value.split(",") if s.strip()]

    # 验证每个项目的格式
    for item in items:
        if not validate_symbol_format(item):
            raise ValueError(
                f"无效的证券代码格式: {item}。支持的格式：6位数字、SecurityType、"
                "6位数字带合法后缀(.SH/.SZ/.BJ)、期货代码带.FUTURE后缀或期权代码带.OPTION后缀"
            )

    # 检查是否包含 SecurityType
    security_type_names = {sec_type.name for sec_type in SecurityType}

    result: list[tuple[str, str]] = []
    for item in items:
        if item in security_type_names:
            result.append(("security_type", item))
        else:
            normalized = normalize_symbol(item)
            result.append(("symbol", normalized))

    return result
