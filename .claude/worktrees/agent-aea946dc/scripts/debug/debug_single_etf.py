#!/usr/bin/env python3
"""
调试单个ETF代码的月线数据获取
"""

import os
import sys
from dotenv import load_dotenv

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

load_dotenv()

def debug_single_etf():
    """调试单个ETF代码的月线数据获取"""

    print("正在连接AmazingData API...")

    # 获取客户端
    from galaxy_db_sync.amazing_data.api.client import amazing_data_client

    # 使用一个具体的ETF代码进行测试
    symbol = "510050.SH"  # 例子：上证50ETF

    print(f"正在获取 {symbol} 在 202501 的月线数据...")

    try:
        # 调用query_kline方法获取月线数据
        # 月线的period值通常是ad.constant.Period.month.value，但我们直接使用数值
        import AmazingData as ad

        # 首先登录
        username = os.getenv('GALAXY_USERNAME')
        password = os.getenv('GALAXY_PASSWORD')
        host = os.getenv('GALAXY_HOST')
        port = int(os.getenv('GALAXY_PORT'))

        print(f"使用账户: {username}, host: {host}:{port}")

        login_result = ad.login(username, password, host, port)
        print(f"登录结果: {login_result}")

        # 获取交易日历
        calendar = ad.BaseData().get_calendar()
        print(f"获取到交易日历，长度: {len(calendar)}")

        # 创建MarketData实例
        market_data = ad.MarketData(calendar)

        # 首先测试get_hist_code_list方法在2025年日期下的行为
        print("测试get_hist_code_list方法...")
        extra_etf_codes = amazing_data_client.get_hist_code_list("EXTRA_ETF", start_date=20250101, end_date=20250531, local_path="./cache/")
        print(f"EXTRA_ETF在2025年1月-5月期间的代码数量: {len(extra_etf_codes)}")
        if extra_etf_codes:
            print(f"前10个代码: {extra_etf_codes[:10]}")

        # 获取 2025 年 1 月的日线数据
        # 从命令模块中获取正确的 interval 值
        from galaxy_db_sync.application.kline.command import (
            IntervalOption,
            get_sdk_interval_value,
        )
        interval_day = get_sdk_interval_value(IntervalOption.DAY)

        print(f"\n使用周期值: {interval_day}")

        kline_dict = market_data.query_kline(
            code_list=[symbol],
            begin_date=20250101,
            end_date=20250131,
            period=interval_day
        )

        print(f"API返回结果类型: {type(kline_dict)}")
        print(f"API返回键: {list(kline_dict.keys()) if isinstance(kline_dict, dict) else 'N/A'}")

        if symbol in kline_dict:
            df = kline_dict[symbol]
            if df is not None and not df.empty:
                print(f"获取到 {symbol} 的数据:")
                print(f"数据形状: {df.shape}")
                print(f"列名: {list(df.columns)}")
                print("数据预览:")
                print(df.head())
            else:
                print(f"{symbol}: API返回空数据")
        else:
            print(f"{symbol}: 未在返回结果中找到")

    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 登出
        try:
            ad.logout(username)
            print("\n已登出")
        except:
            print("\n登出时发生错误")

if __name__ == "__main__":
    debug_single_etf()
