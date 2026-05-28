"""证券类型推断模块."""

from galaxy_db_sync.shared_kernel.enums.security_type import (
    SecurityType,
    SecurityTypeFuture,
    SecurityTypeOption,
)
from typing import List, Dict, Set, Optional


# 期货代码前缀常量
ZJ_FUTURE_PREFIXES = ("IF", "IC", "IM", "IH")  # 中金所股指期货
SQ_FUTURE_PREFIXES = (
    "CU", "AL", "ZN", "PB", "NI", "SN", "RB", "WR", "HC", "BU", "RU", "FU",
    "SC", "NR", "LU", "SS", "AO", "EB",
)  # 上期所
DS_FUTURE_PREFIXES = (
    "M", "Y", "A", "B", "P", "C", "CS", "JD", "FB", "LH", "RR", "PG", "PP",
    "V", "EB", "EG", "I", "J", "JM", "SG", "SM", "SP",
)  # 大商所
ZS_FUTURE_PREFIXES = (
    "CF", "CY", "SR", "TA", "MA", "FG", "SA", "UR", "AP", "CJ", "PK", "RI",
    "PM", "WH", "LR", "SF", "SH", "LC", "RO", "RS", "OI", "RM", "ZC", "QA",
    "JR", "SM",
)  # 郑商所
SN_FUTURE_PREFIXES = ("SC", "NR", "LU", "BC")  # 上海国际能源交易中心

# ETF 代码前缀常量
ETF_PREFIXES = {"50", "51", "15", "16", "58", "56", "52", "53", "55"}
SH_ETF_PREFIXES = {"50", "51", "58", "56", "52", "53", "55"}
SZ_ETF_PREFIXES = {"15", "16"}

# 期权代码前缀常量
SH_OPTION_PREFIXES = ("10", "11", "12", "13", "15", "16", "18", "51", "58")
SZ_OPTION_PREFIXES = ("00", "03", "04", "30", "39")


