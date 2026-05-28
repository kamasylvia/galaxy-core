#!/usr/bin/env python3
"""
调试时间转换问题
"""

import os
import sys
from dotenv import load_dotenv

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

load_dotenv()

def debug_time_conversion():
    """调试时间转换问题"""

    print("正在测试时间转换函数...")

    from galaxy_db_bridge.shared_kernel.utils.time_parser import (
        convert_date_string_to_int,
        validate_start_end_by_period
    )

    # 测试月线的时间转换
    interval = "month"
    start = "202501"
    end = "202505"

    print(f"原始输入: start={start}, end={end}, interval={interval}")

    # 验证并调整日期参数
    adjusted_start, adjusted_end = validate_start_end_by_period(
        interval, start, end
    )

    print(f"调整后: start={adjusted_start}, end={adjusted_end}")

    # 转换为整数
    start_int = convert_date_string_to_int(adjusted_start, interval)
    end_int = convert_date_string_to_int(adjusted_end, interval)

    print(f"转换为整数: start_int={start_int}, end_int={end_int}")

    # 现在测试API调用
    print("\n正在连接AmazingData API...")
    from galaxy_db_bridge.amazing_data.api.client import amazing_data_client

    import AmazingData as ad

    # 首先登录
    username = os.getenv('GALAXY_USERNAME')
    password = os.getenv('GALAXY_PASSWORD')
    host = os.getenv('GALAXY_HOST')
    port = int(os.getenv('GALAXY_PORT'))

    print(f"使用账户: {username}, host: {host}:{port}")

    login_result = ad.login(username, password, host, port)
    print(f"登录结果: {login_result}")

    # 使用转换后的整数调用API
    print(f"\n使用转换后的整数调用get_hist_code_list: start_date={start_int}, end_date={end_int}")
    extra_etf_codes = amazing_data_client.get_hist_code_list("EXTRA_ETF", start_date=start_int, end_date=end_int, local_path="./cache/")
    print(f"EXTRA_ETF在{start_int}-{end_int}期间的代码数量: {len(extra_etf_codes)}")
    if extra_etf_codes:
        print(f"前10个代码: {extra_etf_codes[:10]}")

    # 再次使用原始日期调用API，看是否与我们之前的调试结果一致
    print(f"\n使用原始日期调用get_hist_code_list: start_date=20250101, end_date=20250531")
    extra_etf_codes_original = amazing_data_client.get_hist_code_list("EXTRA_ETF", start_date=20250101, end_date=20250531, local_path="./cache/")
    print(f"EXTRA_ETF在20250101-20250531期间的代码数量: {len(extra_etf_codes_original)}")
    if extra_etf_codes_original:
        print(f"前10个代码: {extra_etf_codes_original[:10]}")

    # 登出
    try:
        ad.logout(username)
        print("\n已登出")
    except:
        print("\n登出时发生错误")


if __name__ == "__main__":
    debug_time_conversion()
