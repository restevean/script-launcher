"""Tests for scheduler service."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

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
