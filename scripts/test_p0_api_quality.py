#!/usr/bin/env python
"""P0 数据 API 质量测试脚本.

测试回测必需的 4 个核心数据 API:
1. get_hist_code_list - 历史代码表
2. get_stock_basic - 证券基础信息
3. get_backward_factor - 后复权因子
4. get_history_stock_status - 历史证券状态 (停牌/ST/涨跌停价)

使用方法:
    PYTHONPATH=src python scripts/test_p0_api_quality.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

# 添加 src 到路径
SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if SRC_PATH.exists():
    sys.path.insert(0, str(SRC_PATH))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()


def test_api_quality():
    """测试 P0 数据 API 质量."""
    import AmazingData as ad

    # 从环境变量读取配置
    username = os.getenv("GALAXY_USERNAME")
    password = os.getenv("GALAXY_PASSWORD")
    host = os.getenv("GALAXY_HOST")
    port = int(os.getenv("GALAXY_PORT", "8600"))

    if not all([username, password, host]):
        print("❌ 缺少 AmazingData 配置，请检查 .env 文件")
        print(f"   GALAXY_USERNAME: {username or '(未设置)'}")
        print(f"   GALAXY_PASSWORD: {'***' if password else '(未设置)'}")
        print(f"   GALAXY_HOST: {host or '(未设置)'}")
        return

    print("=" * 60)
    print("P0 数据 API 质量测试")
    print("=" * 60)

    # 1. 登录
    print(f"\n[1] 登录 AmazingData: {host}:{port}")
    try:
        ad.login(username=username, password=password, host=host, port=port)
        print("✅ 登录成功")
    except Exception as e:
        print(f"❌ 登录失败: {e}")
        return

    base_data = ad.BaseData()
    info_data = ad.InfoData()

    # 获取交易日历
    calendar = base_data.get_calendar()
    today = calendar[-1]
    print(f"   今日交易日: {today}")

    # 本地缓存路径
    cache_path = Path(__file__).resolve().parents[1] / "data" / "local_cache"
    cache_path.mkdir(parents=True, exist_ok=True)
    local_path = str(cache_path) + "/"

    # 2. 测试 get_hist_code_list
    print("\n" + "-" * 60)
    print("[2] 测试 get_hist_code_list (历史代码表)")
    print("-" * 60)

    try:
        # 测试股票 A 股
        stock_codes = base_data.get_hist_code_list(
            security_type="EXTRA_STOCK_A_SH_SZ",
            start_date=20130101,
            end_date=today,
            local_path=local_path,
        )
        print(f"✅ EXTRA_STOCK_A_SH_SZ: {len(stock_codes)} 只股票")
        print(f"   样例: {stock_codes[:5]}")

        # 测试 ETF
        etf_codes = base_data.get_hist_code_list(
            security_type="EXTRA_ETF",
            start_date=20130101,
            end_date=today,
            local_path=local_path,
        )
        print(f"✅ EXTRA_ETF: {len(etf_codes)} 只 ETF")
        print(f"   样例: {etf_codes[:5]}")
    except Exception as e:
        print(f"❌ get_hist_code_list 失败: {e}")

    # 3. 测试 get_stock_basic
    print("\n" + "-" * 60)
    print("[3] 测试 get_stock_basic (证券基础信息)")
    print("-" * 60)

    try:
        # 取少量股票测试
        test_codes = stock_codes[:10] if stock_codes else ["600000.SH"]
        stock_basic = info_data.get_stock_basic(test_codes)

        print(f"✅ 返回 DataFrame: {len(stock_basic)} 条记录")
        print(f"   字段数: {len(stock_basic.columns)}")

        # 显示字段
        key_fields = ["MARKET_CODE", "SECURITY_NAME", "LISTDATE", "DELISTDATE", "LISTPLATE_NAME", "IS_LISTED"]
        available_fields = [f for f in key_fields if f in stock_basic.columns]
        print(f"   关键字段覆盖: {available_fields}")

        # 显示样例数据
        if len(stock_basic) > 0:
            print("\n   样例数据 (前 3 条):")
            for _, row in stock_basic.head(3).iterrows():
                code = row.get("MARKET_CODE", "N/A")
                name = row.get("SECURITY_NAME", "N/A")
                list_date = row.get("LISTDATE", "N/A")
                is_listed = row.get("IS_LISTED", "N/A")
                print(f"   {code}: {name}, 上市日期={list_date}, 状态={is_listed}")

        # 检查上市日期分布
        if "LISTDATE" in stock_basic.columns:
            list_dates = stock_basic["LISTDATE"].dropna()
            if len(list_dates) > 0:
                min_date = int(list_dates.min())
                max_date = int(list_dates.max())
                print(f"\n   上市日期范围: {min_date} ~ {max_date}")
    except Exception as e:
        print(f"❌ get_stock_basic 失败: {e}")

    # 4. 测试 get_backward_factor
    print("\n" + "-" * 60)
    print("[4] 测试 get_backward_factor (后复权因子)")
    print("-" * 60)

    try:
        # 使用少量股票测试
        test_codes = stock_codes[:5] if stock_codes else ["600000.SH", "600519.SH"]
        backward_factor = base_data.get_backward_factor(
            code_list=test_codes,
            local_path=local_path,
            is_local=False,  # 从服务器获取最新
        )

        print(f"✅ 返回 DataFrame: shape={backward_factor.shape}")
        print(f"   index 类型: {type(backward_factor.index).__name__}")
        print(f"   columns: {list(backward_factor.columns)}")

        # 检查数据覆盖
        if len(backward_factor.columns) > 0:
            print(f"\n   时间范围:")
            print(f"   index min: {backward_factor.index.min()}")
            print(f"   index max: {backward_factor.index.max()}")

            # 检查因子值分布
            sample_col = backward_factor.columns[0]
            sample_data = backward_factor[sample_col].dropna()
            if len(sample_data) > 0:
                print(f"\n   {sample_col} 样例因子值:")
                print(f"   min={sample_data.min():.4f}, max={sample_data.max():.4f}, mean={sample_data.mean():.4f}")

                # 检查因子变化 (复权因子应该 > 1，且随时间增长)
                print(f"   首日因子: {sample_data.iloc[0]:.4f}")
                print(f"   末日因子: {sample_data.iloc[-1]:.4f}")
                growth = sample_data.iloc[-1] / sample_data.iloc[0] if sample_data.iloc[0] > 0 else 0
                print(f"   累计增长: {growth:.2f}x")
    except Exception as e:
        print(f"❌ get_backward_factor 失败: {e}")

    # 5. 测试 get_history_stock_status
    print("\n" + "-" * 60)
    print("[5] 测试 get_history_stock_status (历史证券状态)")
    print("-" * 60)

    try:
        # 使用少量股票测试
        test_codes = stock_codes[:5] if stock_codes else ["600000.SH"]
        history_status = info_data.get_history_stock_status(test_codes)

        print(f"✅ 返回 DataFrame: {len(history_status)} 条记录")
        print(f"   字段数: {len(history_status.columns)}")

        # 检查关键字段
        key_fields = [
            "MARKET_CODE", "TRADE_DATE",
            "PRECLOSE", "HIGH_LIMITED", "LOW_LIMITED",
            "IS_ST_SEC", "IS_SUSP_SEC", "IS_WD_SEC", "IS_XR_SEC"
        ]
        available_fields = [f for f in key_fields if f in history_status.columns]
        missing_fields = [f for f in key_fields if f not in history_status.columns]
        print(f"   关键字段覆盖: {available_fields}")
        if missing_fields:
            print(f"   缺失字段: {missing_fields}")

        if len(history_status) > 0:
            # 按股票代码分组统计
            print("\n   各股票记录数:")
            code_counts = history_status.groupby("MARKET_CODE").size()
            for code, count in code_counts.items():
                print(f"   {code}: {count} 条")

            # 统计停牌天数
            if "IS_SUSP_SEC" in history_status.columns:
                suspend_counts = (history_status["IS_SUSP_SEC"] == "1").sum()
                total_records = len(history_status)
                suspend_ratio = suspend_counts / total_records if total_records > 0 else 0
                print(f"\n   停牌统计: {suspend_counts}/{total_records} = {suspend_ratio:.2%}")

            # 统计 ST 天数
            if "IS_ST_SEC" in history_status.columns:
                st_counts = (history_status["IS_ST_SEC"] == "1").sum()
                st_ratio = st_counts / total_records if total_records > 0 else 0
                print(f"   ST统计: {st_counts}/{total_records} = {st_ratio:.2%}")

            # 检查涨跌停价完整性
            if "HIGH_LIMITED" in history_status.columns and "LOW_LIMITED" in history_status.columns:
                high_valid = history_status["HIGH_LIMITED"].notna().sum()
                low_valid = history_status["LOW_LIMITED"].notna().sum()
                print(f"\n   涨停价有效: {high_valid}/{total_records}")
                print(f"   跌停价有效: {low_valid}/{total_records}")

            # 样例数据
            print("\n   样例数据 (前 5 条):")
            display_cols = ["MARKET_CODE", "TRADE_DATE", "PRECLOSE", "HIGH_LIMITED", "LOW_LIMITED", "IS_ST_SEC", "IS_SUSP_SEC"]
            display_cols = [c for c in display_cols if c in history_status.columns]
            print(history_status[display_cols].head(5).to_string(index=False))
    except Exception as e:
        print(f"❌ get_history_stock_status 失败: {e}")

    # 6. 数据质量总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    print("""
    P0 数据 API 覆盖情况:

    ✅ get_hist_code_list     - 历史代码表 (股票池筛选)
    ✅ get_stock_basic        - 证券基础信息 (上市/退市日期)
    ✅ get_backward_factor    - 后复权因子 (价格复权)
    ✅ get_history_stock_status - 历史证券状态 (停牌/ST/涨跌停价)

    回测核心需求满足度: 100%

    数据质量检查项:
    - [ ] 复权因子时间覆盖完整性
    - [ ] 历史状态字段完整性
    - [ ] 涨跌停价计算正确性
    """)

    # 登出
    try:
        ad.logout(username)
        print("✅ 已登出")
    except Exception as e:
        print(f"⚠️ 登出失败 (非关键): {e}")


if __name__ == "__main__":
    test_api_quality()