def infer_security_type(symbol: str) -> Optional[str]:
    """
    根据证券代码推断其类型

    Args:
        symbol: 证券代码，如 "600000.SH", "510050.SH", "IF2403.FUTURE" 等

    Returns:
        SecurityType 枚举值或 None（无法确定时）
    """
    symbol = symbol.strip()

    # 如果代码本身就是一个 SecurityType，则直接返回
    security_type_names = {sec_type.name for sec_type in SecurityType}
    security_type_future_names = {sec_type.name for sec_type in SecurityTypeFuture}
    security_type_option_names = {sec_type.name for sec_type in SecurityTypeOption}

    if symbol in security_type_names:
        return symbol
    elif symbol in security_type_future_names:
        return symbol
    elif symbol in security_type_option_names:
        return symbol

    # 分离代码和后缀
    if "." in symbol:
        code_part, suffix_part = symbol.rsplit(".", 1)

        # 处理6位数字代码
        if len(code_part) == 6 and code_part.isdigit():
            prefix = code_part[:2]

            # ETF 代码段
            if prefix in ETF_PREFIXES:
                if suffix_part.upper() == "SH":
                    return SecurityType.SH_ETF.value
                elif suffix_part.upper() == "SZ":
                    return SecurityType.SZ_ETF.value
                elif suffix_part.upper() == "BJ":
                    return SecurityType.BJ_A.value  # 北交所ETF实际上属于股票类别

            # 指数代码段（通常以000或399开头）
            elif code_part.startswith("000") or code_part.startswith("399"):
                if suffix_part.upper() == "SH":
                    return SecurityType.SH_INDEX.value
                elif suffix_part.upper() == "SZ":
                    return SecurityType.SZ_INDEX.value
                elif suffix_part.upper() == "BJ":
                    return SecurityType.BJ_INDEX.value

            # 可转债代码段
            elif prefix in {"11", "12"}:
                if suffix_part.upper() == "SH":
                    return SecurityType.SH_KZZ.value
                elif suffix_part.upper() == "SZ":
                    return SecurityType.SZ_KZZ.value
                elif suffix_part.upper() == "BJ":
                    return SecurityType.BJ_A.value  # 北交所可转债

            # 港股通代码段
            elif prefix in {"90"}:
                if suffix_part.upper() == "SH":
                    return SecurityType.SH_HKT.value
                elif suffix_part.upper() == "SZ":
                    return SecurityType.SZ_HKT.value

            # 逆回购代码段
            elif prefix in {"20", "131"}:
                if suffix_part.upper() == "SH":
                    return SecurityType.SH_GLRA.value  # 上海国债逆回购
                elif suffix_part.upper() == "SZ":
                    return SecurityType.SZ_GLRA.value  # 深圳国债逆回购

            # 股票代码段
            else:
                if suffix_part.upper() == "SH":
                    return SecurityType.SH_A.value
                elif suffix_part.upper() == "SZ":
                    return SecurityType.SZ_A.value
                elif suffix_part.upper() == "BJ":
                    return SecurityType.BJ_A.value

        # 处理期货代码
        elif suffix_part.upper() == "FUTURE":
            code_upper = code_part.upper()
            if code_upper.startswith(ZJ_FUTURE_PREFIXES):
                return SecurityTypeFuture.ZJ_FUTURE.value
            elif code_upper.startswith(SQ_FUTURE_PREFIXES):
                return SecurityTypeFuture.SQ_FUTURE.value
            elif code_upper.startswith(DS_FUTURE_PREFIXES):
                return SecurityTypeFuture.DS_FUTURE.value
            elif code_upper.startswith(ZS_FUTURE_PREFIXES):
                return SecurityTypeFuture.ZS_FUTURE.value
            elif code_upper.startswith(SN_FUTURE_PREFIXES):
                return SecurityTypeFuture.SN_FUTURE.value
            else:
                return SecurityTypeFuture.EXTRA_FUTURE.value

        # 处理期权代码
        elif suffix_part.upper() == "OPTION":
            if code_part.startswith(SH_OPTION_PREFIXES):
                return SecurityTypeOption.SH_OPTION.value
            elif code_part.startswith(SZ_OPTION_PREFIXES):
                return SecurityTypeOption.SZ_OPTION.value
            else:
                return SecurityTypeOption.EXTRA_ETF_OP.value

    # 对于没有后缀的6位数字代码，根据前缀推断
    elif len(symbol) == 6 and symbol.isdigit():
        prefix = symbol[:2]

        # ETF 代码段
        if prefix in {"50", "51", "15", "16", "58"}:
            return SecurityType.EXTRA_ETF.value

        # 指数代码段
        elif symbol.startswith("000") or symbol.startswith("399"):
            return SecurityType.EXTRA_INDEX_A_SH_SZ.value

        # 可转债代码段
        elif prefix in {"11", "12"}:
            return SecurityType.EXTRA_KZZ.value

        # 股票代码段
        else:
            return SecurityType.EXTRA_STOCK_A_SH_SZ.value

    return None


