"""独立的数据清理脚本 - 基于交易日数量判断数据完整性.

不依赖 AmazingData SDK，可直接运行。

完整性判断标准：
1. 证券上市至今不足 250 个交易日 → 删除所有长周期数据
2. 证券上市超过 250 个交易日：
   - 周线：该周期内交易日 < 5 天 → 删除
   - 月线：该周期内交易日 < 20 天 → 删除
   - 季线：该周期内交易日 < 60 天 → 删除
   - 年线：该周期内交易日 < 230 天 → 删除
"""

import argparse
import psycopg2
import os
from dotenv import load_dotenv


# 上市时间阈值
MIN_LISTING_DAYS = 250  # 上市不足 250 个交易日，删除所有长周期数据

# 周期内交易日阈值（仅对上市超过 MIN_LISTING_DAYS 的证券）
INCOMPLETE_THRESHOLD = {
    'week': 5,
    'month': 20,
    'season': 60,
    'year': 230,
}


def get_db_connection():
    """获取数据库连接."""
    load_dotenv()
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=int(os.environ.get('DB_PORT', 5432)),
        database=os.environ.get('DB_NAME', 'galaxy'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', ''),
    )


def get_newly_listed_symbols(conn, min_days: int = MIN_LISTING_DAYS) -> list:
    """获取上市不足指定天数的证券列表.

    Returns:
        [(symbol, total_trading_days), ...]
    """
    cur = conn.cursor()
    cur.execute(f"""
        SELECT symbol, COUNT(*) as total_days
        FROM kline_day
        GROUP BY symbol
        HAVING COUNT(*) < {min_days}
        ORDER BY total_days DESC
    """)
    return cur.fetchall()


def get_period_boundary_sql(interval: str) -> tuple[str, str]:
    """获取周期边界的 SQL 表达式."""
    if interval == 'week':
        return (
            "date_trunc('week', lp.trade_time)::date",
            "(date_trunc('week', lp.trade_time) + interval '6 days')::date"
        )
    elif interval == 'month':
        return (
            "date_trunc('month', lp.trade_time)::date",
            "(date_trunc('month', lp.trade_time) + interval '1 month - 1 day')::date"
        )
    elif interval == 'season':
        return (
            "date_trunc('quarter', lp.trade_time)::date",
            "(date_trunc('quarter', lp.trade_time) + interval '3 months - 1 day')::date"
        )
    elif interval == 'year':
        return (
            "date_trunc('year', lp.trade_time)::date",
            "(date_trunc('year', lp.trade_time) + interval '1 year - 1 day')::date"
        )
    else:
        raise ValueError(f"不支持的周期: {interval}")


def count_incomplete_for_newly_listed(conn, interval: str, symbols: list) -> int:
    """统计新上市证券在该周期的不完整数据数量."""
    if not symbols:
        return 0

    table_name = f"kline_{interval}"
    cur = conn.cursor()

    # 构建 IN 子句
    symbols_str = ",".join(f"'{s}'" for s in symbols)

    cur.execute(f"""
        SELECT COUNT(*)
        FROM {table_name}
        WHERE symbol IN ({symbols_str})
    """)
    return cur.fetchone()[0]


def count_incomplete_for_established(conn, interval: str) -> int:
    """统计已稳定证券的不完整数据数量."""
    threshold = INCOMPLETE_THRESHOLD[interval]
    table_name = f"kline_{interval}"
    period_start, period_end = get_period_boundary_sql(interval)

    cur = conn.cursor()
    sql = f"""
        SELECT COUNT(*)
        FROM (
            SELECT lp.symbol, lp.trade_time, COUNT(d.trade_time) as trading_days
            FROM {table_name} lp
            LEFT JOIN kline_day d ON d.symbol = lp.symbol
                AND d.trade_time >= {period_start}
                AND d.trade_time <= {period_end}
            WHERE lp.symbol NOT IN (
                SELECT symbol FROM kline_day GROUP BY symbol HAVING COUNT(*) < {MIN_LISTING_DAYS}
            )
            GROUP BY lp.symbol, lp.trade_time
            HAVING COUNT(d.trade_time) < {threshold}
        ) incomplete
    """
    cur.execute(sql)
    return cur.fetchone()[0]


def get_incomplete_samples(conn, interval: str, limit: int = 5) -> list:
    """获取不完整数据的样例."""
    threshold = INCOMPLETE_THRESHOLD[interval]
    table_name = f"kline_{interval}"
    period_start, period_end = get_period_boundary_sql(interval)

    cur = conn.cursor()

    # 已稳定证券的样例
    sql = f"""
        SELECT lp.symbol, lp.trade_time, COUNT(d.trade_time) as trading_days
        FROM {table_name} lp
        LEFT JOIN kline_day d ON d.symbol = lp.symbol
            AND d.trade_time >= {period_start}
            AND d.trade_time <= {period_end}
        WHERE lp.symbol NOT IN (
            SELECT symbol FROM kline_day GROUP BY symbol HAVING COUNT(*) < {MIN_LISTING_DAYS}
        )
        GROUP BY lp.symbol, lp.trade_time
        HAVING COUNT(d.trade_time) < {threshold}
        ORDER BY lp.trade_time
        LIMIT {limit}
    """
    cur.execute(sql)
    return cur.fetchall()


