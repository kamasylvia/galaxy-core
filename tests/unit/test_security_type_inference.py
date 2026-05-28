#!/usr/bin/env python3
"""
测试security_type推断函数
"""


def infer_security_type_simple(symbol: str) -> str:
    """
    简化版证券代码类型推断函数，不依赖复杂导入
    """
    symbol = symbol.strip()

    # 分离代码和后缀
    if "." in symbol:
        code_part, suffix_part = symbol.rsplit(".", 1)

        # 处理6位数字代码
        if len(code_part) == 6 and code_part.isdigit():
            prefix = code_part[:2]

            # ETF 代码段
            if prefix in {"50", "51", "52", "56", "15", "16", "58"}:
                if suffix_part.upper() == "SH":
                    if prefix in {"50", "51", "58"}:
                        return "SH_ETF"
                    else:
                        return "SH_ETF"
                elif suffix_part.upper() == "SZ":
                    if prefix in {"15", "16"}:
                        return "SZ_ETF"
                    else:
                        return "SZ_ETF"
                elif suffix_part.upper() == "BJ":
                    return "BJ_A"  # 北交所ETF实际上属于股票类别

            # 指数代码段（通常以000或399开头）
            elif code_part.startswith("000") or code_part.startswith("399"):
                if suffix_part.upper() == "SH":
                    return "SH_INDEX"
                elif suffix_part.upper() == "SZ":
                    return "SZ_INDEX"
                elif suffix_part.upper() == "BJ":
                    return "BJ_INDEX"

            # 可转债代码段
            elif prefix in {"11", "12"}:
                if suffix_part.upper() == "SH":
                    return "SH_KZZ"
                elif suffix_part.upper() == "SZ":
                    return "SZ_KZZ"
                elif suffix_part.upper() == "BJ":
                    return "BJ_A"  # 北交所可转债

            # 港股通代码段（暂时简化处理）
            elif code_part.startswith("90"):
                if suffix_part.upper() == "SH":
                    return "SH_HKT"
                elif suffix_part.upper() == "SZ":
                    return "SZ_HKT"

            # 股票代码段
            else:
                if suffix_part.upper() == "SH":
                    return "SH_A"
                elif suffix_part.upper() == "SZ":
                    return "SZ_A"
                elif suffix_part.upper() == "BJ":
                    return "BJ_A"

        # 处理期货代码
        elif suffix_part.upper() == "FUTURE":
            # 期货代码通常为字母+数字，如 IF2403, cu2403
            # 根据代码前缀进一步细化期货类型
            if code_part.upper().startswith(("IF", "IC", "IM", "IH")):  # 中金所股指期货
                return "ZJ_FUTURE"
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
                return "SQ_FUTURE"
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
                return "DS_FUTURE"
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
                return "ZS_FUTURE"
            elif code_part.upper().startswith(
                ("SC", "NR", "LU", "BC")
            ):  # 上海国际能源交易中心
                return "SN_FUTURE"
            else:
                return "EXTRA_FUTURE"

        # 处理期权代码
        elif suffix_part.upper() == "OPTION":
            # 期权代码通常为数字，如 10003737
            # 根据代码前缀进一步细化期权类型
            # 上海证券交易所期权代码通常以10、11、12、13、15、16、18、51、58开头
            # 深圳证券交易所期权代码通常以00、03、04、30、39开头
            if code_part.startswith(
                ("10", "11", "12", "13", "15", "16", "18", "51", "58")
            ):
                return "SH_OPTION"  # 上交所期权
            elif code_part.startswith(("00", "03", "04", "30", "39")):
                return "SZ_OPTION"  # 深交所期权
            else:
                return "EXTRA_ETF_OP"  # 其他期权

    # 对于没有后缀的6位数字代码，根据前缀推断
    elif len(symbol) == 6 and symbol.isdigit():
        prefix = symbol[:2]

        # ETF 代码段
        if prefix in {"50", "51", "15", "16", "58"}:
            return "EXTRA_ETF"  # 需要额外API调用才能确定具体交易所

        # 指数代码段
        elif symbol.startswith("000") or symbol.startswith("399"):
            return "EXTRA_INDEX_A_SH_SZ"  # 需要额外API调用才能确定具体交易所

        # 可转债代码段
        elif prefix in {"11", "12"}:
            return "EXTRA_KZZ"  # 需要额外API调用才能确定具体交易所

        # 股票代码段
        else:
            return "EXTRA_STOCK_A_SH_SZ"  # 需要额外API调用才能确定具体交易所

    # 如果无法推断，返回 None
    return None


# 检查几个有问题的代码
test_symbols = [
    "520960.SH",
    "520500.SH",
    "562310.SH",
    "588670.SH",
    "510050.SH",
    "159919.SZ",
]
for symbol in test_symbols:
    result = infer_security_type_simple(symbol)
    print(f"{symbol} -> {result}")
