"""独立测试日期转换逻辑"""

import calendar
from datetime import datetime


def convert_date_string_to_int(
    date_str: str, interval: str, is_end_date: bool = False
) -> int:
    """将日期字符串转换为整数格式，根据周期类型决定精度.

    Args:
        date_str: 日期字符串
        interval: 周期类型
        is_end_date: 是否是结束日期，如果是则补全为周期最后一天，否则补全为第一天

    Returns:
        整数格式的日期
    """
    # 根据周期确定日期字符串的长度
    if interval == "year":
        # 年线：4位数字 (YYYY)
        date_str = date_str.zfill(4)
        year = int(date_str[:4])
        if is_end_date:
            # 结束日期：补全为该年的最后一天
            return year * 10000 + 1231  # YYYY1231
        else:
            # 开始日期：补全为该年的第一天
            return year * 10000 + 101  # YYYY0101
    elif interval in ("season", "month"):
        # 月线/季线：6位数字 (YYYYMM)
        date_str = date_str.zfill(6)
        year = int(date_str[:4])
        month = int(date_str[4:6])

        if is_end_date:
            # 结束日期：补全为该月的最后一天
            last_day = calendar.monthrange(year, month)[1]
            return year * 10000 + month * 100 + last_day  # YYYYMMDD
        else:
            # 开始日期：补全为该月的第一天
            return year * 10000 + month * 100 + 1  # YYYYMM01
    elif interval in ("day", "week"):
        # 日线/周线：8位数字 (YYYYMMDD)
        date_str = date_str.zfill(8)
        return int(date_str[:8])
    elif interval in ("min60", "min120"):
        # 小时线：10位数字 (YYYYMMDDHH)
        date_str = date_str.zfill(10)
        if is_end_date:
            # 结束日期：补全为该小时的最后时刻
            return int(date_str[:10] + "5959")  # 补全为 YYYYMMDDHH5959
        else:
            # 开始日期：补全为该小时的开始时刻
            return int(date_str[:10] + "0000")  # 补全为 YYYYMMDDHH0000
    elif interval in ("min1", "min3", "min5", "min10", "min15", "min30"):
        # 分钟线：12位数字 (YYYYMMDDHHMM)
        date_str = date_str.zfill(12)
        return int(date_str[:12])
    else:
        # 默认按日线处理
        date_str = date_str.zfill(8)
        return int(date_str[:8])


def test_date_conversion():
    """测试日期转换功能"""
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

    print("\n测试闰年2月:")
    result11 = convert_date_string_to_int("202402", "month", is_end_date=False)
    result12 = convert_date_string_to_int("202402", "month", is_end_date=True)
    print(f"  '202402' (开始日期) -> {result11}")
    print(f"  '202402' (结束日期) -> {result12}")
    print(f"  预期: 20240201 (开始), 20240229 (结束) - 闰年")

    print("\n测试非闰年2月:")
    result13 = convert_date_string_to_int("202302", "month", is_end_date=False)
    result14 = convert_date_string_to_int("202302", "month", is_end_date=True)
    print(f"  '202302' (开始日期) -> {result13}")
    print(f"  '202302' (结束日期) -> {result14}")
    print(f"  预期: 20230201 (开始), 20230228 (结束) - 非闰年")

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
    if result11 != 20240201 or result12 != 20240229:
        print("\n❌ 闰年2月测试失败")
        success = False
    if result13 != 20230201 or result14 != 20230228:
        print("\n❌ 非闰年2月测试失败")
        success = False

    if success:
        print("\n✅ 所有测试通过！日期格式修复成功。")
    else:
        print("\n❌ 测试失败。")
        raise AssertionError("日期转换逻辑测试失败")


if __name__ == "__main__":
    test_date_conversion()
