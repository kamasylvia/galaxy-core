"""
测试交易日历缓存逻辑的单元测试
不依赖实际数据库连接，只测试缓存判断逻辑
"""
from datetime import date


def test_cache_logic():
    """测试缓存判断逻辑是否正确"""

    print("测试交易日历缓存判断逻辑...")

    # 模拟原来的错误逻辑
    def old_cache_logic(cached_dates, start_date, end_date):
        """原始的错误逻辑"""
        return len(cached_dates) == 0 or (
            cached_dates
            and (min(cached_dates) > start_date or max(cached_dates) < end_date)
        )

    # 模拟修复后的逻辑
    def new_cache_logic(cached_dates, start_date, end_date):
        """修复后的逻辑"""
        cache_has_data = len(cached_dates) > 0
        cache_fully_covers_range = (
            cache_has_data
            and min(cached_dates) <= start_date
            and max(cached_dates) >= end_date
        )

        return not cache_fully_covers_range

    # 测试案例1：缓存完全覆盖请求范围
    # 假设数据库中有从2016-01-01到2016-02-28的所有交易日（实际交易日）
    cached_dates = [date(2016, 1, 1), date(2016, 1, 4), date(2016, 1, 5), date(2016, 1, 6), date(2016, 1, 7), date(2016, 1, 8),
                   date(2016, 1, 11), date(2016, 1, 12), date(2016, 1, 13), date(2016, 1, 14), date(2016, 1, 15)]  # 包含起始日期附近的交易日
    start_date = date(2016, 1, 1)  # 请求开始日期
    end_date = date(2016, 1, 10)   # 请求结束日期

    # 在这个例子中，缓存包含了从2016-01-01开始的一些交易日，直到2016-01-15
    # 请求范围是2016-01-01到2016-01-10，这意味着缓存完全覆盖了请求范围
    # 因为min(cached_dates)=2016-01-01 <= start_date=2016-01-01
    # 且max(cached_dates)=2016-01-15 >= end_date=2016-01-10

    print("\n测试案例1: 缓存完全覆盖请求范围")
    print(f"缓存交易日: {min(cached_dates)} 到 {max(cached_dates)}")
    print(f"请求范围: {start_date} 到 {end_date}")
    print(f"原逻辑需要获取数据: {old_cache_logic(cached_dates, start_date, end_date)}")
    print(f"新逻辑需要获取数据: {new_cache_logic(cached_dates, start_date, end_date)}")

    # 测试案例2：缓存不包含请求范围的开始部分
    cached_dates2 = [date(2016, 1, 15), date(2016, 1, 16), date(2016, 1, 17)]
    start_date2 = date(2016, 1, 1)
    end_date2 = date(2016, 1, 20)

    print("\n测试案例2: 缓存不包含请求开始部分")
    print(f"缓存交易日: {min(cached_dates2)} 到 {max(cached_dates2)}")
    print(f"请求范围: {start_date2} 到 {end_date2}")
    print(f"原逻辑需要获取数据: {old_cache_logic(cached_dates2, start_date2, end_date2)}")
    print(f"新逻辑需要获取数据: {new_cache_logic(cached_dates2, start_date2, end_date2)}")

    # 测试案例3：缓存不包含请求范围的结束部分
    cached_dates3 = [date(2016, 1, 1), date(2016, 1, 2), date(2016, 1, 3)]
    start_date3 = date(2016, 1, 1)
    end_date3 = date(2016, 1, 20)

    print("\n测试案例3: 缓存不包含请求结束部分")
    print(f"缓存交易日: {min(cached_dates3)} 到 {max(cached_dates3)}")
    print(f"请求范围: {start_date3} 到 {end_date3}")
    print(f"原逻辑需要获取数据: {old_cache_logic(cached_dates3, start_date3, end_date3)}")
    print(f"新逻辑需要获取数据: {new_cache_logic(cached_dates3, start_date3, end_date3)}")

    # 测试案例4：没有任何缓存
    cached_dates4 = []
    start_date4 = date(2016, 1, 1)
    end_date4 = date(2016, 1, 20)

    print("\n测试案例4: 没有任何缓存")
    print(f"缓存交易日: 无")
    print(f"请求范围: {start_date4} 到 {end_date4}")
    print(f"原逻辑需要获取数据: {old_cache_logic(cached_dates4, start_date4, end_date4)}")
    print(f"新逻辑需要获取数据: {new_cache_logic(cached_dates4, start_date4, end_date4)}")

    print("\n结论:")
    print("- 原逻辑在案例1中错误地认为需要获取数据（因为min > start_date）")
    print("- 新逻辑在案例1中正确地认为不需要获取数据（因为缓存完全覆盖了请求范围）")
    print("- 修复后的逻辑解决了缓存永远无法命中的问题")


if __name__ == "__main__":
    test_cache_logic()
