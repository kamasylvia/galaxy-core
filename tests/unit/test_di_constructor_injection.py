"""DI 构造函数注入测试模块.

验证 database/services 层的纯异步服务文件已从单例直接导入
改为构造函数注入 AsyncDatabaseManager。
"""

import inspect
import unittest
from unittest.mock import MagicMock


class TestConstructorInjectionTask1(unittest.TestCase):
    """Task 1: 验证服务文件使用构造函数注入，无模块级单例."""

    def test_kline_service_requires_db_manager(self):
        """KlineService.__init__ 应接受 db_manager 参数."""
        from galaxy_core.database.services.kline import KlineService

        sig = inspect.signature(KlineService.__init__)
        params = list(sig.parameters.keys())
        self.assertIn("db_manager", params, f"__init__ 参数应包含 db_manager, 实际: {params}")

    def test_no_module_level_singleton_kline_service(self):
        """kline.py 不应有模块级单例实例."""
        import galaxy_core.database.services.kline as module

        self.assertFalse(
            hasattr(module, "kline_service"),
            "kline.py 不应有 kline_service 模块级实例",
        )

    def test_no_singleton_import_in_kline(self):
        """kline.py 不应在底部导入 async_db_manager 单例."""
        with open(
            "src/galaxy_core/database/services/kline.py", encoding="utf-8"
        ) as f:
            content = f.read()

        # 应该只有 AsyncDatabaseManager 类型导入，没有 async_db_manager 实例导入
        self.assertNotIn(
            "import async_db_manager\n",
            content,
            "kline.py 不应在底部导入 async_db_manager 单例",
        )

    def test_init_py_no_kline_service_export(self):
        """__init__.py 不应导出 kline_service 实例."""
        with open(
            "src/galaxy_core/database/services/__init__.py", encoding="utf-8"
        ) as f:
            content = f.read()

        self.assertNotIn(
            "kline_service",
            content,
            "__init__.py 不应导出 kline_service 实例",
        )


if __name__ == "__main__":
    unittest.main()
