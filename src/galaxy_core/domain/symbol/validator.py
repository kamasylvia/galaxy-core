"""证券代码验证纯函数.

从 shared_kernel/utils/symbol_validator.py 提取。
不依赖任何外部库（仅依赖 domain.value_objects.SecurityType）。
"""

import re
from galaxy_core.domain.value_objects import SecurityType


# 交易所代码前缀常量
SH_PREFIXES = {"50", "51", "52", "58", "60", "68", "90", "11", "12"}
SZ_PREFIXES = {"00", "03", "15", "16", "30"}
BJ_PREFIXES = {"920", "83", "87"}


def normalize_symbol(symbol: str) -> str:
    """标准化证券代码.

    - 6位数字自动补全后缀: 600000 -> 600000.SH, 000001 -> 000001.SZ
    - 已有后缀的直接返回: 600000.SH -> 600000.SH
    - 期货代码: IF2403 -> IF2403.FUTURE
    - 期权代码: 10003737 -> 10003737.OPTION
    - 其他格式保持不变
    """
    symbol = symbol.strip()

    # 如果已经有后缀，直接返回
    if "." in symbol:
        return symbol

    # 如果是6位纯数字，根据规则添加后缀
    if len(symbol) == 6 and symbol.isdigit():
        prefix = symbol[:2]
        if prefix in {"50", "51", "52", "58", "60", "68", "90", "11", "12"}:
            return f"{symbol}.SH"
        elif prefix in {"00", "03", "15", "16", "30"}:
            return f"{symbol}.SZ"
        elif symbol.startswith("920"):
            return f"{symbol}.BJ"

    # 如果是期货代码（字母+数字格式）
    if re.match(r"^[A-Za-z]+\d+$", symbol):
        return f"{symbol}.FUTURE"

    # 如果是期权代码（数字开头或其他格式）
    if re.match(r"^\d+[A-Za-z]*$", symbol):
        return f"{symbol}.OPTION"

    return symbol


def is_code_suffix_match(code: str, suffix: str) -> bool:
    """检查证券代码与后缀是否匹配.

    Args:
        code: 证券代码
        suffix: 后缀 (SH/SZ/BJ/FUTURE/OPTION 等)

    Returns:
        bool: 是否匹配
    """
    if not code or not suffix:
        return False

    # 对于6位数字的普通证券代码
    if len(code) == 6 and code.isdigit():
        prefix = code[:2]

        if suffix == "SH":
            return prefix in SH_PREFIXES
        elif suffix == "SZ":
            return prefix in SZ_PREFIXES
        elif suffix == "BJ":
            return code.startswith("920") or code.startswith("83") or code.startswith("87")
        else:
            return False

    # 对于期货代码
    elif suffix.upper() == "FUTURE":
        return bool(re.match(r"^[A-Za-z]+\d+$", code))

    # 对于期权代码
    elif suffix.upper() == "OPTION":
        return bool(re.match(r"^\d+$", code)) or bool(re.match(r"^\d+\.[A-Z]+$", code))

    else:
        return True

    return False


def validate_symbol_format(symbol: str) -> bool:
    """验证证券代码格式是否合法.

    合法格式包括:
    - 6位数字: "600000"
    - SecurityType: "SH_A", "SZ_ETF" 等
    - 6位数字带合法后缀: "600000.SH", "000001.SZ" 等
    - 期货代码带后缀: "IF2403.FUTURE", "CU2403.FUTURE" 等
    - 期权代码带后缀: "10003737.OPTION", "SR405.OPTION" 等

    Args:
        symbol: 证券代码

    Returns:
        bool: 格式是否合法
    """
    symbol = symbol.strip()

    # 检查是否是SecurityType
    security_type_names = {sec_type.name for sec_type in SecurityType}
    if symbol in security_type_names:
        return True

    # 检查是否是6位数字
    if len(symbol) == 6 and symbol.isdigit():
        return True

    # 检查是否是带后缀的形式
    if "." in symbol:
        parts = symbol.split(".")

        if len(parts) == 2:
            code_part, suffix_part = parts

            # 6位数字带合法后缀
            if len(code_part) == 6 and code_part.isdigit():
                valid_suffixes = {"SH", "SZ", "BJ"}
                if suffix_part.upper() in valid_suffixes:
                    return is_code_suffix_match(code_part, suffix_part.upper())

            # 期货或期权代码格式
            elif suffix_part.upper() in ["FUTURE", "OPTION"]:
                return is_code_suffix_match(code_part, suffix_part.upper())

        elif len(parts) >= 3:
            suffix_part = parts[-1]
            code_part = ".".join(parts[:-1])

            if suffix_part.upper() in ["FUTURE", "OPTION"]:
                return is_code_suffix_match(code_part, suffix_part.upper())

    return False
