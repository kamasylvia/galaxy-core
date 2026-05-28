#!/usr/bin/env python3
"""
检查年线表中的security_type分布
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()


def check_year_security_type():
    """检查年线表中的security_type分布"""

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
        # 检查kline_year表中是否存在SH_A类型的记录
        result = conn.execute(
            text(
                "SELECT security_type, COUNT(*) FROM kline_year GROUP BY security_type;"
            )
        )
        year_security_types = result.fetchall()
        print("kline_year表中的security_type分布:")
        for row in year_security_types:
            print(f"  {row[0]}: {row[1]}")

        # 检查是否有SH_A类型的记录
        result = conn.execute(
            text("SELECT COUNT(*) FROM kline_year WHERE security_type = 'SH_A';")
        )
        sh_a_count = result.scalar()
        print(f"\nkline_year表中SH_A类型的记录数: {sh_a_count}")

        if sh_a_count > 0:
            # 显示一些SH_A的样例
            result = conn.execute(
                text(
                    "SELECT symbol, security_type, trade_time FROM kline_year WHERE security_type = 'SH_A' LIMIT 5;"
                )
            )
            samples = result.fetchall()
            print("\nSH_A类型记录样例:")
            for sample in samples:
                print(f"  {sample[0]} - {sample[1]} - {sample[2]}")

        # 检查所有K线表的security_type分布
        tables = [
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

        print("\n所有K线表的security_type分布:")
        for table in tables:
            try:
                result = conn.execute(
                    text(
                        f"SELECT security_type, COUNT(*) FROM {table} GROUP BY security_type;"
                    )
                )
                types = result.fetchall()
                if types:
                    print(f"\n{table}:")
                    for t in types:
                        print(f"  {t[0]}: {t[1]}")
            except Exception as e:
                print(f"  {table}: 无法查询 ({str(e)})")


if __name__ == "__main__":
    check_year_security_type()
