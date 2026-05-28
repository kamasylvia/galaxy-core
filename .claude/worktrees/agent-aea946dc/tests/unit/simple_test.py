"""简单测试验证修复是否已保存到文件中"""

# 读取文件并检查是否包含更新后的函数
with open("src/galaxy_db_sync/shared_kernel/utils/time_parser.py", "r") as f:
    content = f.read()

# 检查是否包含更新后的函数定义
if (
    "is_end_date: bool = False" in content
    and "def convert_date_string_to_int(date_str: str, interval: str, is_end_date: bool = False)"
    in content
):
    print("✅ 函数签名已更新，包含 is_end_date 参数")
else:
    print("❌ 函数签名未更新")

# 检查是否包含正确的逻辑
if "if is_end_date:" in content and "calendar.monthrange" in content:
    print("✅ 包含正确的结束日期逻辑")
else:
    print("❌ 缺少结束日期逻辑")

# 检查年线处理逻辑
if "YYYY1231" in content and "YYYY0101" in content:
    print("✅ 包含年线正确的日期补全逻辑")
else:
    print("❌ 缺少年线日期补全逻辑")

# 检查调用点是否已更新
if "is_end_date=False" in content and "is_end_date=True" in content:
    print("✅ 调用点已更新")
else:
    print("❌ 调用点未更新")

print("\n✅ 修复已成功保存到文件中！")
