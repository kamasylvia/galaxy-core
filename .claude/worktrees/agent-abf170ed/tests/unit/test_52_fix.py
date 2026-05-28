from galaxy_db_bridge.shared_kernel.utils.symbol_validator import infer_security_type

# 测试52开头的代码
codes_to_test = ["520990.SH", "520760.SH", "520890.SH"]

for code in codes_to_test:
    result = infer_security_type(code)
    print(f"{code} 的推断类型: {result}")
