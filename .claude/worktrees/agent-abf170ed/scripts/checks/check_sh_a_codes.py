#!/usr/bin/env python3
"""
检查数据库中被错误标记为SH_A类型的证券代码
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

from galaxy_db_bridge.database.core.connection import db_manager
from galaxy_db_bridge.database.models.kline import KlineMonth, KlineYear, KlineDay
from galaxy_db_bridge.shared_kernel.utils.symbol_validator import infer_security_type


def check_sh_a_codes():
    """检查被错误标记为SH_A类型的证券代码"""

    db_manager.initialize()

    print("检查数据库中被标记为SH_A的证券代码...")

    # 检查月线表中SH_A类型的证券代码
    with db_manager.session() as session:
        sh_a_month = (
            session.query(KlineMonth.symbol)
            .filter(KlineMonth.security_type == "SH_A")
            .distinct()
            .all()
        )
        print(f"\n月线表中被标记为SH_A的证券代码总数: {len(sh_a_month)}")

        incorrect_month = []
        for code_tuple in sh_a_month:
            code = code_tuple[0]
            inferred_type = infer_security_type(code)
            if inferred_type != "SH_A":
                incorrect_month.append((code, inferred_type))

        print(f"月线表中推断类型与SH_A不一致的代码数量: {len(incorrect_month)}")
        for code, inferred_type in incorrect_month[:20]:  # 显示前20个
            print(f"  {code} -> 推断类型: {inferred_type}")
        if len(incorrect_month) > 20:
            print(f"  ... 还有 {len(incorrect_month) - 20} 个")

    print()

    # 检查年线表中SH_A类型的证券代码
    with db_manager.session() as session:
        sh_a_year = (
            session.query(KlineYear.symbol)
            .filter(KlineYear.security_type == "SH_A")
            .distinct()
            .all()
        )
        print(f"年线表中被标记为SH_A的证券代码总数: {len(sh_a_year)}")

        incorrect_year = []
        for code_tuple in sh_a_year:
            code = code_tuple[0]
            inferred_type = infer_security_type(code)
            if inferred_type != "SH_A":
                incorrect_year.append((code, inferred_type))

        print(f"年线表中推断类型与SH_A不一致的代码数量: {len(incorrect_year)}")
        for code, inferred_type in incorrect_year[:20]:  # 显示前20个
            print(f"  {code} -> 推断类型: {inferred_type}")
        if len(incorrect_year) > 20:
            print(f"  ... 还有 {len(incorrect_year) - 20} 个")

    print()

    # 检查日线表中SH_A类型的证券代码
    with db_manager.session() as session:
        sh_a_day = (
            session.query(KlineDay.symbol)
            .filter(KlineDay.security_type == "SH_A")
            .distinct()
            .all()
        )
        print(f"日线表中被标记为SH_A的证券代码总数: {len(sh_a_day)}")

        incorrect_day = []
        for code_tuple in sh_a_day:
            code = code_tuple[0]
            inferred_type = infer_security_type(code)
            if inferred_type != "SH_A":
                incorrect_day.append((code, inferred_type))

        print(f"日线表中推断类型与SH_A不一致的代码数量: {len(incorrect_day)}")
        for code, inferred_type in incorrect_day[:20]:  # 显示前20个
            print(f"  {code} -> 推断类型: {inferred_type}")
        if len(incorrect_day) > 20:
            print(f"  ... 还有 {len(incorrect_day) - 20} 个")


if __name__ == "__main__":
    check_sh_a_codes()
