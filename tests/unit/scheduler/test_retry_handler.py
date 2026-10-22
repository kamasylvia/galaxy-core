"""Tests for retry_handler."""

from unittest.mock import AsyncMock

import pytest

from galaxy_core.application.scheduler.retry_handler import RetryPolicy, sync_with_retry


class TestRetryPolicy:
    """Tests for RetryPolicy configuration."""

    def test_default_max_retries(self):
        """Default max retries is 3."""
        policy = RetryPolicy()
        assert policy.max_retries == 3

    def test_default_retry_delay(self):
        """Default retry delay is 300 seconds (5 minutes)."""
        policy = RetryPolicy()
        assert policy.retry_delay == 300

    def test_retry_delay_from_config(self):
        """Retry delay is loaded from config."""
        policy = RetryPolicy.from_config()
        # Config in conftest.py sets retry_delay_minutes = 5
        assert policy.retry_delay == 300  # in seconds

    def test_from_config_kline_overrides_max_retries(self):
        """kline sync_type 读 [scheduler.kline] 子表覆盖 max_retries.

        2026-08-11 根治:凌晨 AM 返空需 kline 独立 max_retries=6。
        用 patch 隔离 mock config(避免 test_sync_regression 模块级 mock 污染)。
        """
        from unittest.mock import patch

        fake_config = {
            "max_retries": 3,
            "retry_delay_minutes": 5,
            "kline": {"max_retries": 6},
        }
        with patch(
            "galaxy_core.application.scheduler.retry_handler.get_section",
            return_value=fake_config,
        ):
            policy = RetryPolicy.from_config("kline_day")
        assert policy.max_retries == 6
        # retry_delay 不被子表覆盖,保留全局值(5min × 60 = 300s)
        assert policy.retry_delay == 300

    def test_from_config_non_matching_sync_type_uses_global(self):
        """非 kline_ 前缀的 sync_type 走全局默认."""
        from unittest.mock import patch

        fake_config = {
            "max_retries": 3,
            "retry_delay_minutes": 5,
            "kline": {"max_retries": 6},
        }
        with patch(
            "galaxy_core.application.scheduler.retry_handler.get_section",
            return_value=fake_config,
        ):
            policy_long_hu = RetryPolicy.from_config("long_hu_bang")
            assert policy_long_hu.max_retries == 3
            assert policy_long_hu.retry_delay == 300

            policy_none = RetryPolicy.from_config(None)
            assert policy_none.max_retries == 3

    def test_from_config_kline_subtable_can_override_delay(self):
        """子表也可覆盖 retry_delay_minutes(通用性)."""
        # 直接构造含 delay 覆盖的 config dict 测试
        from unittest.mock import patch

        fake_config = {
            "max_retries": 3,
            "retry_delay_minutes": 5,
            "kline": {"max_retries": 6, "retry_delay_minutes": 60},
        }
        with patch(
            "galaxy_core.application.scheduler.retry_handler.get_section",
            return_value=fake_config,
        ):
            policy = RetryPolicy.from_config("kline_day")
            assert policy.max_retries == 6
            assert policy.retry_delay == 3600  # 60min × 60


class TestSyncWithRetry:
    """Tests for sync_with_retry function."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self, mock_sync_func):
        """Returns True immediately on success."""
        mock_sync_func.return_value = True
        result = await sync_with_retry(mock_sync_func, "test_sync")
        assert result is True
        assert mock_sync_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure(self, mock_sync_func):
        """Initial + MAX_RETRIES attempts on total failure."""
        mock_sync_func.side_effect = Exception("Sync failed")
        import galaxy_core.application.scheduler.retry_handler as rh

        original_sleep = rh.asyncio.sleep
        rh.asyncio.sleep = AsyncMock()

        result = await sync_with_retry(mock_sync_func, "test_sync")
        assert result is False
        assert mock_sync_func.call_count == 4  # initial + 3 retries
        # 仅重试间隙 sleep(2026-08-20 修复):最后一次重试失败后不再 sleep
        # (原实现白白多等一个 retry_delay 才标 failed,拖晚后续 job 1 小时)
        assert rh.asyncio.sleep.call_count == 2
        assert rh.asyncio.sleep.call_args_list[0][0][0] == 300
        assert rh.asyncio.sleep.call_args_list[1][0][0] == 300

        rh.asyncio.sleep = original_sleep

    @pytest.mark.asyncio
    async def test_success_after_retry(self, mock_sync_func):
        """Succeeds on retry."""
        mock_sync_func.side_effect = [
            Exception("Initial failure"),
            Exception("Retry 1 failure"),
            True,  # Success on retry 2
        ]
        import galaxy_core.application.scheduler.retry_handler as rh

        original_sleep = rh.asyncio.sleep
        rh.asyncio.sleep = AsyncMock()

        result = await sync_with_retry(mock_sync_func, "test_sync")
        assert result is True
        assert mock_sync_func.call_count == 3  # initial + 2 retries
        # Only 1 sleep (after retry 1 fails, retry 2 succeeds)
        assert rh.asyncio.sleep.call_count == 1

        rh.asyncio.sleep = original_sleep

    @pytest.mark.asyncio
    async def test_timeout_error_empty_message_logged_with_type(
        self, mock_sync_func, caplog
    ):
        """回归: asyncio.TimeoutError(str 空)失败时 log 应含类型名(2026-07-29)。

        原 `logger.error(f"...: {e}")` 对 TimeoutError(str 空)显示「同步失败: 」
        后面空白,无法定位根因。修复:str 空 时用 type(e).__name__ + exc_info。
        """
        import logging
        import asyncio as _asyncio

        mock_sync_func.side_effect = _asyncio.TimeoutError()
        import galaxy_core.application.scheduler.retry_handler as rh

        original_sleep = rh.asyncio.sleep
        rh.asyncio.sleep = AsyncMock()

        with caplog.at_level(logging.ERROR, logger="galaxy_core.application.scheduler.retry_handler"):
            await sync_with_retry(mock_sync_func, "test_timeout_sync")

        # log 应含 TimeoutError 类型名(非空白)
        assert any(
            "TimeoutError" in rec.message for rec in caplog.records
        ), f"未找到 TimeoutError 类型名,实际: {[r.message for r in caplog.records]}"

        rh.asyncio.sleep = original_sleep

    @pytest.mark.asyncio
    async def test_sync_type_kline_uses_kline_subtable(
        self, mock_sync_func
    ):
        """sync_type='kline_day' 读 [scheduler.kline] max_retries=6.

        2026-08-11 根治:验证 sync_type kwarg 透传到 RetryPolicy.from_config。
        kline 失败应重试 6 次(initial + 6 = 7 次),而非全局 3 次。
        """
        from unittest.mock import patch

        mock_sync_func.side_effect = Exception("AM empty")
        import galaxy_core.application.scheduler.retry_handler as rh

        original_sleep = rh.asyncio.sleep
        rh.asyncio.sleep = AsyncMock()

        fake_config = {
            "max_retries": 3,
            "retry_delay_minutes": 5,
            "kline": {"max_retries": 6},
        }
        with patch(
            "galaxy_core.application.scheduler.retry_handler.get_section",
            return_value=fake_config,
        ):
            result = await sync_with_retry(
                mock_sync_func, "kline_day 20260810", sync_type="kline_day"
            )
        assert result is False
        # initial + 6 retries = 7 calls
        assert mock_sync_func.call_count == 7
        # 仅重试间隙 sleep(2026-08-20 修复):6 次重试只有 5 次间隙 sleep
        assert rh.asyncio.sleep.call_count == 5

        rh.asyncio.sleep = original_sleep
