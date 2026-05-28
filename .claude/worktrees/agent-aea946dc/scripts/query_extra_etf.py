#!/usr/bin/env python3
"""
查询数据库中EXTRA_ETF类型的证券代码
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()


def query_extra_etf_codes():
    """查询数据库中EXTRA_ETF类型的证券代码"""

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
        print("查询EXTRA_ETF类型的证券代码...")

        # 查找security_type为EXTRA_ETF的证券代码
        result = conn.execute(
            text(
                "SELECT DISTINCT symbol FROM kline_day WHERE security_type = 'EXTRA_ETF' LIMIT 20;"
            )
        )
        rows = result.fetchall()

        if rows:
            print("EXTRA_ETF类型的证券代码:")
            for row in rows:
                print(f"  {row[0]}")
        else:
            print("未找到EXTRA_ETF类型的证券代码")

        print("\n检查kline_month表...")
        # 检查是否存在月线数据表
        result = conn.execute(
            text("SELECT tablename FROM pg_tables WHERE tablename = 'kline_month';")
        )
        if result.fetchone():
            print("kline_month表存在")

            # 检查EXTRA_ETF在月线表中的记录数量
            result = conn.execute(
                text(
                    "SELECT COUNT(*) FROM kline_month WHERE security_type = 'EXTRA_ETF';"
                )
            )
            count = result.scalar()
            print(f"kline_month表中EXTRA_ETF类型的记录数: {count}")

            # 检查月线表中是否有任何数据
            result = conn.execute(text("SELECT COUNT(*) FROM kline_month;"))
            total_count = result.scalar()
            print(f"kline_month表中总记录数: {total_count}")
        else:
            print("kline_month表不存在")

        print("\n检查所有K线表的存在情况...")
        # 检查所有K线表
        kline_tables = [
            "kline_min1",
            "kline_min3",
            "kline_min5",
            "kline_min10",
            "kline_min15",
            "kline_min30",
            "kline_min60",
            "kline_min120",
            "kline_day",
            "kline_week",
            "kline_month",
            "kline_season",
            "kline_year",
        ]

        for table in kline_tables:
            result = conn.execute(
                text(f"SELECT tablename FROM pg_tables WHERE tablename = '{table}';")
            )
            exists = bool(result.fetchone())
            print(f'  {table}: {"存在" if exists else "不存在"}')


if __name__ == "__main__":
    query_extra_etf_codes()
