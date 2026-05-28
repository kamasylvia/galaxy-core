#!/usr/bin/env python3
"""测试日期格式修复功能"""

from galaxy_db_sync.shared_kernel.utils.time_parser import convert_date_string_to_int


def test_date_conversion():
    """测试日期转换功能"""
    print("测试年线日期转换:")
    print(
        f"  '2024' (开始日期) -> {convert_date_string_to_int('2024', 'year', is_end_date=False)}"
    )  # 应该是 20240101
    print(
        f"  '2024' (结束日期) -> {convert_date_string_to_int('2024', 'year', is_end_date=True)}"
    )  # 应该是 20241231

    print("\n测试月线日期转换:")
    print(
        f"  '202401' (开始日期) -> {convert_date_string_to_int('202401', 'month', is_end_date=False)}"
    )  # 应该是 20240101
    print(
        f"  '202401' (结束日期) -> {convert_date_string_to_int('202401', 'month', is_end_date=True)}"
    )  # 应该是 20240131
    print(
        f"  '202402' (开始日期) -> {convert_date_string_to_int('202402', 'month', is_end_date=False)}"
    )  # 应该是 20240201
    print(
        f"  '202402' (结束日期) -> {convert_date_string_to_int('202402', 'month', is_end_date=True)}"
    )  # 应该是 20240229 (闰年)
    print(
        f"  '202302' (开始日期) -> {convert_date_string_to_int('202302', 'month', is_end_date=False)}"
    )  # 应该是 20230201
    print(
        f"  '202302' (结束日期) -> {convert_date_string_to_int('202302', 'month', is_end_date=True)}"
    )  # 应该是 20230228 (非闰年)

    print("\n测试季线日期转换:")
    print(
        f"  '202401' (开始日期) -> {convert_date_string_to_int('202401', 'season', is_end_date=False)}"
    )  # 应该是 20240101
    print(
        f"  '202401' (结束日期) -> {convert_date_string_to_int('202401', 'season', is_end_date=True)}"
    )  # 应该是 20240131
    print(
        f"  '202403' (开始日期) -> {convert_date_string_to_int('202403', 'season', is_end_date=False)}"
    )  # 应该是 20240301
    print(
        f"  '202403' (结束日期) -> {convert_date_string_to_int('202403', 'season', is_end_date=True)}"
    )  # 应该是 20240331

    print("\n测试日线日期转换:")
    print(
        f"  '20240115' (开始日期) -> {convert_date_string_to_int('20240115', 'day', is_end_date=False)}"
    )  # 应该是 20240115
    print(
        f"  '20240115' (结束日期) -> {convert_date_string_to_int('20240115', 'day', is_end_date=True)}"
    )  # 应该是 20240115

    print("\n测试周线日期转换:")
    print(
        f"  '20240115' (开始日期) -> {convert_date_string_to_int('20240115', 'week', is_end_date=False)}"
    )  # 应该是 20240115
    print(
        f"  '20240115' (结束日期) -> {convert_date_string_to_int('20240115', 'week', is_end_date=True)}"
    )  # 应该是 20240115

    print("\n测试小时线日期转换:")
    print(
        f"  '2024011509' (开始日期) -> {convert_date_string_to_int('2024011509', 'min60', is_end_date=False)}"
    )  # 应该是 20240115090000
    print(
        f"  '2024011509' (结束日期) -> {convert_date_string_to_int('2024011509', 'min60', is_end_date=True)}"
    )  # 应该是 20240115095959


if __name__ == "__main__":
    test_date_conversion()
