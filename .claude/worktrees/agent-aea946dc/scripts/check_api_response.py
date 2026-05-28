"""检查 API 返回的 DataFrame 结构."""

from galaxy_db_sync.amazing_data.api.client import amazing_data_client
import logging

logging.basicConfig(level=logging.INFO)

# 查询单个 ETF 的数据
result = amazing_data_client.query_kline(
    code_list=['510330.SH'],
    begin_date=20250101,
    end_date=20250131,
    interval=10008,  # day
)

for symbol, df in result.items():
    print(f"Symbol: {symbol}")
    print(f"Type: {type(df)}")
    if df is not None and not df.empty:
        print(f"Shape: {df.shape}")
        print(f"Columns: {df.columns.tolist()}")
        print(f"Index type: {type(df.index)}")
        print(f"Index values: {df.index[:5].tolist()}")
        print(f"\nFirst few rows:")
        print(df.head())
    else:
        print("Empty or None")
