import sys
import os

sys.path.insert(0, os.path.join(os.getcwd(), "src"))

try:
    from galaxy_db_sync.shared_kernel.utils.time_parser import (
        convert_date_string_to_int,
    )

    print("测试年线日期转换:")
    result1 = convert_date_string_to_int("2024", "year", is_end_date=False)
    result2 = convert_date_string_to_int("2024", "year", is_end_date=True)
    print(f"  '2024' (开始日期) -> {result1}")
    print(f"  '2024' (结束日期) -> {result2}")
    print(f"  预期: 20240101 (开始), 20241231 (结束)")

    print("\n测试月线日期转换:")
    result3 = convert_date_string_to_int("202401", "month", is_end_date=False)
    result4 = convert_date_string_to_int("202401", "month", is_end_date=True)
    print(f"  '202401' (开始日期) -> {result3}")
    print(f"  '202401' (结束日期) -> {result4}")
    print(f"  预期: 20240101 (开始), 20240131 (结束)")

    print("\n测试季线日期转换:")
    result5 = convert_date_string_to_int("202403", "season", is_end_date=False)
    result6 = convert_date_string_to_int("202403", "season", is_end_date=True)
    print(f"  '202403' (开始日期) -> {result5}")
    print(f"  '202403' (结束日期) -> {result6}")
    print(f"  预期: 20240301 (开始), 20240331 (结束)")

    print("\n测试日线日期转换:")
    result7 = convert_date_string_to_int("20240115", "day", is_end_date=False)
    result8 = convert_date_string_to_int("20240115", "day", is_end_date=True)
    print(f"  '20240115' (开始日期) -> {result7}")
    print(f"  '20240115' (结束日期) -> {result8}")
    print(f"  预期: 20240115 (开始), 20240115 (结束)")

    print("\n测试周线日期转换:")
    result9 = convert_date_string_to_int("20240115", "week", is_end_date=False)
    result10 = convert_date_string_to_int("20240115", "week", is_end_date=True)
    print(f"  '20240115' (开始日期) -> {result9}")
    print(f"  '20240115' (结束日期) -> {result10}")
    print(f"  预期: 20240115 (开始), 20240115 (结束)")

    # 验证修复结果
    success = True
    if result1 != 20240101 or result2 != 20241231:
        print("\n❌ 年线测试失败")
        success = False
    if result3 != 20240101 or result4 != 20240131:
        print("\n❌ 月线测试失败")
        success = False
    if result5 != 20240301 or result6 != 20240331:
        print("\n❌ 季线测试失败")
        success = False
    if result7 != 20240115 or result8 != 20240115:
        print("\n❌ 日线测试失败")
        success = False
    if result9 != 20240115 or result10 != 20240115:
        print("\n❌ 周线测试失败")
        success = False

    if success:
        print("\n✅ 所有测试通过！日期格式修复成功。")
    else:
        print("\n❌ 测试失败。")
except Exception as e:
    print(f"发生错误: {e}")
    import traceback

    traceback.print_exc()
