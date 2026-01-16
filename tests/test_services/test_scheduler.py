"""Tests for scheduler service."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from script_launcher.services.scheduler import SchedulerService


@pytest.fixture
def scheduler() -> Generator[SchedulerService, None, None]:
    """Provide a scheduler with mocked BackgroundScheduler to avoid thread issues."""
    with patch("script_launcher.services.scheduler.BackgroundScheduler") as mock_bg:
        mock_instance = MagicMock()
        mock_instance.running = False
        mock_instance.get_job.return_value = MagicMock(
            trigger=MagicMock(interval=timedelta(seconds=10))
        )
        mock_instance.add_job.return_value = MagicMock(id="mock_job_id")
        mock_bg.return_value = mock_instance

        service = SchedulerService()
        yield service


@pytest.fixture
def mock_script() -> MagicMock:
    """Create a mock script object."""
    script = MagicMock()
    script.id = 1
    script.name = "Test Script"
    script.path = "/path/to/script.py"
    script.repeat_enabled = True
    script.is_active = True
    script.interval_value = 10
    script.interval_unit = "seconds"
    script.weekdays = None
    script.scheduled_start_enabled = False
    script.scheduled_start_datetime = None
    return script


class TestSchedulerService:
    """Tests for SchedulerService class."""

    @patch("script_launcher.services.scheduler.BackgroundScheduler")
    def test_scheduler_can_start(self, mock_bg_scheduler: MagicMock) -> None:
        """Test that scheduler can be started."""
        mock_instance = MagicMock()
        mock_instance.running = False
        mock_bg_scheduler.return_value = mock_instance

        sched = SchedulerService()
        sched.start()

        mock_instance.start.assert_called_once()

    @patch("script_launcher.services.scheduler.BackgroundScheduler")
    def test_start_already_running(self, mock_bg_scheduler: MagicMock) -> None:
        """Test starting scheduler when already running does nothing."""
        mock_instance = MagicMock()
        mock_instance.running = True  # Already running
        mock_bg_scheduler.return_value = mock_instance

        sched = SchedulerService()
        sched.start()  # Should not call start() since already running

        mock_instance.start.assert_not_called()

    @patch("script_launcher.services.scheduler.BackgroundScheduler")
    def test_shutdown_not_running(self, mock_bg_scheduler: MagicMock) -> None:
        """Test shutting down scheduler that isn't running does nothing."""
        mock_instance = MagicMock()
        mock_instance.running = False
        mock_bg_scheduler.return_value = mock_instance

        sched = SchedulerService()
        sched.shutdown()  # Should not raise

        mock_instance.shutdown.assert_not_called()

    def test_add_job(self, scheduler: SchedulerService, mock_script: MagicMock) -> None:
        """Test adding a scheduled job."""
        scheduler.add_job(mock_script)

        assert mock_script.id in scheduler._jobs
        job_id = scheduler._jobs[mock_script.id]
        job = scheduler._scheduler.get_job(job_id)
        assert job is not None

    def test_add_job_without_repeat(
        self, scheduler: SchedulerService, mock_script: MagicMock
    ) -> None:
        """Test adding a job when repeat is disabled does nothing."""
        mock_script.repeat_enabled = False

        scheduler.add_job(mock_script)

        assert mock_script.id not in scheduler._jobs

    def test_add_job_without_interval(
        self, scheduler: SchedulerService, mock_script: MagicMock
    ) -> None:
        """Test adding a job without interval values does nothing."""
        mock_script.interval_value = None

        scheduler.add_job(mock_script)

        assert mock_script.id not in scheduler._jobs

    def test_remove_job(self, scheduler: SchedulerService, mock_script: MagicMock) -> None:
        """Test removing a scheduled job."""
        scheduler.add_job(mock_script)
        assert mock_script.id in scheduler._jobs

        scheduler.remove_job(mock_script.id)
        assert mock_script.id not in scheduler._jobs

    def test_remove_nonexistent_job(self, scheduler: SchedulerService) -> None:
        """Test removing a job that doesn't exist does nothing."""
        scheduler.remove_job(999)  # Should not raise

    def test_update_job_enable(self, scheduler: SchedulerService, mock_script: MagicMock) -> None:
        """Test updating a job when script is enabled."""
        scheduler.update_job(mock_script)

        assert mock_script.id in scheduler._jobs

    def test_update_job_disable(self, scheduler: SchedulerService, mock_script: MagicMock) -> None:
        """Test updating a job when script is disabled removes it."""
        scheduler.add_job(mock_script)
        assert mock_script.id in scheduler._jobs

        mock_script.is_active = False
        scheduler.update_job(mock_script)

        assert mock_script.id not in scheduler._jobs

    def test_update_job_disable_repeat(
        self, scheduler: SchedulerService, mock_script: MagicMock
    ) -> None:
        """Test updating a job when repeat is disabled removes it."""
        scheduler.add_job(mock_script)
        assert mock_script.id in scheduler._jobs

        mock_script.repeat_enabled = False
        scheduler.update_job(mock_script)

        assert mock_script.id not in scheduler._jobs

    @patch("script_launcher.services.scheduler.BackgroundScheduler")
    def test_get_next_run(self, mock_bg_scheduler: MagicMock, mock_script: MagicMock) -> None:
        """Test getting next run time for a job."""
        mock_instance = MagicMock()
        mock_instance.running = False
        mock_job = MagicMock()
        mock_job.next_run_time = datetime.now(UTC) + timedelta(seconds=10)
        mock_instance.get_job.return_value = mock_job
        mock_instance.add_job.return_value = MagicMock(id="script_1")
        mock_bg_scheduler.return_value = mock_instance

        sched = SchedulerService()
        sched.add_job(mock_script)
        next_run = sched.get_next_run(mock_script.id)

        assert next_run is not None
        assert isinstance(next_run, datetime)

    def test_get_next_run_no_job(self, scheduler: SchedulerService) -> None:
        """Test getting next run time for non-existent job."""
        next_run = scheduler.get_next_run(999)
        assert next_run is None

    def test_add_job_replaces_existing(
        self, scheduler: SchedulerService, mock_script: MagicMock
    ) -> None:
        """Test adding a job replaces existing job for same script."""
        scheduler.add_job(mock_script)
        assert mock_script.id in scheduler._jobs
        first_call_count = scheduler._scheduler.add_job.call_count

        # Add again - should remove old job and add new one
        scheduler.add_job(mock_script)

        # Verify job was added again (remove_job was called internally)
        assert scheduler._scheduler.add_job.call_count == first_call_count + 1
        assert mock_script.id in scheduler._jobs

    def test_add_job_with_weekdays(
        self, scheduler: SchedulerService, mock_script: MagicMock
    ) -> None:
        """Test adding a job with weekday filter."""
        mock_script.weekdays = "[0, 1, 2, 3, 4]"  # JSON string

        scheduler.add_job(mock_script)

        assert mock_script.id in scheduler._jobs

    def test_add_scheduled_start_job(
        self, scheduler: SchedulerService, mock_script: MagicMock
    ) -> None:
        """Test adding a scheduled start job."""
        mock_script.scheduled_start_enabled = True
        mock_script.scheduled_start_datetime = datetime.now(UTC) + timedelta(hours=1)

        scheduler.add_scheduled_start_job(mock_script)

        assert mock_script.id in scheduler._scheduled_start_jobs

    def test_add_scheduled_start_job_disabled(
        self, scheduler: SchedulerService, mock_script: MagicMock
    ) -> None:
        """Test adding a scheduled start job when disabled does nothing."""
        mock_script.scheduled_start_enabled = False
        mock_script.scheduled_start_datetime = datetime.now(UTC) + timedelta(hours=1)

        scheduler.add_scheduled_start_job(mock_script)

        assert mock_script.id not in scheduler._scheduled_start_jobs

    def test_add_scheduled_start_job_no_datetime(
        self, scheduler: SchedulerService, mock_script: MagicMock
    ) -> None:
        """Test adding a scheduled start job without datetime does nothing."""
        mock_script.scheduled_start_enabled = True
        mock_script.scheduled_start_datetime = None

        scheduler.add_scheduled_start_job(mock_script)

        assert mock_script.id not in scheduler._scheduled_start_jobs

    def test_remove_scheduled_start_job(
        self, scheduler: SchedulerService, mock_script: MagicMock
    ) -> None:
        """Test removing a scheduled start job."""
        mock_script.scheduled_start_enabled = True
        mock_script.scheduled_start_datetime = datetime.now(UTC) + timedelta(hours=1)

        scheduler.add_scheduled_start_job(mock_script)
        assert mock_script.id in scheduler._scheduled_start_jobs

        scheduler.remove_scheduled_start_job(mock_script.id)
        assert mock_script.id not in scheduler._scheduled_start_jobs

    def test_update_job_with_scheduled_start(
        self, scheduler: SchedulerService, mock_script: MagicMock
    ) -> None:
        """Test update_job with future scheduled start delays repeat job.

        When a script has both repeat_enabled and a future scheduled_start:
        - The scheduled_start job should be added
        - The repeat job should NOT be added yet (will be added when scheduled_start fires)
        """
        mock_script.scheduled_start_enabled = True
        mock_script.scheduled_start_datetime = datetime.now(UTC) + timedelta(hours=1)

        scheduler.update_job(mock_script)

        # Only scheduled start job should be present (repeat job is delayed)
        assert mock_script.id not in scheduler._jobs
        assert mock_script.id in scheduler._scheduled_start_jobs

    def test_update_job_disables_scheduled_start(
        self, scheduler: SchedulerService, mock_script: MagicMock
    ) -> None:
        """Test update_job removes scheduled start job when disabled."""
        mock_script.scheduled_start_enabled = True
        mock_script.scheduled_start_datetime = datetime.now(UTC) + timedelta(hours=1)

        scheduler.update_job(mock_script)
        assert mock_script.id in scheduler._scheduled_start_jobs

        mock_script.scheduled_start_enabled = False
        scheduler.update_job(mock_script)

        assert mock_script.id not in scheduler._scheduled_start_jobs

    @pytest.mark.asyncio
    @patch("script_launcher.services.scheduler.script_executor")
    @patch("script_launcher.services.scheduler.log_manager")
    async def test_execute_scheduled_start_deactivates_script_without_repeat(
        self,
        mock_log_manager: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """Test that scheduled start deactivates script when repeat_enabled=False.

        The script should be deactivated (is_active=False) but the user's
        scheduled_start configuration should be preserved.
        """
        from script_launcher.services.scheduler import SchedulerService

        # Setup mocks - must use AsyncMock for async functions
        mock_executor.is_running.return_value = False
        mock_executor.run = AsyncMock()
        mock_log_manager.write = AsyncMock()

        # Mock script object for database
        mock_script_obj = MagicMock()
        mock_script_obj.is_active = True
        mock_script_obj.scheduled_start_enabled = True

        # Mock async session
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_script_obj)

        # Create scheduler and add job to internal dict
        with patch("script_launcher.services.scheduler.BackgroundScheduler"):
            sched = SchedulerService()
            sched._scheduled_start_jobs[1] = "job_1"

        # Patch async_session_maker inside the function
        with patch("script_launcher.database.async_session_maker") as mock_session_maker:
            mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute scheduled start with repeat_enabled=False
            await sched._execute_scheduled_start_async(
                script_id=1,
                script_name="Test Script",
                script_path="/path/to/script.py",
                repeat_enabled=False,
            )

        # Verify job was removed from internal dict
        assert 1 not in sched._scheduled_start_jobs

        # Verify script was deactivated but config preserved
        assert mock_script_obj.is_active is False
        # scheduled_start_enabled should remain True (user's config preserved)
        assert mock_script_obj.scheduled_start_enabled is True

    @pytest.mark.asyncio
    @patch("script_launcher.services.scheduler.script_executor")
    @patch("script_launcher.services.scheduler.log_manager")
    async def test_execute_scheduled_start_keeps_script_active_with_repeat(
        self,
        mock_log_manager: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """Test that scheduled start keeps script active when repeat_enabled=True."""
        from script_launcher.services.scheduler import SchedulerService

        # Setup mocks - must use AsyncMock for async functions
        mock_executor.is_running.return_value = False
        mock_executor.run = AsyncMock()
        mock_log_manager.write = AsyncMock()

        # Mock script object for database
        mock_script_obj = MagicMock()
        mock_script_obj.id = 1
        mock_script_obj.name = "Test Script"
        mock_script_obj.path = "/path/to/script.py"
        mock_script_obj.repeat_enabled = True
        mock_script_obj.interval_value = 10
        mock_script_obj.interval_unit = "seconds"
        mock_script_obj.weekdays = None
        mock_script_obj.is_active = True

        # Mock async session
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_script_obj)

        # Create scheduler with mocked BackgroundScheduler
        with patch("script_launcher.services.scheduler.BackgroundScheduler") as mock_bg:
            mock_instance = MagicMock()
            mock_instance.running = False
            mock_instance.add_job.return_value = MagicMock(id="mock_job_id")
            mock_bg.return_value = mock_instance

            sched = SchedulerService()
            sched._scheduled_start_jobs[1] = "job_1"

            # Patch async_session_maker inside the function
            with patch("script_launcher.database.async_session_maker") as mock_session_maker:
                mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

                # Execute scheduled start with repeat_enabled=True
                await sched._execute_scheduled_start_async(
                    script_id=1,
                    script_name="Test Script",
                    script_path="/path/to/script.py",
                    repeat_enabled=True,
                )

            # Verify job was removed from internal dict (it already fired)
            assert 1 not in sched._scheduled_start_jobs

            # Script execution was called
            mock_executor.run.assert_called_once()

            # Verify repeat job was added (script stays active)
            assert 1 in sched._jobs

    def test_update_job_with_future_scheduled_start_delays_repeat(
        self, scheduler: SchedulerService, mock_script: MagicMock
    ) -> None:
        """Test that repeat job is NOT added when scheduled_start is pending in the future.

        When a script has:
        - repeat_enabled = True
        - scheduled_start_enabled = True with a future datetime

        The repeat job should NOT be added immediately. It should wait until the
        scheduled_start fires, then add the repeat job.
        """
        mock_script.repeat_enabled = True
        mock_script.scheduled_start_enabled = True
        mock_script.scheduled_start_datetime = datetime.now(UTC) + timedelta(hours=1)

        scheduler.update_job(mock_script)

        # Scheduled start job should be present
        assert mock_script.id in scheduler._scheduled_start_jobs
        # Repeat job should NOT be present yet (waiting for scheduled_start)
        assert mock_script.id not in scheduler._jobs

    def test_update_job_adds_repeat_when_no_scheduled_start(
        self, scheduler: SchedulerService, mock_script: MagicMock
    ) -> None:
        """Test that repeat job IS added when there's no scheduled_start."""
        mock_script.repeat_enabled = True
        mock_script.scheduled_start_enabled = False
        mock_script.scheduled_start_datetime = None

        scheduler.update_job(mock_script)

        # Repeat job should be present (no scheduled_start to wait for)
        assert mock_script.id in scheduler._jobs
        # No scheduled start job
        assert mock_script.id not in scheduler._scheduled_start_jobs

    @pytest.mark.asyncio
    @patch("script_launcher.services.scheduler.script_executor")
    @patch("script_launcher.services.scheduler.log_manager")
    async def test_execute_scheduled_start_adds_repeat_job(
        self,
        mock_log_manager: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """Test that scheduled start adds repeat job when repeat_enabled=True.

        After the scheduled_start fires, if the script has repeat_enabled=True,
        the repeat job should be added to continue periodic execution.
        """
        from script_launcher.services.scheduler import SchedulerService

        # Setup mocks
        mock_executor.is_running.return_value = False
        mock_executor.run = AsyncMock()
        mock_log_manager.write = AsyncMock()

        # Create a mock script with repeat configuration
        mock_script = MagicMock()
        mock_script.id = 1
        mock_script.name = "Test Script"
        mock_script.path = "/path/to/script.py"
        mock_script.repeat_enabled = True
        mock_script.interval_value = 10
        mock_script.interval_unit = "seconds"
        mock_script.weekdays = None
        mock_script.is_active = True

        # Mock async session to return the script
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_script)

        # Create scheduler with mocked BackgroundScheduler
        with patch("script_launcher.services.scheduler.BackgroundScheduler") as mock_bg:
            mock_instance = MagicMock()
            mock_instance.running = False
            mock_instance.add_job.return_value = MagicMock(id="mock_job_id")
            mock_bg.return_value = mock_instance

            sched = SchedulerService()
            sched._scheduled_start_jobs[1] = "job_1"

            # Patch async_session_maker
            with patch("script_launcher.database.async_session_maker") as mock_session_maker:
                mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

                # Execute scheduled start with repeat_enabled=True
                await sched._execute_scheduled_start_async(
                    script_id=1,
                    script_name="Test Script",
                    script_path="/path/to/script.py",
                    repeat_enabled=True,
                )

            # Verify repeat job was added
            assert 1 in sched._jobs
