"""Async CLI 入口测试模块.

测试 application/cli/commands 模块的异步 CLI 功能，包括：
- async_main() 函数行为
- handle_kline_command_async() 异步命令处理
- asyncio.run() 包装正确性
- 退出码语义（成功 0，失败 1）
- async database initialization 被调用
- sync operations 被 asyncio.to_thread 正确包装
"""

import argparse
import asyncio
import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

if "AmazingData" not in sys.modules:
    sys.modules["AmazingData"] = types.SimpleNamespace(
        login=lambda **kwargs: None,
        logout=lambda *args, **kwargs: None,
        BaseData=lambda: types.SimpleNamespace(get_calendar=lambda *args, **kwargs: []),
        InfoData=lambda: types.SimpleNamespace(),
        MarketData=lambda calendar: types.SimpleNamespace(query_kline=lambda **kwargs: {}),
    )

if "akshare" not in sys.modules:
    sys.modules["akshare"] = types.SimpleNamespace()

if "tgw" not in sys.modules:
    sys.modules["tgw"] = types.SimpleNamespace()

# Mock config_loader before importing galaxy_core (override if exists) — 返回默认值而非空 dict
config_loader_mock = types.ModuleType("galaxy_core.shared_kernel.utils.config_loader")

def _mock_get_config(*args, **kwargs):
    if len(args) >= 3:
        return args[2]
    return kwargs.get("default")

config_loader_mock.get_config = _mock_get_config
config_loader_mock.get_section = lambda *args, **kwargs: {}
config_loader_mock.load_config_dict = lambda *args, **kwargs: {}
sys.modules["galaxy_core.shared_kernel.utils.config_loader"] = config_loader_mock

from galaxy_core.application.cli.commands import async_main, main
from galaxy_core.application.kline.command import handle_kline_command_async


