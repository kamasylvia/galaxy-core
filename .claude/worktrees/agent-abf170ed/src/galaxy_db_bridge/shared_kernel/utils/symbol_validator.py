"""证券代码验证工具."""

from galaxy_db_bridge.shared_kernel.enums.security_type import (
    SecurityType,
    SecurityTypeFuture,
    SecurityTypeOption,
)
import logging
from typing import List, Dict, Set, Tuple, Optional


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
            # 51: 上交所ETF (510-519开头，如510050上证50ETF)
            # 15: 深交所ETF (159开头，如159919沪深300ETF)
            # 16: 深交所ETF (16xx开头的一些ETF)
            # 58: 科创板ETF (588开头，如588670科创50ETF)
            # 50: 上交所ETF及LOF基金 (50xxxx系列)
            # 56: 上交所ETF (56xxxx开头，如563020上证300ETF)
            # 52: 上交所ETF (52xxxx开头，如520990等商品ETF)
            # 53: 上交所基金 (53xxxx开头，包含ETF和LOF基金)
            # 55: 上交所基金 (55xxxx开头，包含ETF和LOF基金)
            if prefix in {"50", "51", "15", "16", "58", "56", "52", "53", "55"}:
                if suffix_part.upper() == "SH":
                    if prefix in {"50", "51", "58", "56", "52", "53", "55"}:
                        return SecurityType.SH_ETF.value
                    else:
                        return SecurityType.SH_ETF.value
                elif suffix_part.upper() == "SZ":
                    if prefix in {"15", "16"}:
                        return SecurityType.SZ_ETF.value
                    else:
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
            elif prefix in {
                "20",
                "131",
            }:  # 204xxx 上交所国债回购, 1318xx 深交所国债回购
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
            # 期货代码通常为字母+数字，如 IF2403, cu2403
            # 根据代码前缀进一步细化期货类型
            if code_part.upper().startswith(("IF", "IC", "IM", "IH")):  # 中金所股指期货
                return SecurityTypeFuture.ZJ_FUTURE.value
            elif code_part.upper().startswith(
                (
                    "CU",
                    "AL",
                    "ZN",
                    "PB",
                    "NI",
                    "SN",
                    "RB",
                    "WR",
                    "HC",
                    "BU",
                    "RU",
                    "FU",
                    "SC",
                    "NR",
                    "LU",
                    "SS",
                    "AO",
                    "EB",
                )
            ):  # 上期所
                return SecurityTypeFuture.SQ_FUTURE.value
            elif code_part.upper().startswith(
                (
                    "M",
                    "Y",
                    "A",
                    "B",
                    "P",
                    "C",
                    "CS",
                    "JD",
                    "FB",
                    "LH",
                    "RR",
                    "PG",
                    "PP",
                    "V",
                    "EB",
                    "EG",
                    "I",
                    "J",
                    "JM",
                    "SG",
                    "SM",
                    "SP",
                )
            ):  # 大商所
                return SecurityTypeFuture.DS_FUTURE.value
            elif code_part.upper().startswith(
                (
                    "CF",
                    "CY",
                    "SR",
                    "TA",
                    "MA",
                    "FG",
                    "SA",
                    "UR",
                    "AP",
                    "CJ",
                    "PK",
                    "RI",
                    "PM",
                    "WH",
                    "LR",
                    "SF",
                    "SH",
                    "LC",
                    "RO",
                    "RS",
                    "OI",
                    "RM",
                    "ZC",
                    "QA",
                    "JR",
                    "LR",
                    "SF",
                    "SM",
                )
            ):  # 郑商所
                return SecurityTypeFuture.ZS_FUTURE.value
            elif code_part.upper().startswith(
                ("SC", "NR", "LU", "BC")
            ):  # 上海国际能源交易中心
                return SecurityTypeFuture.SN_FUTURE.value
            else:
                return SecurityTypeFuture.EXTRA_FUTURE.value

        # 处理期权代码
        elif suffix_part.upper() == "OPTION":
            # 期权代码通常为数字，如 10003737
            # 根据代码前缀进一步细化期权类型
            # 上海证券交易所期权代码通常以10、11、12、13、15、16、18、51、58开头
            # 深圳证券交易所期权代码通常以00、03、04、30、39开头
            if code_part.startswith(
                ("10", "11", "12", "13", "15", "16", "18", "51", "58")
            ):
                return SecurityTypeOption.SH_OPTION.value  # 上交所期权
            elif code_part.startswith(("00", "03", "04", "30", "39")):
                return SecurityTypeOption.SZ_OPTION.value  # 深交所期权
            else:
                return SecurityTypeOption.EXTRA_ETF_OP.value  # 其他期权

    # 对于没有后缀的6位数字代码，根据前缀推断
    elif len(symbol) == 6 and symbol.isdigit():
        prefix = symbol[:2]

        # ETF 代码段
        # 50: 上交所ETF及LOF基金 (50xxxx系列)
        # 51: 上交所ETF (510-519开头，如510050上证50ETF)
        # 15: 深交所ETF (159开头，如159919沪深300ETF)
        # 16: 深交所ETF (16xx开头的一些ETF)
        # 58: 科创板ETF (588开头，如588670科创50ETF)
        if prefix in {"50", "51", "15", "16", "58"}:
            return SecurityType.EXTRA_ETF.value  # 需要额外API调用才能确定具体交易所

        # 指数代码段
        elif symbol.startswith("000") or symbol.startswith("399"):
            return (
                SecurityType.EXTRA_INDEX_A_SH_SZ.value
            )  # 需要额外API调用才能确定具体交易所

        # 可转债代码段
        elif prefix in {"11", "12"}:
            return SecurityType.EXTRA_KZZ.value  # 需要额外API调用才能确定具体交易所

        # 股票代码段
        else:
            return (
                SecurityType.EXTRA_STOCK_A_SH_SZ.value
            )  # 需要额外API调用才能确定具体交易所

    # 如果无法推断，返回 None
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
            # 期货代码通常为字母+数字，如 IF2403, cu2403
            # 根据代码前缀进一步细化期货类型
            if code_part.upper().startswith(("IF", "IC", "IM", "IH")):  # 中金所股指期货
                return [
                    SecurityTypeFuture.ZJ_FUTURE.value,
                    SecurityTypeFuture.EXTRA_FUTURE.value,
                ]
            elif code_part.upper().startswith(
                (
                    "CU",
                    "AL",
                    "ZN",
                    "PB",
                    "NI",
                    "SN",
                    "RB",
                    "WR",
                    "HC",
                    "BU",
                    "RU",
                    "FU",
                    "SC",
                    "NR",
                    "LU",
                    "SS",
                    "AO",
                    "EB",
                )
            ):  # 上期所
                return [
                    SecurityTypeFuture.SQ_FUTURE.value,
                    SecurityTypeFuture.EXTRA_FUTURE.value,
                ]
            elif code_part.upper().startswith(
                (
                    "M",
                    "Y",
                    "A",
                    "B",
                    "P",
                    "C",
                    "CS",
                    "JD",
                    "FB",
                    "LH",
                    "RR",
                    "PG",
                    "PP",
                    "V",
                    "EB",
                    "EG",
                    "I",
                    "J",
                    "JM",
                    "SG",
                    "SM",
                    "SP",
                )
            ):  # 大商所
                return [
                    SecurityTypeFuture.DS_FUTURE.value,
                    SecurityTypeFuture.EXTRA_FUTURE.value,
                ]
            elif code_part.upper().startswith(
                (
                    "CF",
                    "CY",
                    "SR",
                    "TA",
                    "MA",
                    "FG",
                    "SA",
                    "UR",
                    "AP",
                    "CJ",
                    "PK",
                    "RI",
                    "PM",
                    "WH",
                    "LR",
                    "SF",
                    "SH",
                    "LC",
                    "RO",
                    "RS",
                    "OI",
                    "RM",
                    "ZC",
                    "QA",
                    "JR",
                    "LR",
                    "SF",
                    "SM",
                )
            ):  # 郑商所
                return [
                    SecurityTypeFuture.ZS_FUTURE.value,
                    SecurityTypeFuture.EXTRA_FUTURE.value,
                ]
            elif code_part.upper().startswith(
                ("SC", "NR", "LU", "BC")
            ):  # 上海国际能源交易中心
                return [
                    SecurityTypeFuture.SN_FUTURE.value,
                    SecurityTypeFuture.EXTRA_FUTURE.value,
                ]
            else:
                return [SecurityTypeFuture.EXTRA_FUTURE.value]

        # 处理期权代码
        elif suffix_part.upper() == "OPTION":
            # 期权代码通常为数字，如 10003737
            # 根据代码前缀进一步细化期权类型
            if code_part.startswith(
                ("10", "11", "12", "13", "15", "16", "18", "51", "58")
            ):
                return [
                    SecurityTypeOption.SH_OPTION.value,
                    SecurityTypeOption.EXTRA_ETF_OP.value,
                ]  # 上交所期权
            elif code_part.startswith(("00", "03", "04", "30", "39")):
                return [
                    SecurityTypeOption.SZ_OPTION.value,
                    SecurityTypeOption.EXTRA_ETF_OP.value,
                ]  # 深交所期权
            else:
                return [SecurityTypeOption.EXTRA_ETF_OP.value]  # 其他期权

        elif len(code_part) == 6 and code_part.isdigit():
            prefix = code_part[:2]

            # ETF 代码段
            # 51: 上交所ETF (510-519开头，如510050上证50ETF)
            # 15: 深交所ETF (159开头，如159919沪深300ETF)
            # 16: 深交所ETF (16xx开头的一些ETF)
            # 58: 科创板ETF (588开头，如588670科创50ETF)
            # 50: 上交所ETF及LOF基金 (50xxxx系列)
            # 56: 上交所ETF (56xxxx开头，如563020上证300ETF)
            # 52: 上交所ETF (52xxxx开头，如520990等商品ETF)
            if prefix in {"50", "51", "15", "16", "58", "56", "52"}:
                if suffix_part.upper() == "SH":
                    if prefix in {"50", "51", "58", "56", "52"}:
                        return [SecurityType.SH_ETF.value, SecurityType.EXTRA_ETF.value]
                    else:
                        return [SecurityType.SH_ETF.value, SecurityType.EXTRA_ETF.value]
                elif suffix_part.upper() == "SZ":
                    if prefix in {"15", "16"}:
                        return [SecurityType.SZ_ETF.value, SecurityType.EXTRA_ETF.value]
                    else:
                        return [SecurityType.SZ_ETF.value, SecurityType.EXTRA_ETF.value]
                elif suffix_part.upper() == "BJ":
                    return [
                        SecurityType.BJ_A.value,
                        SecurityType.EXTRA_STOCK_A.value,
                    ]  # 北交所ETF

            # 指数代码段（通常以000或399开头）
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
                    ]  # 北交所可转债

            # 港股通代码段
            elif prefix in {"90"}:
                if suffix_part.upper() == "SH":
                    return [SecurityType.SH_HKT.value, SecurityType.EXTRA_HKT.value]
                elif suffix_part.upper() == "SZ":
                    return [SecurityType.SZ_HKT.value, SecurityType.EXTRA_HKT.value]

            # 逆回购代码段
            elif prefix in {
                "20",
                "131",
            }:  # 204xxx 上交所国债回购, 1318xx 深交所国债回购
                if suffix_part.upper() == "SH":
                    return [
                        SecurityType.SH_GLRA.value,
                        SecurityType.EXTRA_GLRA.value,
                    ]  # 上海国债逆回购
                elif suffix_part.upper() == "SZ":
                    return [
                        SecurityType.SZ_GLRA.value,
                        SecurityType.EXTRA_GLRA.value,
                    ]  # 深圳国债逆回购

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

    # 对于没有后缀的6位数字代码，返回最宽泛的类型
    elif len(symbol) == 6 and symbol.isdigit():
        prefix = symbol[:2]

        # ETF 代码段
        # 50: 上交所ETF及LOF基金 (50xxxx系列)
        # 51: 上交所ETF (510-519开头，如510050上证50ETF)
        # 15: 深交所ETF (159开头，如159919沪深300ETF)
        # 16: 深交所ETF (16xx开头的一些ETF)
        # 58: 科创板ETF (588开头，如588670科创50ETF)
        if prefix in {"50", "51", "15", "16", "58"}:
            return [SecurityType.EXTRA_ETF.value]

        # 指数代码段
        elif symbol.startswith("000") or symbol.startswith("399"):
            return [
                SecurityType.EXTRA_INDEX_A_SH_SZ.value,
                SecurityType.EXTRA_INDEX_A.value,
            ]

        # 可转债代码段
        elif prefix in {"11", "12"}:
            return [SecurityType.EXTRA_KZZ.value]

        # 股票代码段
        else:
            return [
                SecurityType.EXTRA_STOCK_A_SH_SZ.value,
                SecurityType.EXTRA_STOCK_A.value,
            ]

    # 如果无法推断，返回空列表
    return []


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
        # 按代码段智能推断交易所（无需用户指定）
        if symbol.startswith(("50", "51", "52", "58", "60", "68", "90", "11", "12")):
            if symbol.startswith(("50", "51", "58")):
                return f"{symbol}.SH"  # ETF代码（50/51/58开头）属于上交所
            else:
                return f"{symbol}.SH"  # 沪市：含可转债(11/12)、股票(60/68)
        elif symbol.startswith(("00", "03", "15", "16", "30")):
            return f"{symbol}.SZ"  # 深市：含ETF(15)、可转债(12*)、股票(00/30)
        elif symbol.startswith("920"):
            return f"{symbol}.BJ"  # 北交所

    # 如果是期货代码（字母+数字格式）
    import re

    if re.match(r"^[A-Za-z]+\d+$", symbol):
        # 检查是否是期货代码格式
        return f"{symbol}.FUTURE"

    # 如果是期权代码（数字开头或其他格式）
    if re.match(r"^\d+[A-Za-z]*$", symbol):
        # 检查是否是期权代码格式
        return f"{symbol}.OPTION"

    # 不符合以上规则的代码保持原样
    return symbol


