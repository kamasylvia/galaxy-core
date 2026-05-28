#!/usr/bin/env python3
"""
标准化交易日历表中的market字段写法
将所有不规范的格式统一为英文代码格式：SSE、SZSE、BSE
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()


def standardize_market_field():
    """标准化交易日历表中的market字段写法"""

    print("开始标准化交易日历表中的market字段...")

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
            # 检查当前的market值分布
            print("\n更新前的Market字段统计:")
            result = conn.execute(
                text(
                    "SELECT market, COUNT(*) FROM trading_calendar GROUP BY market ORDER BY COUNT(*) DESC;"
                )
            )
            market_counts_before = result.fetchall()
            for row in market_counts_before:
                print(f"  {row[0]}: {row[1]}")

            # 定义需要更新的映射关系
            updates = [
                ("上海证券交易所(SSE)", "SSE"),
                ("深圳证券交易所(SZSE)", "SZSE"),
                ("北京证券交易所(BSE)", "BSE"),
                ("SSE_上海证券交易所", "SSE"),
                ("SZSE_深圳证券交易所", "SZSE"),
                ("BSE_北京证券交易所", "BSE"),
            ]

            total_updated = 0

            for old_value, new_value in updates:
                # 检查有多少记录需要更新
                result = conn.execute(
                    text(
                        f"SELECT COUNT(*) FROM trading_calendar WHERE market = :old_value;"
                    ),
                    {"old_value": old_value},
                )
                count_to_update = result.scalar()

                if count_to_update > 0:
                    print(
                        f"\n将 {old_value} 更新为 {new_value}，共 {count_to_update} 条记录"
                    )

                    # 执行更新
                    result = conn.execute(
                        text(
                            f"UPDATE trading_calendar SET market = :new_value WHERE market = :old_value;"
                        ),
                        {"new_value": new_value, "old_value": old_value},
                    )
                    total_updated += result.rowcount
                    print(f"  已更新 {result.rowcount} 条记录")

            if total_updated > 0:
                # 提交事务
                trans.commit()
                print(f"\n事务已提交，总共更新了 {total_updated} 条记录")
            else:
                print("\n没有需要更新的记录")

            # 检查更新后的统计
            print(f"\n更新后的Market字段统计:")
            result = conn.execute(
                text(
                    "SELECT market, COUNT(*) FROM trading_calendar GROUP BY market ORDER BY COUNT(*) DESC;"
                )
            )
            market_counts_after = result.fetchall()
            for row in market_counts_after:
                print(f"  {row[0]}: {row[1]}")

            print("\nMarket字段标准化完成!")

        except Exception as e:
            # 回滚事务
            trans.rollback()
            print(f"发生错误，事务已回滚: {str(e)}")
            raise


if __name__ == "__main__":
    standardize_market_field()
