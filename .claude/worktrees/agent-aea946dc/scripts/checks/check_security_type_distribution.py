#!/usr/bin/env python3
"""
检查数据库中security_type分布的脚本
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# 连接到数据库
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "5432")
db_name = os.getenv("DB_NAME", "galaxy")
db_user = os.getenv("DB_USER", "postgres")
db_password = os.getenv("DB_PASSWORD", "postgres")
db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

engine = create_engine(db_url)

print("检查数据库中security_type分布...")

with engine.connect() as conn:
    # 检查kline_day表是否存在
    result = conn.execute(
        text("SELECT tablename FROM pg_tables WHERE tablename = 'kline_day';")
    )
    if result.fetchone():
        print("\nkline_day表中security_type分布:")

        # 获取所有security_type及其数量
        result = conn.execute(
            text(
                "SELECT security_type, COUNT(*) FROM kline_day GROUP BY security_type ORDER BY COUNT(*) DESC"
            )
        )
        rows = result.fetchall()
        for sec_type, count in rows:
            print(f"  {sec_type}: {count}")

        # 检查是否有SH_A类型的记录（这些应该是ETF但被错误分类的）
        print("\n检查SH_A类型的记录（可能存在错误分类的ETF）:")
        result = conn.execute(
            text(
                "SELECT symbol, COUNT(*) FROM kline_day WHERE security_type = 'SH_A' GROUP BY symbol LIMIT 10"
            )
        )
        rows = result.fetchall()
        for symbol, count in rows:
            print(f"  {symbol}: {count}")

        # 获取一些SH_A类型的样例数据
        if rows:
            print("\nSH_A类型的一些样例数据:")
            result = conn.execute(
                text(
                    "SELECT symbol, security_type FROM kline_day WHERE security_type = 'SH_A' LIMIT 5"
                )
            )
            rows = result.fetchall()
            for symbol, sec_type in rows:
                print(f"  {symbol}: {sec_type}")
    else:
        print("kline_day表不存在")

    print("\n检查所有K线表中的SH_A类型记录...")
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

    for table_name in kline_tables:
        result = conn.execute(
            text(f"SELECT tablename FROM pg_tables WHERE tablename = '{table_name}';")
        )
        if result.fetchone():
            result = conn.execute(
                text(f"SELECT COUNT(*) FROM {table_name} WHERE security_type = 'SH_A'")
            )
            count = result.scalar()
            if count > 0:
                print(f"  {table_name} 表中发现 {count} 条 SH_A 类型记录")

                # 显示一些样例
                sample_result = conn.execute(
                    text(
                        f"SELECT symbol FROM {table_name} WHERE security_type = 'SH_A' LIMIT 3"
                    )
                )
                samples = sample_result.fetchall()
                for sample in samples:
                    print(f"    - {sample[0]}")
