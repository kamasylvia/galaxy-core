#!/usr/bin/env python3
"""
检查交易日历表中的重复日期问题
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()


def check_trading_calendar_duplicates():
    """检查交易日历表中的重复日期"""

    # 从环境变量加载数据库配置
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "galaxy")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")

    # 构建 PostgreSQL 数据库 URL
    db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    engine = create_engine(db_url)

    with engine.connect() as conn:
        # 检查交易日历表中的重复日期
        result = conn.execute(
            text(
                "SELECT trade_date, market, COUNT(*) FROM trading_calendar GROUP BY trade_date, market HAVING COUNT(*) > 1 ORDER BY trade_date;"
            )
        )
        duplicate_rows = result.fetchall()
        print(f"发现 {len(duplicate_rows)} 个重复的交易日历记录:")
        for row in duplicate_rows:
            print(f"  {row[0]} - {row[1]} - {row[2]} 次")

        # 检查不同market写法的数量
        result = conn.execute(
            text(
                "SELECT market, COUNT(*) FROM trading_calendar GROUP BY market ORDER BY COUNT(*) DESC;"
            )
        )
        market_counts = result.fetchall()
        print(f"\nMarket字段的不同写法及数量:")
        for row in market_counts:
            print(f"  {row[0]}: {row[1]}")

        # 检查kline_month表的列结构
        result = conn.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'kline_month' ORDER BY ordinal_position;"
            )
        )
        columns = result.fetchall()
        print(f"\nkline_month表的列结构:")
        for col in columns:
            print(f"  {col[0]}: {col[1]}")


if __name__ == "__main__":
    check_trading_calendar_duplicates()
