# 检查53和55开头的代码
codes = ['530300.SH', '530680.SH', '530280.SH', '530080.SH', '530880.SH', '530050.SH', '530580.SH', '530800.SH', '530000.SH', '530180.SH',
         '530380.SH', '551580.SH', '551030.SH', '551900.SH', '551550.SH', '551500.SH', '530530.SH', '530100.SH', '551000.SH', '551520.SH',
         '530060.SH', '551510.SH', '551300.SH']

from galaxy_db_bridge.shared_kernel.utils.symbol_validator import infer_security_type

print('检查53和55开头的代码类型:')
for code in codes:
    prefix = code[:3]  # 前3位
    inferred_type = infer_security_type(code)
    print(f'{code} (前缀{prefix}) -> 推断类型: {inferred_type}')

print()
print('分析代码前缀:')
prefixes = set()
for code in codes:
    prefixes.add(code[:3])

for prefix in sorted(prefixes):
    print(f'前缀 {prefix} 的代码:')
    for code in codes:
        if code.startswith(prefix):
            inferred_type = infer_security_type(code)
            print(f'  {code} -> {inferred_type}')
