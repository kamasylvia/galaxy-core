#!/usr/bin/env python3
"""
期权API支持验证脚本

该脚本用于验证 get_hist_code_list 和 get_option_code_list 是否支持期权类型。
"""

import pytest

pytest.skip("manual integration script; excluded from automated test runs", allow_module_level=True)

import sys
import os
import traceback

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from galaxy_db_sync.amazing_data.api.client import amazing_data_client
from galaxy_db_sync.shared_kernel.utils.config_loader import get_section


def test_get_hist_code_list_with_option():
    """测试 get_hist_code_list 是否支持期权类型"""
    print("=" * 60)
    print("测试 get_hist_code_list 是否支持期权类型")
    print("=" * 60)

    option_security_types = ["EXTRA_ETF_OP", "SH_OPTION", "SZ_OPTION"]

    for sec_type in option_security_types:
        print(f"\n测试 security_type: {sec_type}")
        try:
            # 从配置获取 local_path
            amazing_data_config = get_section("amazing_data")
            local_path = amazing_data_config.get("local_path", "./cache")

            # 尝试获取期权代码列表
            result = amazing_data_client.get_hist_code_list(
                security_type=sec_type,
                start_date=20200101,
                end_date=20251231,
                local_path=local_path,
            )

            print(f"  ✓ 成功获取 {sec_type} 的代码列表")
            print(f"  - 代码数量: {len(result)}")
            if result:
                print(f"  - 前5个代码: {result[:5]}")
            else:
                print(f"  - 无代码返回")

        except Exception as e:
            print(f"  ✗ 获取 {sec_type} 代码列表失败: {str(e)}")
            print(f"  - 错误类型: {type(e).__name__}")
            if (
                "not support" in str(e).lower()
                or "invalid" in str(e).lower()
                or "not found" in str(e).lower()
            ):
                print(f"  - 错误信息表明该 security_type 在当前 API 路径下不可用")


def test_get_option_code_list():
    """测试 get_option_code_list 功能"""
    print("\n" + "=" * 60)
    print("测试 get_option_code_list 功能")
    print("=" * 60)

    option_security_types = ["EXTRA_ETF_OP", "SH_OPTION", "SZ_OPTION"]

    for sec_type in option_security_types:
        print(f"\n测试 security_type: {sec_type}")
        try:
            # 尝试获取期权代码列表
            result = amazing_data_client.get_option_code_list(security_type=sec_type)

            print(f"  ✓ 成功获取 {sec_type} 的期权代码列表")
            print(f"  - 代码数量: {len(result)}")
            if result:
                print(f"  - 前5个代码: {result[:5]}")
            else:
                print(f"  - 无代码返回")

        except Exception as e:
            print(f"  ✗ 获取 {sec_type} 期权代码列表失败: {str(e)}")
            print(f"  - 错误类型: {type(e).__name__}")
            traceback.print_exc()


def main():
    """主函数"""
    print("期权API支持验证脚本")
    print("注意：此脚本需要有效的AmazingData账户和网络连接")

    try:
        # 首先测试 get_hist_code_list
        test_get_hist_code_list_with_option()

        # 然后测试 get_option_code_list
        test_get_option_code_list()

        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)

    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
