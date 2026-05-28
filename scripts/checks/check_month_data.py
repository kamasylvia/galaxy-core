#!/usr/bin/env python3
"""
检查数据库中ETF月线数据
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()


def check_month_data():
    """检查数据库中ETF月线数据"""

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
        # 检查kline_month表中ETF数据的总体情况
        result = conn.execute(
            text(
                "SELECT COUNT(*) FROM kline_month WHERE security_type IN ('SH_ETF', 'SZ_ETF');"
            )
        )
        count = result.scalar()
        print(f"kline_month表中ETF类型的记录总数: {count}")

        # 检查最近几个月的数据
        result = conn.execute(
            text(
                "SELECT MAX(date) FROM kline_month WHERE security_type IN ('SH_ETF', 'SZ_ETF');"
            )
        )
        max_date = result.scalar()
        print(f"kline_month表中ETF数据的最新日期: {max_date}")

        # 检查kline_month表中EXTRA_ETF数据
        result = conn.execute(
            text("SELECT COUNT(*) FROM kline_month WHERE security_type = 'EXTRA_ETF';")
        )
        extra_count = result.scalar()
        print(f"kline_month表中EXTRA_ETF类型的记录数: {extra_count}")

        # 检查159003.SZ这个成功同步的代码的数据
        result = conn.execute(
            text(
                "SELECT date, open, high, low, close, volume, amount FROM kline_month WHERE symbol = '159003.SZ' ORDER BY date DESC LIMIT 10;"
            )
        )
        rows = result.fetchall()
        print("\n159003.SZ 月线数据 (最近10条):")
        for row in rows:
            print(
                f"  {row[0]}: O={row[1]}, H={row[2]}, L={row[3]}, C={row[4]}, V={row[5]}, A={row[6]}"
            )

        # 检查kline_month表总记录数
        result = conn.execute(text("SELECT COUNT(*) FROM kline_month;"))
        total_count = result.scalar()
        print(f"\nkline_month表总记录数: {total_count}")

        # 检查不同security_type的分布
        result = conn.execute(
            text(
                "SELECT security_type, COUNT(*) FROM kline_month GROUP BY security_type;"
            )
        )
        rows = result.fetchall()
        print("\nkline_month表中security_type分布:")
        for row in rows:
            print(f"  {row[0]}: {row[1]}")


if __name__ == "__main__":
    check_month_data()
