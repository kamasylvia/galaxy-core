#!/usr/bin/env python3
"""
同步EXTRA_ETF的月线数据（202501-202505）
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()


def get_etf_codes():
    """获取数据库中的ETF代码"""

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
        # 查找所有ETF类型的证券代码（包括SH_ETF、SZ_ETF和EXTRA_ETF）
        result = conn.execute(text("""
            SELECT DISTINCT symbol
            FROM kline_day
            WHERE security_type IN ('SH_ETF', 'SZ_ETF', 'EXTRA_ETF')
            LIMIT 50;
        """))
        rows = result.fetchall()

        etf_codes = [row[0] for row in rows]
        print(f"找到 {len(etf_codes)} 个ETF代码:")
        for code in etf_codes:
            print(f"  {code}")

        return etf_codes


def main():
    print("开始同步ETF的月线数据...")

    # 获取ETF代码
    etf_codes = get_etf_codes()

    if not etf_codes:
        print("未找到任何ETF代码，退出。")
        return

    print(f"\n将同步 {len(etf_codes)} 个ETF代码的月线数据（202501-202505）")

    # 将ETF代码列表转换为命令行参数格式
    codes_str = "[" + ",".join(etf_codes) + "]"

    # 构建并执行同步命令
    cmd = f".venv/bin/python -m galaxy_db_bridge kline '{codes_str}' --interval month --start 202501 --end 202505"
    print(f"执行命令: {cmd}")

    # 执行命令
    exit_code = os.system(cmd)

    if exit_code == 0:
        print("ETF月线数据同步完成！")
    else:
        print(f"同步过程中出现错误，退出码: {exit_code}")


if __name__ == "__main__":
    main()
