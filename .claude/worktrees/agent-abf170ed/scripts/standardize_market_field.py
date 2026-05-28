#!/usr/bin/env python3
"""
标准化交易日历表中的market字段写法
将 '上海证券交易所(SSE)' 统一改为 'SSE_上海证券交易所'
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()


def standardize_market_field():
    """标准化交易日历表中的market字段写法"""

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
        # 开启事务
        trans = conn.begin()

        try:
            # 检查需要更新的记录数
            result = conn.execute(
                text(
                    "SELECT COUNT(*) FROM trading_calendar WHERE market = '上海证券交易所(SSE)';"
                )
            )
            count_to_update = result.scalar()
            print(f"需要更新的记录数: {count_to_update}")

            if count_to_update > 0:
                # 更新market字段，将 '上海证券交易所(SSE)' 改为 'SSE_上海证券交易所'
                result = conn.execute(
                    text(
                        "UPDATE trading_calendar SET market = 'SSE_上海证券交易所' WHERE market = '上海证券交易所(SSE)';"
                    )
                )
                print(f"已更新 {result.rowcount} 条记录")

                # 提交事务
                trans.commit()
                print("事务已提交")
            else:
                print("没有需要更新的记录")

            # 检查更新后的统计
            result = conn.execute(
                text(
                    "SELECT market, COUNT(*) FROM trading_calendar GROUP BY market ORDER BY COUNT(*) DESC;"
                )
            )
            market_counts = result.fetchall()
            print(f"\n更新后的Market字段统计:")
            for row in market_counts:
                print(f"  {row[0]}: {row[1]}")

        except Exception as e:
            # 回滚事务
            trans.rollback()
            print(f"发生错误，事务已回滚: {str(e)}")
            raise


if __name__ == "__main__":
    standardize_market_field()
