"""检查数据库中2024年至今的K线数据情况."""

from datetime import date, datetime
from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.models.kline import KlineDay
from sqlalchemy import func, distinct


def check_kline_data():
    """检查K线数据."""
    db_manager.initialize()
    session = db_manager.get_session()

    try:
        print("=" * 60)
        print("K线数据检查报告 (2024年至今)")
        print("=" * 60)

        # 1. 总体统计
        start_date = datetime(2024, 1, 1)
        end_date = datetime.now()

        result = session.query(
            func.count(KlineDay.id).label("total_records"),
            func.count(distinct(KlineDay.symbol)).label("unique_symbols"),
            func.min(KlineDay.trade_time).label("min_date"),
            func.max(KlineDay.trade_time).label("max_date"),
        ).filter(
            KlineDay.trade_time >= start_date,
            KlineDay.trade_time <= end_date,
        ).first()

        print(f"\n📊 日线数据总体统计:")
        print(f"   总记录数: {result.total_records}")
        print(f"   不同证券数: {result.unique_symbols}")
        print(f"   最早日期: {result.min_date}")
        print(f"   最晚日期: {result.max_date}")

        # 2. 查看最近的同步记录
        print(f"\n🕐 最近同步的10条记录:")
        recent_records = session.query(
            KlineDay.symbol,
            KlineDay.trade_time,
            KlineDay.close
        ).filter(
            KlineDay.trade_time >= start_date,
        ).order_by(KlineDay.updated_at.desc()).limit(10).all()

        for symbol, trade_time, close in recent_records:
            print(f"   {symbol} {trade_time.date()}: close={close}")

        # 3. 检查EXTRA_ETF相关数据 - 以SH和SZ结尾的ETF
        print(f"\n🔍 ETF数据样本 (前20个):")
        etf_samples = session.query(
            KlineDay.symbol,
            func.count(KlineDay.id).label("count"),
            func.min(KlineDay.trade_time).label("min_date"),
            func.max(KlineDay.trade_time).label("max_date"),
        ).filter(
            KlineDay.trade_time >= start_date,
            (KlineDay.symbol.like('51%.SH') | KlineDay.symbol.like('15%.SZ') |
             KlineDay.symbol.like('56%.SH') | KlineDay.symbol.like('16%.SZ') |
             KlineDay.symbol.like('58%.SH') | KlineDay.symbol.like('59%.SH'))
        ).group_by(KlineDay.symbol).limit(20).all()

        for symbol, count, min_date, max_date in etf_samples:
            print(f"   {symbol}: {count} 条, {min_date.date()} ~ {max_date.date()}")

        # 4. 按日期统计记录数（检查是否有数据）
        print(f"\n📅 最近7天数据量:")
        from datetime import timedelta
        for i in range(7):
            check_date = end_date.date() - timedelta(days=i)
            start_of_day = datetime.combine(check_date, datetime.min.time())
            end_of_day = datetime.combine(check_date, datetime.max.time())
            count = session.query(KlineDay).filter(
                KlineDay.trade_time >= start_of_day,
                KlineDay.trade_time <= end_of_day,
            ).count()
            print(f"   {check_date}: {count} 条记录")

        # 5. 检查特定的几个ETF
        print(f"\n📋 特定ETF检查 (551550.SH, 510330.SH, 159381.SZ):")
        for symbol in ['551550.SH', '510330.SH', '159381.SZ']:
            count = session.query(KlineDay).filter(
                KlineDay.symbol == symbol,
                KlineDay.trade_time >= start_date,
            ).count()
            print(f"   {symbol}: {count} 条记录 (2024至今)")

    finally:
        session.close()


if __name__ == "__main__":
    check_kline_data()
