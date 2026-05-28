#!/usr/bin/env python3
"""直接更新数据库中market字段的长度"""

import psycopg2
from psycopg2 import sql
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def update_market_field_length():
    """更新market字段长度"""
    # 从环境变量获取数据库连接信息，如果不存在则使用默认值
    host = os.getenv("DB_HOST", "qnap.elf-balance.ts.net")
    port = os.getenv("DB_PORT", "5433")
    database = os.getenv("DB_NAME", "galaxy")
    user = os.getenv("DB_USER", "kama")
    password = os.getenv("DB_PASSWORD", "kama")  # 请注意：生产环境中不应硬编码密码

    try:
        # 连接到数据库
        print(f"正在连接到数据库 {host}:{port}/{database} ...")
        conn = psycopg2.connect(
            host=host, port=port, database=database, user=user, password=password
        )

        # 创建游标
        cur = conn.cursor()

        # 更新字段长度
        alter_query = """
        ALTER TABLE trading_calendar
        ALTER COLUMN market TYPE VARCHAR(50);
        """

        print("正在执行字段长度更新...")
        cur.execute(alter_query)

        # 提交更改
        conn.commit()

        print("字段长度更新成功！")

        # 关闭游标和连接
        cur.close()
        conn.close()

    except psycopg2.Error as e:
        print(f"数据库错误: {e}")
        if "conn" in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        print(f"发生错误: {e}")
        if "conn" in locals():
            conn.rollback()
            conn.close()


if __name__ == "__main__":
    update_market_field_length()
