#!/usr/bin/env python3
"""
调试EXTRA_ETF代码列表获取问题
"""

import os
import sys
from dotenv import load_dotenv

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

load_dotenv()

def debug_extra_etf_codes():
    """调试EXTRA_ETF代码列表获取"""

    print("正在连接AmazingData API...")

    # 获取客户端
    from galaxy_db_sync.amazing_data.api.client import amazing_data_client

    print("正在获取EXTRA_ETF代码列表 (20250101 - 20250501)...")

    try:
        code_list = amazing_data_client.get_hist_code_list("EXTRA_ETF", start_date=20250101, end_date=20250501, local_path="./cache/")

        print(f"获取到的代码列表长度: {len(code_list)}")
        print("代码列表:")
        for i, code in enumerate(code_list):
            print(f"  {i+1:3d}. {code}")

    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_extra_etf_codes()
