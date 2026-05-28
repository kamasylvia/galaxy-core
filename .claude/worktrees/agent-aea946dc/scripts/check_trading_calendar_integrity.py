"""检查交易日历数据完整性：覆盖范围、连续性、重复性."""

from datetime import date, timedelta
from collections import Counter

from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.models.trading_calendar import TradingCalendar
from sqlalchemy import func


def check_trading_calendar_integrity():
    """检查交易日历完整性."""
    # 初始化数据库
    db_manager.initialize()

    session = db_manager.get_session()
    try:
        # 1. 获取数据范围
        result = session.query(
            func.min(TradingCalendar.trade_date).label("min_date"),
            func.max(TradingCalendar.trade_date).label("max_date"),
            func.count(TradingCalendar.trade_date).label("total_count"),
            func.count(TradingCalendar.id).label("id_count"),
        ).first()

        min_date = result.min_date
        max_date = result.max_date
        total_count = result.total_count
        id_count = result.id_count

        print("=" * 60)
        print("交易日历数据完整性检查报告")
        print("=" * 60)
        print(f"\n📅 数据范围:")
        print(f"   最早日期: {min_date}")
        print(f"   最晚日期: {max_date}")
        print(f"   总记录数: {total_count}")

        # 2. 检查期望范围（2010年至今）
        expected_start = date(2010, 1, 1)
        expected_end = date.today()

        print(f"\n📋 期望覆盖范围:")
        print(f"   期望起始: {expected_start}")
        print(f"   期望结束: {expected_end}")

        coverage_issues = []
        if min_date > expected_start:
            coverage_issues.append(f"缺少 {expected_start} 到 {min_date} 之间的数据")
        if max_date < expected_end:
            coverage_issues.append(f"缺少 {max_date} 到 {expected_end} 之间的数据")

        if coverage_issues:
            print(f"   ❌ 覆盖不足:")
            for issue in coverage_issues:
                print(f"      - {issue}")
        else:
            print(f"   ✅ 覆盖范围完整")

        # 3. 检查日期连续性（是否有缺失的日期）
        all_dates_query = session.query(TradingCalendar.trade_date).order_by(TradingCalendar.trade_date)
        all_dates = [row.trade_date for row in all_dates_query.all()]

        expected_days = (max_date - min_date).days + 1
        actual_days = len(all_dates)

        print(f"\n🔗 日期连续性检查:")
        print(f"   期望天数: {expected_days} (从 {min_date} 到 {max_date})")
        print(f"   实际天数: {actual_days}")

        if expected_days != actual_days:
            print(f"   ❌ 日期不连续，缺少 {expected_days - actual_days} 天")

            # 找出缺失的日期
            current = min_date
            missing_dates = []
            date_set = set(all_dates)

            while current <= max_date:
                if current not in date_set:
                    missing_dates.append(current)
                current += timedelta(days=1)

            if len(missing_dates) <= 20:
                print(f"   缺失日期:")
                for d in missing_dates:
                    print(f"      - {d}")
            else:
                print(f"   缺失日期太多，仅显示前20个:")
                for d in missing_dates[:20]:
                    print(f"      - {d}")
                print(f"      ... 还有 {len(missing_dates) - 20} 个缺失日期")
        else:
            print(f"   ✅ 日期连续无缺失")

        # 4. 检查重复日期
        print(f"\n🔍 重复性检查:")
        date_counts = Counter(all_dates)
        duplicates = {d: c for d, c in date_counts.items() if c > 1}

        if duplicates:
            print(f"   ❌ 发现 {len(duplicates)} 个重复日期:")
            for d, c in sorted(duplicates.items())[:20]:
                print(f"      - {d}: 出现 {c} 次")
            if len(duplicates) > 20:
                print(f"      ... 还有 {len(duplicates) - 20} 个重复日期")
        else:
            print(f"   ✅ 无重复日期")

        # 5. 按年份统计
        print(f"\n📊 按年份统计:")
        year_stats = session.query(
            TradingCalendar.year,
            func.count(TradingCalendar.trade_date).label("count"),
        ).group_by(TradingCalendar.year).order_by(TradingCalendar.year).all()

        for year, count in year_stats:
            year_start = date(year, 1, 1)
            year_end = date(year, 12, 31)
            expected_year_days = (year_end - year_start).days + 1

            # 单独查询该年交易日数量
            trading_days = session.query(TradingCalendar).filter(
                TradingCalendar.year == year,
                TradingCalendar.is_trading_day == True
            ).count()

            status = "✅" if count == expected_year_days else "❌"
            print(f"   {status} {year}: {count} 天 (交易日: {trading_days})")

        # 6. 交易日统计
        print(f"\n📈 交易日统计:")
        trading_day_count = session.query(TradingCalendar).filter(
            TradingCalendar.is_trading_day == True
        ).count()
        non_trading_day_count = session.query(TradingCalendar).filter(
            TradingCalendar.is_trading_day == False
        ).count()

        print(f"   交易日总数: {trading_day_count}")
        print(f"   非交易日总数: {non_trading_day_count}")

        # 7. 总结
        print(f"\n" + "=" * 60)
        print("总结")
        print("=" * 60)

        all_good = (
            not coverage_issues and
            expected_days == actual_days and
            not duplicates
        )

        if all_good:
            print("✅ 交易日历数据完整性检查通过")
        else:
            print("❌ 交易日历数据存在问题，需要修复")

        return all_good

    finally:
        session.close()


if __name__ == "__main__":
    check_trading_calendar_integrity()
