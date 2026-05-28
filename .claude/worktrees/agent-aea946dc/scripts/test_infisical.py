"""测试 Infisical 集成."""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# 加载 .env.infisical 文件
from dotenv import load_dotenv

env_infisical_path = project_root / ".env.infisical"
if env_infisical_path.exists():
    load_dotenv(env_infisical_path, override=True)
else:
    print("Warning: .env.infisical not found")

# 导入 Infisical 配置模块
from galaxy_db_sync.shared_kernel.utils.infisical_config import (
    InfisicalConfig,
    get_env,
    load_infisical_to_env,
)


def test_infisical_connection():
    """测试 Infisical 连接."""
    print("\n" + "=" * 60)
    print("测试 Infisical 连接")
    print("=" * 60)

    # 检查环境变量
    print("\n1. 检查 Infisical 环境变量:")
    print(f"   INFISICAL_URL: {os.getenv('INFISICAL_URL', 'Not Set')}")
    print(f"   INFISICAL_CLIENT_ID: {'Set' if os.getenv('INFISICAL_CLIENT_ID') else 'Not Set'}")
    print(f"   INFISICAL_CLIENT_SECRET: {'Set' if os.getenv('INFISICAL_CLIENT_SECRET') else 'Not Set'}")
    print(f"   INFISICAL_PROJECT_ID: {os.getenv('INFISICAL_PROJECT_ID', 'Not Set')}")
    print(f"   INFISICAL_ENVIRONMENT: {os.getenv('INFISICAL_ENVIRONMENT', 'dev')}")

    # 检查是否已配置
    print("\n2. 检查 Infisical 配置状态:")
    is_configured = InfisicalConfig.is_configured()
    print(f"   Infisical Configured: {is_configured}")

    if not is_configured:
        print("\n   ❌ Infisical 未配置，请检查 .env.infisical 文件")
        return False

    # 初始化客户端
    print("\n3. 初始化 Infisical 客户端:")
    try:
        success = InfisicalConfig.initialize()
        if success:
            print("   ✅ Infisical 客户端初始化成功")
        else:
            print("   ❌ Infisical 客户端初始化失败")
            return False
    except Exception as e:
        print(f"   ❌ 初始化错误: {e}")
        return False

    # 测试获取单个密钥
    print("\n4. 测试获取单个密钥:")
    try:
        secret = InfisicalConfig.get_secret("GALAXY_USERNAME")
        if secret:
            print(f"   ✅ GALAXY_USERNAME: {secret}")
        else:
            print("   ⚠️  GALAXY_USERNAME: Not found in Infisical")
    except Exception as e:
        print(f"   ❌ 获取密钥错误: {e}")

    # 测试获取所有密钥
    print("\n5. 测试获取所有密钥:")
    try:
        secrets = InfisicalConfig.get_secrets()
        if secrets:
            print(f"   ✅ 成功获取 {len(secrets)} 个密钥:")
            for key in list(secrets.keys())[:5]:  # 只显示前5个
                print(f"      - {key}")
            if len(secrets) > 5:
                print(f"      ... 还有 {len(secrets) - 5} 个密钥")
        else:
            print("   ⚠️  未获取到任何密钥")
    except Exception as e:
        print(f"   ❌ 获取所有密钥错误: {e}")

    return True


def test_get_env_function():
    """测试 get_env 函数."""
    print("\n" + "=" * 60)
    print("测试 get_env 函数")
    print("=" * 60)

    # 测试从本地环境变量获取
    print("\n1. 测试从本地环境变量获取:")
    local_value = os.getenv("GALAXY_USERNAME")
    print(f"   os.getenv('GALAXY_USERNAME'): {local_value}")

    # 测试 get_env 函数
    print("\n2. 测试 get_env 函数:")
    value = get_env("GALAXY_USERNAME", default="Not Found")
    print(f"   get_env('GALAXY_USERNAME'): {value}")

    # 测试获取不存在的密钥
    print("\n3. 测试获取不存在的密钥:")
    value = get_env("NON_EXISTENT_KEY", default="Default Value")
    print(f"   get_env('NON_EXISTENT_KEY', default='Default Value'): {value}")


def test_config_loader():
    """测试配置加载器."""
    print("\n" + "=" * 60)
    print("测试配置加载器")
    print("=" * 60)

    from galaxy_db_sync.shared_kernel.utils.config_loader._config_loader_impl import (
        ConfigLoader,
    )

    # 重置配置缓存
    ConfigLoader.reset()

    print("\n1. 加载配置:")
    try:
        config = ConfigLoader.load()
        print("   ✅ 配置加载成功")

        # 显示 AmazingData 配置
        if "amazing_data" in config:
            ad_config = config["amazing_data"]
            print("\n2. AmazingData 配置:")
            print(f"   username: {ad_config.get('username', 'Not Set')}")
            print(f"   host: {ad_config.get('host', 'Not Set')}")
            print(f"   port: {ad_config.get('port', 'Not Set')}")

        # 显示数据库配置
        if "database" in config:
            db_config = config["database"]
            print("\n3. 数据库配置:")
            print(f"   host: {db_config.get('host', 'Not Set')}")
            print(f"   port: {db_config.get('port', 'Not Set')}")
            print(f"   name: {db_config.get('name', 'Not Set')}")
            print(f"   user: {db_config.get('user', 'Not Set')}")

    except Exception as e:
        print(f"   ❌ 配置加载错误: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主函数."""
    print("\n" + "=" * 60)
    print("Infisical 集成测试")
    print("=" * 60)

    # 测试 Infisical 连接
    connected = test_infisical_connection()

    # 测试 get_env 函数
    test_get_env_function()

    # 测试配置加载器
    test_config_loader()

    print("\n" + "=" * 60)
    if connected:
        print("✅ Infisical 集成测试完成")
    else:
        print("⚠️  Infisical 连接失败，但本地配置仍可用")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