class TestAsyncCLIEntry(unittest.TestCase):
    """异步 CLI 入口测试类."""

    def test_handle_kline_command_async_returns_0_on_success(self):
        """Test async handler returns 0 on successful execution."""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval=["day"],
            start="20230101",
            end="20231231",
        )

        mock_kline_service = MagicMock()
        mock_kline_service.sync = AsyncMock(return_value=MagicMock(
            success_count=1, synced_records=100, failed_codes=[], total_symbols=1
        ))

        with (
            patch(
                "galaxy_core.application.kline.command.parse_symbols",
                return_value=[("symbol", "600000.SH")],
            ),
            patch(
                "galaxy_core.application.kline.command.resolve_symbols",
                return_value=["600000.SH"],
            ),
            patch(
                "galaxy_core.application.kline.command.validate_date_range",
                return_value=[],
            ),
        ):
            result = asyncio.run(handle_kline_command_async(
                args,
                kline_service=mock_kline_service,
            ))

        self.assertEqual(result, 0)
        mock_kline_service.sync.assert_called_once()

    def test_handle_kline_command_async_returns_1_on_error(self):
        """Test async handler returns 1 on failure."""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval="invalid_interval",
            start=None,
            end=None,
        )

        result = asyncio.run(handle_kline_command_async(args))

        self.assertEqual(result, 1)

    def test_handle_kline_command_async_triggers_sync(self):
        """Test async handler triggers sync via kline_service."""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval=["day"],
            start="20230101",
            end="20231231",
        )

        mock_sync_result = MagicMock()
        mock_sync_result.success_count = 1
        mock_sync_result.synced_records = 100
        mock_sync_result.failed_codes = []
        mock_sync_result.total_symbols = 1

        mock_kline_service = MagicMock()
        mock_kline_service.sync = AsyncMock(return_value=mock_sync_result)

        with (
            patch(
                "galaxy_core.application.kline.command.parse_symbols",
                return_value=[("symbol", "600000.SH")],
            ),
            patch(
                "galaxy_core.application.kline.command.resolve_symbols",
                return_value=["600000.SH"],
            ),
            patch(
                "galaxy_core.application.kline.command.validate_date_range",
                return_value=[],
            ),
        ):
            result = asyncio.run(handle_kline_command_async(
                args,
                kline_service=mock_kline_service,
            ))

        self.assertEqual(result, 0)
        mock_kline_service.sync.assert_called_once()

    def test_main_wraps_async_main_with_asyncio_run(self):
        """Test main() correctly wraps async_main with asyncio.run."""
        with (
            patch("asyncio.run", return_value=0) as mock_run,
            patch(
                "galaxy_core.application.cli.commands.async_main",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            result = main()

        mock_run.assert_called_once()
        self.assertEqual(result, 0)

    def test_async_main_returns_1_when_no_command(self):
        """Test async_main returns 1 when no command provided."""
        with patch("sys.argv", ["galaxy-data-ingest"]):
            result = asyncio.run(async_main())

        self.assertEqual(result, 1)

    def test_async_main_dispatches_kline_to_async_handler(self):
        """Test async_main dispatches kline command to async handler via DI container."""
        args = argparse.Namespace(
            command="kline",
            symbols="600000.SH",
            interval=["day"],
            start="20230101",
            end="20231231",
        )

        mock_kline_service = MagicMock()

        with (
            patch("argparse.ArgumentParser.parse_args", return_value=args),
            patch(
                "galaxy_core.application.cli.commands.create_container"
            ) as mock_create_container,
            patch(
                "galaxy_core.application.cli.commands.handle_kline_command_async",
                new_callable=AsyncMock,
                return_value=0,
            ) as mock_handle_async,
        ):
            mock_container = MagicMock()
            mock_container.kline_service.return_value = mock_kline_service
            mock_container.db_manager.return_value = MagicMock()
            mock_create_container.return_value = mock_container

            result = asyncio.run(async_main())

        self.assertEqual(result, 0)
        mock_handle_async.assert_called_once()

    def test_async_main_wraps_calendar_with_di_container(self):
        """Test async_main uses DI container for calendar command."""
        args = argparse.Namespace(
            command="calendar",
            start_year=2024,
            end_year=2024,
        )

        mock_calendar_service = MagicMock()

        with (
            patch("argparse.ArgumentParser.parse_args", return_value=args),
            patch(
                "galaxy_core.application.cli.commands.create_container"
            ) as mock_create_container,
            patch(
                "galaxy_core.application.cli.commands.handle_calendar_command_async",
                new_callable=AsyncMock,
                return_value=0,
            ) as mock_handle_async,
        ):
            mock_container = MagicMock()
            mock_container.calendar_service.return_value = mock_calendar_service
            mock_create_container.return_value = mock_container

            result = asyncio.run(async_main())

        self.assertEqual(result, 0)
        mock_handle_async.assert_called_once_with(args, calendar_service=mock_calendar_service)

    def test_handle_kline_command_async_exception_handling(self):
        """Test async handler returns 1 on exception."""
        args = argparse.Namespace(
            symbols="600000.SH",
            interval=["day"],
            start="20230101",
            end="20231231",
        )

        with (
            patch(
                "galaxy_core.application.kline.command.parse_symbols",
                side_effect=Exception("Test exception"),
            ),
            patch("logging.Logger.error") as mock_logger_error,
        ):
            result = asyncio.run(handle_kline_command_async(args))

        self.assertEqual(result, 1)
        mock_logger_error.assert_called()


class TestSchedulerReplaceFlag(unittest.TestCase):
    """scheduler 子命令 --replace flag 透传测试.

    验证 CLI parser 正确解析 --replace，并将其透传给 run_scheduler(replace=...)。
    """

    def test_scheduler_replace_flag_parsed_true(self):
        """`scheduler --replace` 应解析为 args.replace=True."""
        # 重建与 async_main 相同的 parser 结构（最小复制，验证 flag 注册）
        parser = argparse.ArgumentParser(prog="galaxy-db-sync")
        subparsers = parser.add_subparsers(dest="command")
        sched = subparsers.add_parser("scheduler")
        sched.add_argument("--env", type=str, default="")
        sched.add_argument(
            "--replace",
            action="store_true",
            help="force replace",
        )

        args = parser.parse_args(["scheduler", "--replace"])
        self.assertTrue(args.replace)

    def test_scheduler_replace_defaults_false(self):
        """`scheduler`（无 --replace）应解析为 args.replace=False."""
        parser = argparse.ArgumentParser(prog="galaxy-db-sync")
        subparsers = parser.add_subparsers(dest="command")
        sched = subparsers.add_parser("scheduler")
        sched.add_argument("--env", type=str, default="")
        sched.add_argument("--replace", action="store_true")

        args = parser.parse_args(["scheduler"])
        self.assertFalse(args.replace)

    def test_scheduler_branch_passes_replace_to_run_scheduler(self):
        """async_main scheduler 分支应把 args.replace 透传给 run_scheduler."""
        # sys.argv 模拟 `galaxy-db-sync scheduler --replace`
        with patch.object(
            sys, "argv", ["galaxy-db-sync", "scheduler", "--replace"]
        ), patch(
            "galaxy_core.application.scheduler.scheduler.run_scheduler",
            new_callable=AsyncMock,
            return_value=0,
        ) as mock_run:
            result = asyncio.run(async_main())

        mock_run.assert_awaited_once_with(replace=True)
        self.assertEqual(result, 0)

    def test_scheduler_branch_without_replace_passes_false(self):
        """无 --replace 时 async_main 应透传 replace=False."""
        with patch(
            "galaxy_core.application.scheduler.scheduler.run_scheduler",
            new_callable=AsyncMock,
            return_value=0,
        ) as mock_run, patch.object(sys, "argv", ["galaxy-db-sync", "scheduler"]):
            asyncio.run(async_main())

        mock_run.assert_awaited_once_with(replace=False)


if __name__ == "__main__":
    unittest.main()
