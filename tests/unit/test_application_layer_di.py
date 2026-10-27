"""应用层 DI 迁移测试模块.

验证三个应用层入口（commands.py, scheduler.py, server.py）
已从 injector 迁移到 dependency-injector 的 create_container()。
"""

import unittest


class TestCommandsDI(unittest.TestCase):
    """验证 commands.py 使用 create_container 替代 create_injector."""

    def test_commands_no_injector_import(self):
        """commands.py 不应导入 injector 框架."""
        with open(
            "data/src/galaxy_core/application/cli/commands.py", encoding="utf-8"
        ) as f:
            content = f.read()

        self.assertNotIn(
            "from injector import",
            content,
            "commands.py 不应导入 injector 框架",
        )
        self.assertNotIn(
            "import injector",
            content,
            "commands.py 不应导入 injector 框架",
        )

    def test_commands_no_create_injector_import(self):
        """commands.py 不应导入 create_injector."""
        with open(
            "data/src/galaxy_core/application/cli/commands.py", encoding="utf-8"
        ) as f:
            content = f.read()

        self.assertNotIn(
            "create_injector",
            content,
            "commands.py 不应导入 create_injector",
        )

    def test_commands_uses_create_container(self):
        """commands.py 应导入 create_container."""
        with open(
            "data/src/galaxy_core/application/cli/commands.py", encoding="utf-8"
        ) as f:
            content = f.read()

        self.assertIn(
            "create_container",
            content,
            "commands.py 应使用 create_container",
        )

    def test_commands_no_injector_get_calls(self):
        """commands.py 不应有 injector.get() 调用."""
        with open(
            "data/src/galaxy_core/application/cli/commands.py", encoding="utf-8"
        ) as f:
            content = f.read()

        self.assertNotIn(
            "injector.get(",
            content,
            "commands.py 不应有 injector.get() 调用",
        )

    def test_commands_uses_container_service_calls(self):
        """commands.py 应使用 container.xxx_service() 模式."""
        with open(
            "data/src/galaxy_core/application/cli/commands.py", encoding="utf-8"
        ) as f:
            content = f.read()

        self.assertIn(
            "container.kline_service()",
            content,
            "commands.py 应使用 container.kline_service()",
        )
        self.assertIn(
            "container.calendar_service()",
            content,
            "commands.py 应使用 container.calendar_service()",
        )


class TestSchedulerDI(unittest.TestCase):
    """验证 scheduler.py 使用 create_container 替代 create_injector."""

    def test_scheduler_no_injector_import(self):
        """scheduler.py 不应导入 injector 框架."""
        with open(
            "data/src/galaxy_core/application/scheduler/scheduler.py", encoding="utf-8"
        ) as f:
            content = f.read()

        self.assertNotIn(
            "from injector import",
            content,
            "scheduler.py 不应导入 injector 框架",
        )
        self.assertNotIn(
            "import injector",
            content,
            "scheduler.py 不应导入 injector 框架",
        )

    def test_scheduler_no_create_injector_import(self):
        """scheduler.py 不应导入 create_injector."""
        with open(
            "data/src/galaxy_core/application/scheduler/scheduler.py", encoding="utf-8"
        ) as f:
            content = f.read()

        self.assertNotIn(
            "create_injector",
            content,
            "scheduler.py 不应导入 create_injector",
        )

    def test_scheduler_uses_create_container(self):
        """scheduler.py 应导入 create_container."""
        with open(
            "data/src/galaxy_core/application/scheduler/scheduler.py", encoding="utf-8"
        ) as f:
            content = f.read()

        self.assertIn(
            "create_container",
            content,
            "scheduler.py 应使用 create_container",
        )

    def test_scheduler_no_injector_get_calls(self):
        """scheduler.py 不应有 injector.get() 调用."""
        with open(
            "data/src/galaxy_core/application/scheduler/scheduler.py", encoding="utf-8"
        ) as f:
            content = f.read()

        self.assertNotIn(
            "injector.get(",
            content,
            "scheduler.py 不应有 injector.get() 调用",
        )

    def test_scheduler_uses_container_calls(self):
        """scheduler.py 应使用 container.xxx_service() 模式."""
        with open(
            "data/src/galaxy_core/application/scheduler/scheduler.py", encoding="utf-8"
        ) as f:
            content = f.read()

        self.assertIn(
            "container.db_manager()",
            content,
            "scheduler.py 应使用 container.db_manager()",
        )
        self.assertIn(
            "container.kline_service()",
            content,
            "scheduler.py 应使用 container.kline_service()",
        )


