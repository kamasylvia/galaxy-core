"""监视 K 线数据增长情况."""

import time
import sys
from datetime import datetime, date
from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.models.kline import KlineDay
from sqlalchemy import func


def get_kline_stats():
    """获取 K 线数据统计."""
    session = db_manager.get_session()
    try:
        start_date = date(2025, 1, 1)

        result = session.query(
            func.count(KlineDay.id).label("total"),
            func.count(func.distinct(KlineDay.symbol)).label("symbols"),
            func.max(KlineDay.updated_at).label("last_update"),
        ).filter(
            KlineDay.trade_time >= start_date
        ).first()

        return {
            "total": result.total or 0,
            "symbols": result.symbols or 0,
            "last_update": result.last_update,
        }
    finally:
        session.close()


def main():
    db_manager.initialize()

    print("=" * 70)
    print("K 线数据增长监视器 (2025年至今)")
    print("=" * 70)
    print(f"{'时间':<20} {'总记录数':<12} {'证券数':<10} {'增量':<10} {'状态'}")
    print("-" * 70)

    prev_total = 0
    stable_count = 0

    while True:
        try:
            stats = get_kline_stats()
            current_total = stats["total"]
            delta = current_total - prev_total

            # 判断状态
            if delta > 1000:
                status = "快速增长"
                stable_count = 0
            elif delta > 0:
                status = "增长中"
                stable_count = 0
            else:
                stable_count += 1
                if stable_count > 3:
                    status = "已停止"
                else:
                    status = "稳定"

            print(f"{datetime.now().strftime('%H:%M:%S'):<20} "
                  f"{current_total:<12,} {stats['symbols']:<10} {delta:<10,} {status}")

            prev_total = current_total

            # 如果连续多次无变化，可能已停止
            if stable_count > 5:
                print("\n[监视器] 数据增长已停止，退出监视")
                break

            time.sleep(5)

        except KeyboardInterrupt:
            print("\n[监视器] 用户中断")
            break
        except Exception as e:
            print(f"[错误] {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