def delete_newly_listed_data(conn, interval: str, symbols: list) -> int:
    """删除新上市证券的长周期数据."""
    if not symbols:
        return 0

    table_name = f"kline_{interval}"
    cur = conn.cursor()

    symbols_str = ",".join(f"'{s}'" for s in symbols)

    cur.execute(f"""
        DELETE FROM {table_name}
        WHERE symbol IN ({symbols_str})
    """)
    count = cur.rowcount
    conn.commit()
    return count


def delete_incomplete_for_established(conn, interval: str) -> int:
    """删除已稳定证券的不完整数据."""
    threshold = INCOMPLETE_THRESHOLD[interval]
    table_name = f"kline_{interval}"
    period_start, period_end = get_period_boundary_sql(interval)

    cur = conn.cursor()

    sql = f"""
        DELETE FROM {table_name}
        WHERE (symbol, trade_time) IN (
            SELECT lp.symbol, lp.trade_time
            FROM {table_name} lp
            LEFT JOIN kline_day d ON d.symbol = lp.symbol
                AND d.trade_time >= {period_start}
                AND d.trade_time <= {period_end}
            WHERE lp.symbol NOT IN (
                SELECT symbol FROM kline_day GROUP BY symbol HAVING COUNT(*) < {MIN_LISTING_DAYS}
            )
            GROUP BY lp.symbol, lp.trade_time
            HAVING COUNT(d.trade_time) < {threshold}
        )
    """
    cur.execute(sql)
    count = cur.rowcount
    conn.commit()
    return count


def main():
    parser = argparse.ArgumentParser(
        description="清理不完整长周期数据（基于交易日数量判断）"
    )
    parser.add_argument(
        "--interval",
        choices=["week", "month", "season", "year", "all"],
        default="all",
        help="要清理的周期类型"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只统计不实际删除"
    )

    args = parser.parse_args()

    conn = get_db_connection()

    print("=== 不完整长周期数据清理 ===")
    print(f"模式: {'dry-run（只统计）' if args.dry_run else '实际删除'}")
    print(f"周期: {args.interval}")
    print()
    print("完整性判断标准：")
    print(f"  1. 上市不足 {MIN_LISTING_DAYS} 天的证券 → 删除所有长周期数据")
    print("  2. 上市超过 250 天的证券：")
    print(f"     - 周线: 该周期内交易日 < {INCOMPLETE_THRESHOLD['week']} 天 → 删除")
    print(f"     - 月线: 该周期内交易日 < {INCOMPLETE_THRESHOLD['month']} 天 → 删除")
    print(f"     - 季线: 该周期内交易日 < {INCOMPLETE_THRESHOLD['season']} 天 → 删除")
    print(f"     - 年线: 该周期内交易日 < {INCOMPLETE_THRESHOLD['year']} 天 → 删除")
    print()

    # 获取新上市证券列表
    newly_listed = get_newly_listed_symbols(conn)
    newly_listed_symbols = [s[0] for s in newly_listed]
    print(f"上市不足 {MIN_LISTING_DAYS} 天的证券: {len(newly_listed_symbols)} 个")

    if newly_listed and len(newly_listed) <= 20:
        print("  （列表）:")
        for symbol, days in newly_listed:
            print(f"    {symbol}: {days} 个交易日")

    print()

    intervals = ["week", "month", "season", "year"] if args.interval == "all" else [args.interval]

    total = 0
    for interval in intervals:
        threshold = INCOMPLETE_THRESHOLD[interval]

        # 1. 新上市证券的数据
        count_new = count_incomplete_for_newly_listed(conn, interval, newly_listed_symbols)

        # 2. 已稳定证券的不完整数据
        count_old = count_incomplete_for_established(conn, interval)

        total_count = count_new + count_old
        print(f"{interval}: {total_count} 条不完整数据")
        print(f"  - 新上市证券: {count_new} 条")
        print(f"  - 已稳定证券（交易日 < {threshold}）: {count_old} 条")

        if count_old > 0:
            samples = get_incomplete_samples(conn, interval)
            if samples:
                print(f"  样例:")
                for symbol, trade_time, trading_days in samples:
                    print(
                        f"    {symbol} | {trade_time.strftime('%Y-%m-%d')} | "
                        f"{trading_days} 交易日"
                    )

        if not args.dry_run and total_count > 0:
            deleted = 0
            if count_new > 0:
                deleted += delete_newly_listed_data(conn, interval, newly_listed_symbols)
            if count_old > 0:
                deleted += delete_incomplete_for_established(conn, interval)
            print(f"  -> 已删除 {deleted} 条")
            total += deleted
        else:
            total += total_count

    print()
    print(f"总计: {total} 条{'（dry-run，未删除）' if args.dry_run else '已删除'}")

    if args.dry_run:
        print("\n提示: 这是 dry-run 模式，数据未实际删除。")
        print("要实际删除，请去掉 --dry-run 参数。")

    conn.close()


if __name__ == "__main__":
    main()