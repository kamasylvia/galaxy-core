"""测试配置加载器.

用于在测试环境中加载项目配置，特别是项目根目录路径。
"""

import os
from pathlib import Path
from dotenv import load_dotenv


def load_test_config():
    """加载测试环境配置."""
    # 加载 .env 文件
    env_path = Path(__file__).parent.parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def get_project_root_from_env() -> Path:
    """从环境变量获取项目根目录路径.

    Returns:
        项目根目录的 Path 对象
    """
    load_test_config()
    project_root_path = os.getenv("PROJECT_ROOT_PATH", "")

    if not project_root_path:
        # 如果环境变量未设置，尝试从当前文件位置推断
        # 这是后备方案
        return Path(__file__).parent.parent.parent.parent

    return Path(project_root_path)


# 提供一个全局变量，方便测试使用
PROJECT_ROOT = get_project_root_from_env()


def add_src_to_path():
    """将src目录添加到Python路径."""
    src_path = PROJECT_ROOT / "src"
    if str(src_path) not in os.sys.path:
        os.sys.path.insert(0, str(src_path))


# 立即加载配置
load_test_config()
