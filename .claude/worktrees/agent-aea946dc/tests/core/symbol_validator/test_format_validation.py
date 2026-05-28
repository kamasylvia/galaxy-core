#!/usr/bin/env python3
"""证券代码格式验证测试"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
current_dir = Path(__file__).parent.absolute()
project_root = current_dir.parent.parent.parent
sys.path.insert(0, str(project_root))

from galaxy_db_sync.shared_kernel.utils import (
    validate_symbol_format,
    normalize_symbol,
    parse_symbols,
)


def test_validate_symbol_format():
    """测试证券代码格式验证功能"""
    print("Testing validate_symbol_format function...")

    # 测试有效的6位数字
    assert validate_symbol_format("600000") == True
    print("✅ 6位数字格式验证通过")

    # 测试有效的带后缀格式
    assert validate_symbol_format("600000.SH") == True
    assert validate_symbol_format("000001.SZ") == True
    assert validate_symbol_format("920001.BJ") == True
    print("✅ 带后缀格式验证通过")

    # 测试数字与后缀匹配的情况
    assert validate_symbol_format("600000.SH") == True  # 60开头应为SH
    assert validate_symbol_format("000001.SZ") == True  # 00开头应为SZ
    assert validate_symbol_format("920001.BJ") == True  # 920开头应为BJ
    assert validate_symbol_format("510050.SH") == True  # 51开头应为SH
    assert validate_symbol_format("159919.SZ") == True  # 15开头应为SZ
    print("✅ 数字与后缀匹配验证通过")

    # 测试数字与后缀不匹配的情况（应该返回False）
    assert validate_symbol_format("600000.SZ") == False  # 60开头不能是SZ
    assert validate_symbol_format("000001.SH") == False  # 00开头不能是SH
    assert validate_symbol_format("920001.SH") == False  # 920开头不能是SH
    assert validate_symbol_format("510050.SZ") == False  # 51开头不能是SZ
    assert validate_symbol_format("159919.SH") == False  # 15开头不能是SH
    print("✅ 数字与后缀不匹配验证通过（正确拒绝）")

    # 测试期货代码格式
    assert validate_symbol_format("IF2403.FUTURE") == True  # 股指期货
    assert validate_symbol_format("cu2403.FUTURE") == True  # 铜期货
    assert validate_symbol_format("SR405.FUTURE") == True  # 白糖期货
    print("✅ 期货代码格式验证通过")

    # 测试期权代码格式
    assert validate_symbol_format("10003737.OPTION") == True  # 期权代码
    assert validate_symbol_format("10003737.CZC.OPTION") == True  # 带交易所的期权代码
    print("✅ 期权代码格式验证通过")

    # 测试无效的期货/期权代码格式
    assert validate_symbol_format("IF2403.INVALID") == False  # 无效后缀
    assert validate_symbol_format("12345A.FUTURE") == False  # 非字母开头的期货代码
    assert validate_symbol_format("ABCD.OPTION") == False  # 非数字开头的期权代码
    print("✅ 无效期货/期权代码格式拒绝通过")

    # 测试有效的SecurityType
    assert validate_symbol_format("SH_A") == True
    assert validate_symbol_format("SZ_ETF") == True
    assert validate_symbol_format("EXTRA_STOCK_A") == True
    print("✅ SecurityType格式验证通过")

    # 测试无效格式
    assert validate_symbol_format("123") == False  # 不是6位数字
    assert validate_symbol_format("600000.NYSE") == False  # 无效后缀
    assert validate_symbol_format("ABCDEF") == False  # 非数字
    assert validate_symbol_format("") == False  # 空字符串
    print("✅ 无效格式拒绝通过")


def test_normalize_symbol():
    """测试证券代码标准化功能"""
    print("Testing normalize_symbol function...")

    # 测试6位数字自动补全后缀
    assert normalize_symbol("600000") == "600000.SH"
    assert normalize_symbol("000001") == "000001.SZ"
    assert normalize_symbol("300001") == "300001.SZ"
    assert normalize_symbol("510050") == "510050.SH"
    assert normalize_symbol("159919") == "159919.SZ"
    assert normalize_symbol("920001") == "920001.BJ"
    print("✅ 6位数字自动补全后缀通过")

    # 测试已有后缀的代码
    assert normalize_symbol("600000.SH") == "600000.SH"
    assert normalize_symbol("000001.SZ") == "000001.SZ"
    print("✅ 已有后缀的代码保持不变通过")

    # 测试非6位数字的代码
    assert normalize_symbol("INVALID") == "INVALID"
    print("✅ 非6位数字的代码保持不变通过")


def test_parse_symbols():
    """测试证券代码解析功能"""
    print("Testing parse_symbols function...")

    # 测试单个代码
    result = parse_symbols("600000")
    assert result == [("symbol", "600000.SH")]
    print("✅ 单个代码解析通过")

    # 测试带后缀的单个代码
    result = parse_symbols("600000.SH")
    assert result == [("symbol", "600000.SH")]
    print("✅ 带后缀单个代码解析通过")

    # 测试SecurityType
    result = parse_symbols("SH_A")
    assert result == [("security_type", "SH_A")]
    print("✅ SecurityType解析通过")

    # 测试逗号分隔的列表
    result = parse_symbols("600000,000001")
    assert result == [("symbol", "600000.SH"), ("symbol", "000001.SZ")]
    print("✅ 逗号分隔列表解析通过")

    # 测试列表格式
    result = parse_symbols("[600000.SH, 000001.SZ]")
    assert result == [("symbol", "600000.SH"), ("symbol", "000001.SZ")]
    print("✅ 列表格式解析通过")

    # 测试混合格式
    result = parse_symbols("[600000, SH_A]")
    assert result == [("symbol", "600000.SH"), ("security_type", "SH_A")]
    print("✅ 混合格式解析通过")

    # 测试空列表
    result = parse_symbols("[]")
    assert result == []
    print("✅ 空列表解析通过")

    # 测试空字符串
    result = parse_symbols("")
    assert result == []
    print("✅ 空字符串解析通过")


def test_error_handling():
    """测试错误处理"""
    print("Testing error handling...")

    # 测试无效格式
    try:
        parse_symbols("123")
        print("❌ 应该抛出ValueError异常")
        raise AssertionError("应该抛出ValueError异常")
    except ValueError:
        print("✅ 正确捕获无效格式异常")


if __name__ == "__main__":
    print("开始测试证券代码格式验证功能...\n")

    try:
        success1 = test_validate_symbol_format()
        print()
        success2 = test_normalize_symbol()
        print()
        success3 = test_parse_symbols()
        print()
        success4 = test_error_handling()

        if success1 and success2 and success3 and success4:
            print("\n🎉 所有格式验证测试通过!")
        else:
            print("\n❌ 部分测试失败")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
