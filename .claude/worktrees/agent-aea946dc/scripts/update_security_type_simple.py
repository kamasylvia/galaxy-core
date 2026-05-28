#!/usr/bin/env python3
"""
更新数据库中已有数据的 security_type 脚本（简化版）

此脚本将遍历所有 K 线表，根据证券代码更新其 security_type 字段，
以修正之前可能错误的类型标识。
"""

import sys
import os
from typing import Dict, Type
from sqlalchemy import (
    create_engine,
    inspect,
    func,
    String,
    Integer,
    Float,
    BigInteger,
    DateTime,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import re


def infer_security_type_simple(symbol: str) -> str:
    """
    简化版证券代码类型推断函数，不依赖复杂导入
    """
    symbol = symbol.strip()

    # 分离代码和后缀
    if "." in symbol:
        code_part, suffix_part = symbol.rsplit(".", 1)

        # 处理6位数字代码
        if len(code_part) == 6 and code_part.isdigit():
            prefix = code_part[:2]

            # ETF 代码段
            if prefix in {"50", "51", "52", "53", "55", "56", "15", "16", "58"}:
                if suffix_part.upper() == "SH":
                    if prefix in {"50", "51", "58"}:
                        return "SH_ETF"
                    else:
                        return "SH_ETF"
                elif suffix_part.upper() == "SZ":
                    if prefix in {"15", "16"}:
                        return "SZ_ETF"
                    else:
                        return "SZ_ETF"
                elif suffix_part.upper() == "BJ":
                    return "BJ_A"  # 北交所ETF实际上属于股票类别

            # 指数代码段（通常以000或399开头）
            elif code_part.startswith("000") or code_part.startswith("399"):
                if suffix_part.upper() == "SH":
                    return "SH_INDEX"
                elif suffix_part.upper() == "SZ":
                    return "SZ_INDEX"
                elif suffix_part.upper() == "BJ":
                    return "BJ_INDEX"

            # 可转债代码段
            elif prefix in {"11", "12"}:
                if suffix_part.upper() == "SH":
                    return "SH_KZZ"
                elif suffix_part.upper() == "SZ":
                    return "SZ_KZZ"
                elif suffix_part.upper() == "BJ":
                    return "BJ_A"  # 北交所可转债

            # 港股通代码段（暂时简化处理）
            elif code_part.startswith("90"):
                if suffix_part.upper() == "SH":
                    return "SH_HKT"
                elif suffix_part.upper() == "SZ":
                    return "SZ_HKT"

            # 股票代码段
            else:
                if suffix_part.upper() == "SH":
                    return "SH_A"
                elif suffix_part.upper() == "SZ":
                    return "SZ_A"
                elif suffix_part.upper() == "BJ":
                    return "BJ_A"

        # 处理期货代码
        elif suffix_part.upper() == "FUTURE":
            # 期货代码通常为字母+数字，如 IF2403, cu2403
            # 根据代码前缀进一步细化期货类型
            if code_part.upper().startswith(("IF", "IC", "IM", "IH")):  # 中金所股指期货
                return "ZJ_FUTURE"
            elif code_part.upper().startswith(
                (
                    "CU",
                    "AL",
                    "ZN",
                    "PB",
                    "NI",
                    "SN",
                    "RB",
                    "WR",
                    "HC",
                    "BU",
                    "RU",
                    "FU",
                    "SC",
                    "NR",
                    "LU",
                    "SS",
                    "AO",
                    "EB",
                )
            ):  # 上期所
                return "SQ_FUTURE"
            elif code_part.upper().startswith(
                (
                    "M",
                    "Y",
                    "A",
                    "B",
                    "P",
                    "C",
                    "CS",
                    "JD",
                    "FB",
                    "LH",
                    "RR",
                    "PG",
                    "PP",
                    "V",
                    "EB",
                    "EG",
                    "I",
                    "J",
                    "JM",
                    "SG",
                    "SM",
                    "SP",
                )
            ):  # 大商所
                return "DS_FUTURE"
            elif code_part.upper().startswith(
                (
                    "CF",
                    "CY",
                    "SR",
                    "TA",
                    "MA",
                    "FG",
                    "SA",
                    "UR",
                    "AP",
                    "CJ",
                    "PK",
                    "RI",
                    "PM",
                    "WH",
                    "LR",
                    "SF",
                    "SH",
                    "LC",
                    "RO",
                    "RS",
                    "OI",
                    "RM",
                    "ZC",
                    "QA",
                    "JR",
                    "LR",
                    "SF",
                    "SM",
                )
            ):  # 郑商所
                return "ZS_FUTURE"
            elif code_part.upper().startswith(
                ("SC", "NR", "LU", "BC")
            ):  # 上海国际能源交易中心
                return "SN_FUTURE"
            else:
                return "EXTRA_FUTURE"

        # 处理期权代码
        elif suffix_part.upper() == "OPTION":
            # 期权代码通常为数字，如 10003737
            # 根据代码前缀进一步细化期权类型
            # 上海证券交易所期权代码通常以10、11、12、13、15、16、18、51、58开头
            # 深圳证券交易所期权代码通常以00、03、04、30、39开头
            if code_part.startswith(
                ("10", "11", "12", "13", "15", "16", "18", "51", "58")
            ):
                return "SH_OPTION"  # 上交所期权
            elif code_part.startswith(("00", "03", "04", "30", "39")):
                return "SZ_OPTION"  # 深交所期权
            else:
                return "EXTRA_ETF_OP"  # 其他期权

    # 对于没有后缀的6位数字代码，根据前缀推断
    elif len(symbol) == 6 and symbol.isdigit():
        prefix = symbol[:2]

        # ETF 代码段
        if prefix in {"50", "51", "15", "16", "58"}:
            return "EXTRA_ETF"  # 需要额外API调用才能确定具体交易所

        # 指数代码段
        elif symbol.startswith("000") or symbol.startswith("399"):
            return "EXTRA_INDEX_A_SH_SZ"  # 需要额外API调用才能确定具体交易所

        # 可转债代码段
        elif prefix in {"11", "12"}:
            return "EXTRA_KZZ"  # 需要额外API调用才能确定具体交易所

        # 股票代码段
        else:
            return "EXTRA_STOCK_A_SH_SZ"  # 需要额外API调用才能确定具体交易所

    # 如果无法推断，返回 None
    return None


def get_db_connection():
    """获取数据库连接"""
    # 从环境变量加载数据库配置
    import os
    from dotenv import load_dotenv

    load_dotenv()  # 加载 .env 文件

    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "galaxy")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")

    # 构建 PostgreSQL 数据库 URL
    db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, SessionLocal


