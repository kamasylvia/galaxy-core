#!/usr/bin/env python3
"""
测试额外的证券代码前缀
"""


def infer_security_type_simple(symbol: str) -> str:
    symbol = symbol.strip()

    if "." in symbol:
        code_part, suffix_part = symbol.rsplit(".", 1)

        if len(code_part) == 6 and code_part.isdigit():
            prefix = code_part[:2]

            if prefix in {"50", "51", "52", "53", "55", "56", "15", "16", "58"}:
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
                    return "BJ_A"

            elif code_part.startswith("000") or code_part.startswith("399"):
                if suffix_part.upper() == "SH":
                    return "SH_INDEX"
                elif suffix_part.upper() == "SZ":
                    return "SZ_INDEX"
                elif suffix_part.upper() == "BJ":
                    return "BJ_INDEX"

            elif prefix in {"11", "12"}:
                if suffix_part.upper() == "SH":
                    return "SH_KZZ"
                elif suffix_part.upper() == "SZ":
                    return "SZ_KZZ"
                elif suffix_part.upper() == "BJ":
                    return "BJ_A"

            elif code_part.startswith("90"):
                if suffix_part.upper() == "SH":
                    return "SH_HKT"
                elif suffix_part.upper() == "SZ":
                    return "SZ_HKT"

            else:
                if suffix_part.upper() == "SH":
                    return "SH_A"
                elif suffix_part.upper() == "SZ":
                    return "SZ_A"
                elif suffix_part.upper() == "BJ":
                    return "BJ_A"

    return None


# 检查53开头的代码
test_symbols = ["530000.SH", "530050.SH", "562560.SH", "551000.SH", "562310.SH"]
for symbol in test_symbols:
    result = infer_security_type_simple(symbol)
    print(f"{symbol} -> {result}")