def get_all_possible_security_types(symbol: str) -> List[str]:
    """
    获取证券代码可能对应的所有 SecurityType 值（从最具体到最宽泛）

    Args:
        symbol: 证券代码，如 "600000.SH"

    Returns:
        SecurityType 值的列表，按具体程度排序
    """
    symbol = symbol.strip()

    # 分离代码和后缀
    if "." in symbol:
        code_part, suffix_part = symbol.rsplit(".", 1)

        # 处理期货代码
        if suffix_part.upper() == "FUTURE":
            code_upper = code_part.upper()
            if code_upper.startswith(ZJ_FUTURE_PREFIXES):
                return [
                    SecurityTypeFuture.ZJ_FUTURE.value,
                    SecurityTypeFuture.EXTRA_FUTURE.value,
                ]
            elif code_upper.startswith(SQ_FUTURE_PREFIXES):
                return [
                    SecurityTypeFuture.SQ_FUTURE.value,
                    SecurityTypeFuture.EXTRA_FUTURE.value,
                ]
            elif code_upper.startswith(DS_FUTURE_PREFIXES):
                return [
                    SecurityTypeFuture.DS_FUTURE.value,
                    SecurityTypeFuture.EXTRA_FUTURE.value,
                ]
            elif code_upper.startswith(ZS_FUTURE_PREFIXES):
                return [
                    SecurityTypeFuture.ZS_FUTURE.value,
                    SecurityTypeFuture.EXTRA_FUTURE.value,
                ]
            elif code_upper.startswith(SN_FUTURE_PREFIXES):
                return [
                    SecurityTypeFuture.SN_FUTURE.value,
                    SecurityTypeFuture.EXTRA_FUTURE.value,
                ]
            else:
                return [SecurityTypeFuture.EXTRA_FUTURE.value]

        # 处理期权代码
        elif suffix_part.upper() == "OPTION":
            if code_part.startswith(SH_OPTION_PREFIXES):
                return [
                    SecurityTypeOption.SH_OPTION.value,
                    SecurityTypeOption.EXTRA_ETF_OP.value,
                ]
            elif code_part.startswith(SZ_OPTION_PREFIXES):
                return [
                    SecurityTypeOption.SZ_OPTION.value,
                    SecurityTypeOption.EXTRA_ETF_OP.value,
                ]
            else:
                return [SecurityTypeOption.EXTRA_ETF_OP.value]

        elif len(code_part) == 6 and code_part.isdigit():
            prefix = code_part[:2]

            # ETF 代码段
            if prefix in {"50", "51", "15", "16", "58", "56", "52"}:
                if suffix_part.upper() == "SH":
                    return [SecurityType.SH_ETF.value, SecurityType.EXTRA_ETF.value]
                elif suffix_part.upper() == "SZ":
                    return [SecurityType.SZ_ETF.value, SecurityType.EXTRA_ETF.value]
                elif suffix_part.upper() == "BJ":
                    return [
                        SecurityType.BJ_A.value,
                        SecurityType.EXTRA_STOCK_A.value,
                    ]

            # 指数代码段
            elif code_part.startswith("000") or code_part.startswith("399"):
                if suffix_part.upper() == "SH":
                    return [
                        SecurityType.SH_INDEX.value,
                        SecurityType.EXTRA_INDEX_A_SH_SZ.value,
                        SecurityType.EXTRA_INDEX_A.value,
                    ]
                elif suffix_part.upper() == "SZ":
                    return [
                        SecurityType.SZ_INDEX.value,
                        SecurityType.EXTRA_INDEX_A_SH_SZ.value,
                        SecurityType.EXTRA_INDEX_A.value,
                    ]
                elif suffix_part.upper() == "BJ":
                    return [
                        SecurityType.BJ_INDEX.value,
                        SecurityType.EXTRA_INDEX_A.value,
                    ]

            # 可转债代码段
            elif prefix in {"11", "12"}:
                if suffix_part.upper() == "SH":
                    return [SecurityType.SH_KZZ.value, SecurityType.EXTRA_KZZ.value]
                elif suffix_part.upper() == "SZ":
                    return [SecurityType.SZ_KZZ.value, SecurityType.EXTRA_KZZ.value]
                elif suffix_part.upper() == "BJ":
                    return [
                        SecurityType.BJ_A.value,
                        SecurityType.EXTRA_STOCK_A.value,
                    ]

            # 港股通代码段
            elif prefix in {"90"}:
                if suffix_part.upper() == "SH":
                    return [SecurityType.SH_HKT.value, SecurityType.EXTRA_HKT.value]
                elif suffix_part.upper() == "SZ":
                    return [SecurityType.SZ_HKT.value, SecurityType.EXTRA_HKT.value]

            # 逆回购代码段
            elif prefix in {"20", "131"}:
                if suffix_part.upper() == "SH":
                    return [
                        SecurityType.SH_GLRA.value,
                        SecurityType.EXTRA_GLRA.value,
                    ]
                elif suffix_part.upper() == "SZ":
                    return [
                        SecurityType.SZ_GLRA.value,
                        SecurityType.EXTRA_GLRA.value,
                    ]

            # 股票代码段
            else:
                if suffix_part.upper() == "SH":
                    return [
                        SecurityType.SH_A.value,
                        SecurityType.EXTRA_STOCK_A_SH_SZ.value,
                        SecurityType.EXTRA_STOCK_A.value,
                    ]
                elif suffix_part.upper() == "SZ":
                    return [
                        SecurityType.SZ_A.value,
                        SecurityType.EXTRA_STOCK_A_SH_SZ.value,
                        SecurityType.EXTRA_STOCK_A.value,
                    ]
                elif suffix_part.upper() == "BJ":
                    return [SecurityType.BJ_A.value, SecurityType.EXTRA_STOCK_A.value]

    # 对于没有后缀的6位数字代码
    elif len(symbol) == 6 and symbol.isdigit():
        prefix = symbol[:2]

        if prefix in {"50", "51", "15", "16", "58"}:
            return [SecurityType.EXTRA_ETF.value]
        elif symbol.startswith("000") or symbol.startswith("399"):
            return [
                SecurityType.EXTRA_INDEX_A_SH_SZ.value,
                SecurityType.EXTRA_INDEX_A.value,
            ]
        elif prefix in {"11", "12"}:
            return [SecurityType.EXTRA_KZZ.value]
        else:
            return [
                SecurityType.EXTRA_STOCK_A_SH_SZ.value,
                SecurityType.EXTRA_STOCK_A.value,
            ]

    return []