def update_security_types():
    """更新数据库中所有表的 security_type 字段"""

    engine, SessionLocal = get_db_connection()

    # 预定义的K线表名
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

    print(f"开始更新 {len(kline_tables)} 个K线表的 security_type...")

    total_updated = 0

    for table_name in kline_tables:
        print(f"\n正在处理表: {table_name}")

        try:
            # 检查表是否存在（PostgreSQL）
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        f"SELECT tablename FROM pg_tables WHERE tablename = '{table_name}';"
                    )
                )
                if not result.fetchone():
                    print(f"  表 {table_name} 不存在，跳过")
                    continue

            with SessionLocal() as session:
                # 计算表中的总记录数
                result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                total_records = result.scalar()
                print(f"  表中共有 {total_records} 条记录")

                # 分批处理记录，避免内存问题
                batch_size = 1000
                offset = 0
                batch_updated = 0

                while True:
                    # 获取一批记录
                    result = session.execute(
                        text(
                            f"SELECT id, symbol, security_type FROM {table_name} LIMIT :limit OFFSET :offset"
                        ),
                        {"limit": batch_size, "offset": offset},
                    )
                    records = result.fetchall()

                    if not records:
                        break

                    # 处理这批记录
                    for record_row in records:
                        record_id, symbol, current_type = record_row

                        # 推断正确的 security_type
                        correct_type = infer_security_type_simple(symbol)

                        # 如果当前的 security_type 与推断的不一致，则更新
                        if current_type != correct_type:
                            old_type = current_type

                            # 执行更新
                            session.execute(
                                text(
                                    f"UPDATE {table_name} SET security_type = :new_type WHERE id = :id"
                                ),
                                {"new_type": correct_type, "id": record_id},
                            )

                            # 打印更新信息（只打印前10个）
                            if batch_updated < 10:
                                print(
                                    f"    更新: {symbol} '{old_type}' -> '{correct_type}'"
                                )
                            elif batch_updated == 10:
                                print(f"    ... (省略更多更新)")

                            batch_updated += 1

                    # 提交当前批次的更改
                    session.commit()

                    print(
                        f"    批次 {offset//batch_size + 1}: 处理了 {len(records)} 条记录"
                    )

                    offset += batch_size

                    # 如果记录数少于批次大小，说明已经处理完所有记录
                    if len(records) < batch_size:
                        break

                print(f"  表 {table_name} 更新完成，共更新 {batch_updated} 条记录")
                total_updated += batch_updated

        except Exception as e:
            print(f"  处理表 {table_name} 时出错: {e}")
            continue

    print(f"\n所有表处理完成！总共更新了 {total_updated} 条记录")

    # 显示更新统计
    print("\n更新统计:")
    with SessionLocal() as session:
        for table_name in kline_tables:
            try:
                # 检查表是否存在（PostgreSQL）
                result = session.execute(
                    text(
                        f"SELECT tablename FROM pg_tables WHERE tablename = '{table_name}';"
                    )
                )
                if not result.fetchone():
                    continue

                # 统计各类 security_type 的数量
                result = session.execute(
                    text(
                        f"SELECT security_type, COUNT(id) FROM {table_name} GROUP BY security_type"
                    )
                )
                rows = result.fetchall()

                print(f"  {table_name}:")
                for sec_type, count in rows:
                    print(f"    {sec_type}: {count}")
            except Exception as e:
                print(f"  读取表 {table_name} 统计信息时出错: {e}")


