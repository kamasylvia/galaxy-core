#!/usr/bin/env python3
"""
调试日期格式问题
"""

import os
import sys
from dotenv import load_dotenv

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

load_dotenv()

def debug_date_format():
    """调试日期格式转换问题"""

    from galaxy_db_sync.shared_kernel.utils.time_parser import validate_start_end_by_interval, convert_date_string_to_int

    print("测试不同日期格式转换:")

    # 测试月份格式 (YYYYMM)
    interval = "month"
    start = "202501"
    end = "202505"

    print(f"\n输入: interval={interval}, start={start}, end={end}")
    adjusted_start, adjusted_end = validate_start_end_by_interval(interval, start, end)
    print(f"调整后: start={adjusted_start}, end={adjusted_end}")

    start_int = convert_date_string_to_int(adjusted_start, interval)
    end_int = convert_date_string_to_int(adjusted_end, interval)
    print(f"转换为整数: start={start_int}, end={end_int}")

    # 测试其他可能的格式
    print("\n其他可能的格式测试:")
    test_cases = [
        ("2025", "2025", "year"),
        ("20250101", "20250531", "day"),
        ("202501", "202505", "month"),
    ]

    for start, end, interval in test_cases:
        print(f"\n输入: interval={interval}, start={start}, end={end}")
        adjusted_start, adjusted_end = validate_start_end_by_interval(interval, start, end)
        print(f"调整后: start={adjusted_start}, end={adjusted_end}")

        start_int = convert_date_string_to_int(adjusted_start, interval)
        end_int = convert_date_string_to_int(adjusted_end, interval)
        print(f"转换为整数: start={start_int}, end={end_int}")

if __name__ == "__main__":
    debug_date_format()
