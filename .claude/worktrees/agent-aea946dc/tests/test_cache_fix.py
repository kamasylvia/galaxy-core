import pytest

pytest.skip("manual integration script requiring external database", allow_module_level=True)

import os
from datetime import date
from src.galaxy_db_sync.database.core.connection import init_database
from src.galaxy_db_sync.database.services.trading_calendar import trading_calendar_service

# 设置环境变量（使用示例值，实际环境中应从 .env 文件加载）
os.environ.setdefault('DB_HOST', 'qnap.elf-balance.ts.net')
os.environ.setdefault('DB_PORT', '5433')
os.environ.setdefault('DB_NAME', 'galaxy')
os.environ.setdefault('DB_USER', 'quant_user')  # 使用更合理的默认用户名
os.environ.setdefault('DB_PASSWORD', '')  # 密码为空或留空

# 初始化数据库
try:
    init_database(create_tables=False)  # 不创建表，仅初始化连接
    print("数据库初始化成功")
except Exception as e:
    print(f"数据库初始化失败: {e}")
    exit(1)

print('测试交易日历缓存功能...')
start_date = date(2016, 1, 1)
end_date = date(2016, 2, 28)

print(f'首次调用: 获取 {start_date} 到 {end_date} 的交易日')
trading_days_1 = trading_calendar_service.get_trading_days(start_date, end_date)
print(f'获取到 {len(trading_days_1)} 个交易日')

print(f'第二次调用: 获取 {start_date} 到 {end_date} 的交易日')
trading_days_2 = trading_calendar_service.get_trading_days(start_date, end_date)
print(f'获取到 {len(trading_days_2)} 个交易日')
print('如果第二次调用没有触发从 akshare 获取数据的日志，说明缓存已生效')