def parse_symbols(value: str) -> list[tuple[str, str]]:
    """解析 symbols 参数.

    支持格式:
    - 单代码: "600000.SH" 或 "600000" (自动补全后缀)
    - 列表: "[600000.SH, 000001.SZ]" 或 "600000,000001"
    - SecurityType: "SH_A", "SZ_ETF" 等
    - 混合列表: "[600000, SH_ETF]" (代码和SecurityType混合)
    """
    value = value.strip()

    # 检查是否是列表格式 [symbol1, symbol2, ...]
    if value.startswith("[") and value.endswith("]"):
        content = value[1:-1].strip()
        if not content:
            return []
        # 分割并清理每个元素
        items = [s.strip() for s in content.split(",") if s.strip()]
    else:
        # 尝试按逗号分割
        items = [s.strip() for s in value.split(",") if s.strip()]

    # 验证每个项目的格式
    for item in items:
        if not validate_symbol_format(item):
            raise ValueError(
                f"无效的证券代码格式: {item}。支持的格式：6位数字、SecurityType、6位数字带合法后缀(.SH/.SZ/.BJ)、期货代码带.FUTURE后缀或期权代码带.OPTION后缀"
            )

    # 检查是否包含 SecurityType
    security_type_names = {sec_type.name for sec_type in SecurityType}

    result: list[tuple[str, str]] = []
    for item in items:
        if item in security_type_names:
            # 是 SecurityType，获取该类型的所有代码
            result.append(("security_type", item))
        else:
            # 是普通代码，标准化处理（自动补全后缀）
            normalized = normalize_symbol(item)
            result.append(("symbol", normalized))

    return result


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

        # 上海证券交易所代码段
        sh_prefixes = {"50", "51", "52", "58", "60", "68", "90", "11", "12"}
        # 深圳证券交易所代码段
        sz_prefixes = {"00", "03", "15", "16", "30"}
        # 北京证券交易所代码段
        bj_prefixes = {"920", "83", "87"}  # 920, 83, 87开头是北交所

        if suffix == "SH":
            return prefix in sh_prefixes
        elif suffix == "SZ":
            return prefix in sz_prefixes
        elif suffix == "BJ":
            return (
                code.startswith("920") or code.startswith("83") or code.startswith("87")
            )
        else:
            # 其他后缀（如FUTURE, OPTION）不适用于6位数字代码
            return False

    # 对于期货代码（通常为字母+数字格式，如IF2403, CU2403等）
    elif suffix.upper() == "FUTURE":
        # 期货代码通常格式为字母+数字，例如：IF2403, cu2403, SR405等
        # 至少1个字母开头，后面跟数字
        import re

        future_pattern = r"^[A-Za-z]+\d+$"
        return bool(re.match(future_pattern, code))

    # 对于期权代码（通常为数字格式，如10003737或10003737.CZC等）
    elif suffix.upper() == "OPTION":
        # 期权代码格式可能多样化，这里提供基础支持
        # 主要是数字开头（如10003737）或包含交易所后缀的格式（如10003737.CZC）
        import re

        # 数字开头的期权代码
        option_numeric_pattern = r"^\d+$"
        # 包含交易所后缀的格式（如10003737.CZC）
        option_with_exchange_pattern = r"^\d+\.[A-Z]+$"
        return bool(re.match(option_numeric_pattern, code)) or bool(
            re.match(option_with_exchange_pattern, code)
        )

    # 其他特殊后缀的处理
    else:
        # 默认返回True，允许自定义后缀格式
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

        # 如果只有两部分，按原有逻辑处理
        if len(parts) == 2:
            code_part, suffix_part = parts

            # 检查是否是6位数字带合法后缀的形式
            if len(code_part) == 6 and code_part.isdigit():
                # 检查后缀是否合法
                valid_suffixes = {"SH", "SZ", "BJ"}
                if suffix_part.upper() in valid_suffixes:
                    # 检查数字与后缀是否匹配
                    return is_code_suffix_match(code_part, suffix_part.upper())

            # 检查是否是期货或期权代码格式
            elif suffix_part.upper() in ["FUTURE", "OPTION"]:
                # 检查代码部分是否符合相应格式
                return is_code_suffix_match(code_part, suffix_part.upper())

        # 如果有多于两部分，处理复杂格式（如 "10003737.CZC.OPTION"）
        elif len(parts) >= 3:
            # 检查是否是以期货或期权结尾的格式
            suffix_part = parts[-1]  # 最后一部分作为后缀
            code_part = ".".join(parts[:-1])  # 其余部分作为代码

            if suffix_part.upper() in ["FUTURE", "OPTION"]:
                # 检查代码部分是否符合相应格式
                return is_code_suffix_match(code_part, suffix_part.upper())

    return False


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
        },  # EXTRA_STOCK_A 包含沪深和北交所
        "EXTRA_STOCK_A_SH_SZ": {"SH_A", "SZ_A"},  # 沪深A股包含上海和深圳
        # 指数层级
        "EXTRA_INDEX_A": {
            "EXTRA_INDEX_A_SH_SZ",
            "BJ_INDEX",
        },  # 沪深北指数包含沪深和北交所
        "EXTRA_INDEX_A_SH_SZ": {"SH_INDEX", "SZ_INDEX"},  # 沪深指数包含上海和深圳
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

    # 构建层级关系图
    hierarchy = get_security_type_hierarchy()

    # 构建反向映射：子类型 -> 父类型
    child_to_parent = {}
    for parent, children in hierarchy.items():
        for child in children:
            child_to_parent[child] = parent

    # 转换为集合以加快查找速度
    input_set = set(security_types)

    # 找出需要保留的类型：那些没有父类型在输入列表中的类型
    result = []
    for sec_type in security_types:
        # 检查当前类型的所有祖先类型是否在输入列表中
        current = sec_type
        is_descendant_of_any_input = False

        # 向上遍历直到根节点
        while current in child_to_parent:
            parent = child_to_parent[current]
            if parent in input_set:
                is_descendant_of_any_input = True
                break
            current = parent

        # 如果当前类型不是任何输入类型（在输入列表中的类型）的后代，则保留它
        if not is_descendant_of_any_input:
            result.append(sec_type)

    return result


