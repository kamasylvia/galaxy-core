#!/usr/bin/env python3
"""检查交易日历表中的重复日期问题。"""

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()


def check_trading_calendar_duplicates():
    """检查交易日历是否仍存在重复 trade_date。"""
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "galaxy")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")

    db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    engine = create_engine(db_url)

    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT trade_date, COUNT(*) FROM trading_calendar GROUP BY trade_date HAVING COUNT(*) > 1 ORDER BY trade_date;"
            )
        )
        duplicate_rows = result.fetchall()
        print(f"发现 {len(duplicate_rows)} 个重复的交易日历日期:")
        for trade_date, count in duplicate_rows:
            print(f"  {trade_date} - {count} 次")

        result = conn.execute(
            text(
                "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'trading_calendar'::regclass ORDER BY conname;"
            )
        )
        constraints = result.fetchall()
        print("\ntrading_calendar 约束:")
        for name, definition in constraints:
            print(f"  {name}: {definition}")

        result = conn.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'kline_month' ORDER BY ordinal_position;"
            )
        )
        columns = result.fetchall()
        print("\nkline_month 表的列结构:")
        for column_name, data_type in columns:
            print(f"  {column_name}: {data_type}")


if __name__ == "__main__":
    check_trading_calendar_duplicates()