def preview_changes():
    """预览将要进行的更改"""

    engine, SessionLocal = get_db_connection()

    print("预览将要进行的 security_type 更新:")

    # 只检查一个表作为样本
    sample_table = "kline_day"  # 使用日线表作为样本

    try:
        # 检查表是否存在（PostgreSQL）
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    f"SELECT tablename FROM pg_tables WHERE tablename = '{sample_table}';"
                )
            )
            if not result.fetchone():
                print(f"  表 {sample_table} 不存在")
                return

        with SessionLocal() as session:
            # 获取前100条记录进行预览
            result = session.execute(
                text(f"SELECT symbol, security_type FROM {sample_table} LIMIT 100")
            )
            sample_records = result.fetchall()

            updates_preview = []
            for symbol, current_type in sample_records:
                correct_type = infer_security_type_simple(symbol)
                if current_type != correct_type:
                    updates_preview.append(
                        {
                            "symbol": symbol,
                            "old_type": current_type,
                            "new_type": correct_type,
                        }
                    )

            print(
                f"\n在 {sample_table} 表的前100条记录中，发现 {len(updates_preview)} 个需要更新的记录:"
            )
            for i, update in enumerate(updates_preview[:10]):  # 只显示前10个
                print(
                    f"  {update['symbol']}: '{update['old_type']}' -> '{update['new_type']}'"
                )

            if len(updates_preview) > 10:
                print(f"  ... 还有 {len(updates_preview) - 10} 个需要更新")

            print(f"\n总共在样本中发现 {len(updates_preview)} 个需要更新的记录")

    except Exception as e:
        print(f"预览更改时出错: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--preview":
        preview_changes()
    else:
        print("此脚本将更新数据库中所有K线表的 security_type 字段")
        print("根据最新的 infer_security_type 函数推断正确的类型")

        response = input("\n是否继续? (y/N): ")
        if response.lower() in ["y", "yes"]:
            update_security_types()
        else:
            print("操作已取消")
