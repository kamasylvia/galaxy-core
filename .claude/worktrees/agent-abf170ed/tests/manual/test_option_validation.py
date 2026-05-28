#!/usr/bin/env python3
"""
期权验证功能测试脚本

此脚本测试期权类型验证功能是否正常工作。
"""

import pytest

pytest.skip("manual integration script; excluded from automated test runs", allow_module_level=True)

import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from galaxy_db_bridge.shared_kernel.utils.symbol_validator import (
    symbol_validator,
    get_validated_symbols,
)


def test_option_validation():
    """测试期权验证功能"""
    print("测试期权验证功能...")

    # 测试期权SecurityType
    option_types = ["EXTRA_ETF_OP", "SH_OPTION", "SZ_OPTION"]

    for opt_type in option_types:
        print(f"\n测试期权类型: {opt_type}")
        try:
            result = symbol_validator([opt_type])
            print(f"  ✓ 验证成功: {result}")

            validated = get_validated_symbols([opt_type])
            print(f"  ✓ 有效代码获取: {validated}")

        except Exception as e:
            print(f"  ✗ 验证失败: {e}")


def test_mixed_validation():
    """测试混合验证（包含期权和普通代码）"""
    print("\n测试混合验证（期权和普通代码）...")

    mixed_symbols = ["EXTRA_ETF_OP", "600000.SH", "SH_A"]

    try:
        result = symbol_validator(mixed_symbols)
        print(f"  ✓ 混合验证结果: {result}")

        validated = get_validated_symbols(mixed_symbols)
        print(f"  ✓ 有效代码: {validated[:5]}...")  # 只显示前5个

    except Exception as e:
        print(f"  ✗ 混合验证失败: {e}")


def main():
    """主函数"""
    print("期权验证功能测试")
    print("=" * 50)

    try:
        test_option_validation()
        test_mixed_validation()

        print("\n" + "=" * 50)
        print("测试完成")

    except Exception as e:
        print(f"测试过程中发生错误: {e}")


if __name__ == "__main__":
    main()
