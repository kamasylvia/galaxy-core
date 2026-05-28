from galaxy_db_sync.shared_kernel.utils import infer_security_type

# 检查52开头的代码
print(f'520990.SH 的推断类型: {infer_security_type("520990.SH")}')

# 查看52开头是否在ETF前缀中
code = "520990"
prefix = code[:2]
print(f"代码前缀: {prefix}")

# 检查当前的ETF前缀定义
etf_prefixes = {"50", "51", "15", "16", "58", "56"}
print(f"当前ETF前缀集合: {etf_prefixes}")
print(f"52是否在ETF前缀中: {'52' in etf_prefixes}")

if prefix not in etf_prefixes:
    print("需要将52添加到ETF前缀集合中")
else:
    print("52已在ETF前缀集合中")
