"""Tests for CalendarSyncJob."""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from galaxy_db_bridge.application.scheduler.calendar_sync_job import CalendarSyncJob


class TestCalendarSyncJobRun:
    """Tests for CalendarSyncJob.run method."""

    @pytest.mark.asyncio
    async def test_december_20_syncs_next_year(self, mock_state_manager):
        """Dec 20 triggers next year calendar sync."""
        mock_state_manager.is_synced.return_value = False
        mock_state_manager.mark_running = AsyncMock()
        mock_state_manager.mark_success = AsyncMock()

        job = CalendarSyncJob(mock_state_manager)
        job._do_sync_calendar = AsyncMock()
        job._check_calendar_exists = AsyncMock(return_value=False)

        await job.run(date(2025, 12, 20))

        mock_state_manager.mark_running.assert_called_once_with("calendar", "2026")

    @pytest.mark.asyncio
    async def test_december_25_checks_and_syncs_if_missing(self, mock_state_manager):
        """Dec 25 checks if next year exists, syncs if missing."""
        mock_state_manager.is_synced.return_value = False

        job = CalendarSyncJob(mock_state_manager)
        job._check_calendar_exists = AsyncMock(return_value=False)
        job._do_sync_calendar = AsyncMock()

        await job.run(date(2025, 12, 25))

        job._check_calendar_exists.assert_called_once_with(2026)

    @pytest.mark.asyncio
    async def test_december_25_skips_if_exists(self, mock_state_manager):
        """Dec 25 skips if next year calendar already exists."""
        job = CalendarSyncJob(mock_state_manager)
        job._check_calendar_exists = AsyncMock(return_value=True)
        job._do_sync_calendar = AsyncMock()

        await job.run(date(2025, 12, 25))

        job._do_sync_calendar.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_december_skips(self, mock_state_manager):
        """Non-December dates skip sync."""
        job = CalendarSyncJob(mock_state_manager)
        job._check_calendar_exists = AsyncMock(return_value=True)

        await job.run(date(2025, 11, 15))

        # Should not call any sync methods
        job._check_calendar_exists.assert_not_called()

    @pytest.mark.asyncio
    async def test_before_dec_20_skips(self, mock_state_manager):
        """Before Dec 20 skips."""
        job = CalendarSyncJob(mock_state_manager)
        job._check_calendar_exists = AsyncMock(return_value=True)

        await job.run(date(2025, 12, 15))

        job._check_calendar_exists.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_already_synced(self, mock_state_manager):
        """Skips if already synced."""
        mock_state_manager.is_synced.return_value = True

        job = CalendarSyncJob(mock_state_manager)
        job._check_calendar_exists = AsyncMock(return_value=False)
        job._do_sync_calendar = AsyncMock()

        await job.run(date(2025, 12, 20))

        mock_state_manager.mark_running.assert_not_called()

    @pytest.mark.asyncio
    async def test_marks_success_after_sync(self, mock_state_manager):
        """Marks sync as success after calendar sync completes."""
        mock_state_manager.is_synced.return_value = False
        mock_state_manager.mark_running = AsyncMock()
        mock_state_manager.mark_success = AsyncMock()

        job = CalendarSyncJob(mock_state_manager)
        job._do_sync_calendar = AsyncMock()
        job._check_calendar_exists = AsyncMock(return_value=False)

        await job.run(date(2025, 12, 20))

        mock_state_manager.mark_success.assert_called_once_with("calendar", "2026")

    @pytest.mark.asyncio
    async def test_marks_failed_after_sync_failure(self, mock_state_manager):
        """Marks sync as failed after all retries exhausted."""
        mock_state_manager.is_synced.return_value = False

        job = CalendarSyncJob(mock_state_manager)
        job._check_calendar_exists = AsyncMock(return_value=False)
        # Mock sync_with_retry to return False
        with patch("galaxy_db_bridge.application.scheduler.calendar_sync_job.sync_with_retry", return_value=False):
            await job.run(date(2025, 12, 20))

        mock_state_manager.mark_failed.assert_called_once_with(
            "calendar", "2026", "All retries exhausted"
        )

    @pytest.mark.asyncio
    async def test_december_31_checks_existence(self, mock_state_manager):
        """Dec 31 checks if next year calendar exists."""
        job = CalendarSyncJob(mock_state_manager)
        job._check_calendar_exists = AsyncMock(return_value=True)
        job._do_sync_calendar = AsyncMock()

        await job.run(date(2025, 12, 31))

        job._check_calendar_exists.assert_called_once_with(2026)