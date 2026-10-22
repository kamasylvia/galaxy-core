"""logging_helpers 模块单元测试."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from galaxy_core.shared_kernel.utils.logging_helpers import (
    BatchProgressLogger,
    log_sync_result,
)

_LOGGER_NAME = "galaxy_core.shared_kernel.utils.logging_helpers"


class TestBatchProgressLogger:
    """BatchProgressLogger 测试套件."""

    def test_init(self) -> None:
        """初始化时 total 正确设置."""
        progress = BatchProgressLogger(total=300, operation_name="test")
        assert progress.total == 300
        assert progress.operation_name == "test"
        assert progress.processed == 0

    def test_init_default_interval(self) -> None:
        """默认 log_interval 为 100."""
        progress = BatchProgressLogger(total=100, operation_name="test")
        assert progress.log_interval == 100

    def test_update_increments(self) -> None:
        """update(1) 正确累加 processed 计数."""
        progress = BatchProgressLogger(total=100, operation_name="test")
        progress.update()
        progress.update()
        progress.update()
        assert progress.processed == 3

    def test_update_with_count(self) -> None:
        """update(50) 正确增加 processed 计数."""
        progress = BatchProgressLogger(total=100, operation_name="test")
        progress.update(50)
        assert progress.processed == 50

    def test_progress_logs_at_interval(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """在 log_interval 边界处输出 DEBUG 进度日志."""
        progress = BatchProgressLogger(
            total=300, operation_name="test_op", log_interval=100
        )
        with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
            for _ in range(100):
                progress.update()

        progress_messages = [
            r for r in caplog.records if "进度: 100/300" in r.message
        ]
        assert len(progress_messages) == 1
        assert progress_messages[0].levelname == "DEBUG"

    def test_no_log_between_intervals(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """未到 log_interval 边界时不输出进度日志."""
        progress = BatchProgressLogger(
            total=300, operation_name="test_op", log_interval=100
        )
        with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
            for _ in range(50):
                progress.update()

        progress_messages = [r for r in caplog.records if "进度" in r.message]
        assert len(progress_messages) == 0

    def test_complete_without_success_count(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """complete() 不带 success_count 时输出总处理数."""
        progress = BatchProgressLogger(total=100, operation_name="test_op")
        progress.update(100)
        with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
            progress.complete()

        complete_messages = [
            r for r in caplog.records if "完成，共 100 条" in r.message
        ]
        assert len(complete_messages) == 1
        assert complete_messages[0].levelname == "INFO"

    def test_complete_with_success_count(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """complete(success_count=95) 输出成功数/总数."""
        progress = BatchProgressLogger(total=100, operation_name="test_op")
        with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
            progress.complete(success_count=95)

        complete_messages = [
            r for r in caplog.records if "成功 95/100" in r.message
        ]
        assert len(complete_messages) == 1
        assert complete_messages[0].levelname == "INFO"


class TestLogSyncResult:
    """log_sync_result 测试套件."""

    def test_basic_sync_result(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """基本同步结果输出包含成功代码数、记录数、失败代码数."""
        mock_result = MagicMock()
        mock_result.success_count = 10
        mock_result.synced_records = 500
        mock_result.failed_codes = []

        with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
            log_sync_result(mock_result)

        success_messages = [
            r for r in caplog.records if "同步成功代码数: 10" in r.message
        ]
        assert len(success_messages) == 1

        records_messages = [
            r for r in caplog.records if "同步成功记录数: 500" in r.message
        ]
        assert len(records_messages) == 1

        failed_messages = [
            r for r in caplog.records if "同步失败代码数: 0" in r.message
        ]
        assert len(failed_messages) == 1

    def test_with_failures(self, caplog: pytest.LogCaptureFixture) -> None:
        """有失败代码时输出失败详情."""
        mock_result = MagicMock()
        mock_result.success_count = 10
        mock_result.synced_records = 500
        mock_result.failed_codes = ["A.SH", "B.SH"]

        with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
            log_sync_result(mock_result)

        failed_detail = [
            r
            for r in caplog.records
            if "失败代码: A.SH, B.SH" in r.message
        ]
        assert len(failed_detail) == 1

    def test_failure_truncation(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """失败代码超过 10 只时截断显示."""
        failed_codes = [f"00000{i}.SH" for i in range(15)]
        mock_result = MagicMock()
        mock_result.success_count = 5
        mock_result.synced_records = 100
        mock_result.failed_codes = failed_codes

        with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
            log_sync_result(mock_result)

        truncation_messages = [
            r for r in caplog.records if "共 15 只" in r.message
        ]
        assert len(truncation_messages) == 1

        ellipsis_messages = [
            r
            for r in caplog.records
            if "..." in r.message and "失败代码" in r.message
        ]
        assert len(ellipsis_messages) == 1

    def test_separator_lines(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """输出包含分隔符行."""
        mock_result = MagicMock()
        mock_result.success_count = 1
        mock_result.synced_records = 10
        mock_result.failed_codes = []

        with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
            log_sync_result(mock_result)

        separator_messages = [
            r for r in caplog.records if "=" * 50 in r.message
        ]
        assert len(separator_messages) == 2