def get_security_type_hierarchy() -> Dict[str, Set[str]]:
    """
    定义 SecurityType 的层级关系。

    返回一个字典，其中 key 是父类型，value 是子类型的集合。
    """
    hierarchy = {
        # A股层级
        "EXTRA_STOCK_A": {
            "EXTRA_STOCK_A_SH_SZ",
            "BJ_A",
        },
        "EXTRA_STOCK_A_SH_SZ": {"SH_A", "SZ_A"},
        # 指数层级
        "EXTRA_INDEX_A": {
            "EXTRA_INDEX_A_SH_SZ",
            "BJ_INDEX",
        },
        "EXTRA_INDEX_A_SH_SZ": {"SH_INDEX", "SZ_INDEX"},
        # ETF层级
        "EXTRA_ETF": {"SH_ETF", "SZ_ETF"},
        # 可转债层级
        "EXTRA_KZZ": {"SH_KZZ", "SZ_KZZ"},
        # 港股通层级
        "EXTRA_HKT": {"SH_HKT", "SZ_HKT"},
        # 逆回购层级
        "EXTRA_GLRA": {"SH_GLRA", "SZ_GLRA"},
        # 期货层级
        "EXTRA_FUTURE": {
            "ZJ_FUTURE",
            "SQ_FUTURE",
            "DS_FUTURE",
            "ZS_FUTURE",
            "SN_FUTURE",
        },
        # 期权层级
        "EXTRA_ETF_OP": {"SH_OPTION", "SZ_OPTION"},
    }
    return hierarchy


def filter_most_precise_security_types(security_types: List[str]) -> List[str]:
    """
    从 SecurityType 列表中过滤出最精确的类型，避免重复API调用。

    例如：
    - 如果同时有 EXTRA_STOCK_A 和 EXTRA_STOCK_A_SH_SZ，则只保留 EXTRA_STOCK_A
    - 如果同时有 SH_A 和 SZ_A，则保留两者（它们是并列关系）

    Args:
        security_types: SecurityType 列表

    Returns:
        List[str]: 过滤后的最精确 SecurityType 列表
    """
    if not security_types:
        return []

    hierarchy = get_security_type_hierarchy()

    # 构建反向映射：子类型 -> 父类型
    child_to_parent = {}
    for parent, children in hierarchy.items():
        for child in children:
            child_to_parent[child] = parent

    input_set = set(security_types)
    result = []

    for sec_type in security_types:
        current = sec_type
        is_descendant_of_any_input = False

        while current in child_to_parent:
            parent = child_to_parent[current]
            if parent in input_set:
                is_descendant_of_any_input = True
                break
            current = parent

        if not is_descendant_of_any_input:
            result.append(sec_type)

    return result