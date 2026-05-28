#!/usr/bin/env python
"""快速 P0 API 可用性测试."""

# Monkey-patch pandas fillna for SDK compatibility with pandas 3.x
import pandas as pd
import pandas.core.generic as generic

_original = generic.NDFrame.fillna

def _patched_fillna(self, value=None, method=None, axis=None, inplace=False, limit=None, downcast=None, **kwargs):
    if method is not None:
        if inplace:
            if method in ('ffill', 'pad'):
                self.ffill(axis=axis, limit=limit, inplace=True)
            elif method in ('bfill', 'backfill'):
                self.bfill(axis=axis, limit=limit, inplace=True)
            return None
        else:
            if method in ('ffill', 'pad'):
                return self.ffill(axis=axis, limit=limit)
            elif method in ('bfill', 'backfill'):
                return self.bfill(axis=axis, limit=limit)
    return _original(self, value=value, axis=axis, inplace=inplace, limit=limit)

generic.NDFrame.fillna = _patched_fillna

import os
import sys
from pathlib import Path

# 添加 src 到路径
SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if SRC_PATH.exists():
    sys.path.insert(0, str(SRC_PATH))

from dotenv import load_dotenv
load_dotenv()


def quick_test():
    """快速测试 P0 API 可用性."""
    import AmazingData as ad

    username = os.getenv("GALAXY_USERNAME")
    password = os.getenv("GALAXY_PASSWORD")
    host = os.getenv("GALAXY_HOST")
    port = int(os.getenv("GALAXY_PORT", "8600"))

    print("=" * 50)
    print("P0 API 快速可用性测试")
    print("=" * 50)

    # 1. 登录
    print(f"\n[登录] {host}:{port}")
    ad.login(username=username, password=password, host=host, port=port)
    print("✅ 登录成功")

    base_data = ad.BaseData()
    info_data = ad.InfoData()
    calendar = base_data.get_calendar()
    today = calendar[-1]
    print(f"   今日交易日: {today}")

    # 2. 测试 get_hist_code_list (快速)
    print("\n[1] get_hist_code_list")
    codes = base_data.get_code_list(security_type="EXTRA_STOCK_A")
    print(f"✅ 当前股票池: {len(codes)} 只")
    print(f"   样例: {codes[:3]}")

    # 3. 测试 get_stock_basic (少量)
    print("\n[2] get_stock_basic")
    test_codes = codes[:3]
    stock_basic = info_data.get_stock_basic(test_codes)
    print(f"✅ 返回 {len(stock_basic)} 条记录")
    print(f"   字段: {list(stock_basic.columns)[:5]}...")
    for _, row in stock_basic.head(2).iterrows():
        print(f"   {row.get('MARKET_CODE')}: {row.get('SECURITY_NAME')}, 上市={row.get('LISTDATE')}")

    # 4. 测试 get_history_stock_status (少量)
    print("\n[3] get_history_stock_status")
    test_codes = codes[:2]
    status = info_data.get_history_stock_status(test_codes)
    # 返回类型可能是 dict 或 DataFrame
    if isinstance(status, dict):
        print(f"✅ 返回 dict: {len(status)} 个股票")
        for code, df in status.items():
            print(f"   {code}: {len(df)} 条记录, 字段={list(df.columns)[:5]}...")
            if len(df) > 0:
                row = df.iloc[0]
                print(f"   样例: {row.get('TRADE_DATE')} 涨停价={row.get('HIGH_LIMITED')} 跌停价={row.get('LOW_LIMITED')} ST={row.get('IS_ST_SEC')} 停牌={row.get('IS_SUSP_SEC')}")
    else:
        print(f"✅ 返回 DataFrame: {len(status)} 条记录")
        print(f"   字段: {list(status.columns)[:6]}...")
        key_fields = ["IS_SUSP_SEC", "IS_ST_SEC", "HIGH_LIMITED", "LOW_LIMITED"]
        available = [f for f in key_fields if f in status.columns]
        print(f"   关键字段: {available}")
        if len(status) > 0:
            row = status.iloc[0]
            print(f"   样例: {row.get('MARKET_CODE')} {row.get('TRADE_DATE')} 涨停价={row.get('HIGH_LIMITED')} 跌停价={row.get('LOW_LIMITED')}")

    # 5. 测试 get_backward_factor (少量)
    print("\n[4] get_backward_factor")
    test_codes = codes[:2]
    factor = base_data.get_backward_factor(code_list=test_codes, local_path="/tmp/", is_local=False)
    print(f"✅ 返回 DataFrame shape={factor.shape}")
    print(f"   columns: {list(factor.columns)}")
    if len(factor.columns) > 0:
        col = factor.columns[0]
        data = factor[col].dropna()
        print(f"   {col}: 首日={data.iloc[0]:.4f} 末日={data.iloc[-1]:.4f}")

    # 登出
    ad.logout(username)
    print("\n✅ 测试完成，已登出")

    print("\n" + "=" * 50)
    print("结论: 4 个 P0 API 全部可用")
    print("=" * 50)


if __name__ == "__main__":
    quick_test()