# 将API调用相关的函数移到单独的部分，避免循环导入
def get_valid_symbols_from_input(
    input_list: List[str], start_date: str = "20200101", end_date: str = "20301231"
) -> List[str]:
    """
    从输入列表获取有效的证券代码列表。

    对于 SecurityType 的入参，先过滤出最精确的 SecurityType 以减少 API 调用，
    然后传入 get_hist_code_list 获得代码列表。
    对于非 SecurityType 的代码，进行初筛。

    Args:
        input_list: 输入的证券代码列表，可能包含 SecurityType 或普通代码
        start_date: 开始日期，用于获取 SecurityType 的历史代码列表
        end_date: 结束日期，用于获取 SecurityType 的历史代码列表

    Returns:
        List[str]: 有效的证券代码列表
    """
    security_type_names = {sec_type.name for sec_type in SecurityType}

    security_types = []
    normal_symbols = []

    # 分离 SecurityType 和普通代码
    for item in input_list:
        if item in security_type_names:
            security_types.append(item)
        else:
            # 对普通代码进行格式校验（初筛）
            if validate_symbol_format(item):
                normalized = normalize_symbol(item)
                normal_symbols.append(normalized)

    # 对 SecurityType 进行层级检测，选出最精确的类型
    precise_security_types = filter_most_precise_security_types(security_types)

    # 获取 SecurityType 对应的代码列表（这部分需要在使用时动态导入，避免循环导入）
    security_type_codes = []
    if precise_security_types:
        # 动态导入，避免循环导入
        from galaxy_db_bridge.amazing_data.api.client import amazing_data_client

        # 从配置获取 local_path
        from galaxy_db_bridge.shared_kernel.utils.config_loader import get_section

        amazing_data_config = get_section("amazing_data")
        local_path = amazing_data_config.get("local_path", "./cache")

        # 导入 datetime 模块用于处理日期
        from datetime import datetime

        for sec_type in precise_security_types:
            try:
                # 转换日期格式为整数，处理 None 值
                # 需要根据周期类型来正确处理日期
                from galaxy_db_bridge.shared_kernel.utils.time_parser import (
                    convert_date_string_to_int,
                )

                # 假设我们不知道确切的周期类型，使用默认的月线处理方式
                # 对于获取历史代码列表，我们希望获取整个时间段的代码，所以使用月度周期来处理
                start_int = (
                    convert_date_string_to_int(start_date, "month", is_end_date=False)
                    if start_date
                    else 20200101
                )  # 默认开始日期
                end_int = (
                    convert_date_string_to_int(end_date, "month", is_end_date=True)
                    if end_date
                    else int(datetime.now().strftime("%Y%m%d"))
                )  # 使用当前日期作为默认结束日期

                # 获取历史代码列表
                codes = amazing_data_client.get_hist_code_list(
                    security_type=sec_type,
                    start_date=start_int,
                    end_date=end_int,
                    local_path=local_path,  # 从配置获取 local_path
                )
                security_type_codes.extend(codes)
                logging.info(f"通过 {sec_type} 获取到 {len(codes)} 个代码")
            except Exception as e:
                logging.warning(f"获取 {sec_type} 的代码列表时出错: {e}")

    # 合并所有代码列表并去重
    all_codes = list(set(normal_symbols + security_type_codes))

    return all_codes
