"""Tests for log manager service."""

import tempfile
from datetime import date
from pathlib import Path

import pytest

from script_launcher.services.log_manager import LogManager


@pytest.fixture
def temp_log_dir() -> Path:
    """Create a temporary directory for logs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def log_manager(temp_log_dir: Path) -> LogManager:
    """Provide a log manager with temporary directory."""
    return LogManager(log_dir=temp_log_dir)


class TestLogManager:
    """Tests for LogManager class."""

    @pytest.mark.asyncio
    async def test_write_log(self, log_manager: LogManager, temp_log_dir: Path) -> None:
        """Test writing a log entry."""
        await log_manager.write(
            script_id=1,
            script_name="test",
            level="INFO",
            message="Test message",
        )

        # Check log file was created
        today = date.today().isoformat()
        log_file = temp_log_dir / f"{today}.log"
        assert log_file.exists()

        # Check content
        content = log_file.read_text()
        assert "test" in content
        assert "INFO" in content
        assert "Test message" in content

    @pytest.mark.asyncio
    async def test_write_multiple_logs(self, log_manager: LogManager, temp_log_dir: Path) -> None:
        """Test writing multiple log entries."""
        await log_manager.write(1, "script1", "INFO", "First message")
        await log_manager.write(2, "script2", "ERROR", "Second message")
        await log_manager.write(1, "script1", "DEBUG", "Third message")

        today = date.today().isoformat()
        log_file = temp_log_dir / f"{today}.log"
        content = log_file.read_text()

        assert "First message" in content
        assert "Second message" in content
        assert "Third message" in content

    def test_read_logs(self, log_manager: LogManager, temp_log_dir: Path) -> None:
        """Test reading logs from file."""
        # Create a log file manually
        today = date.today()
        log_file = temp_log_dir / f"{today.isoformat()}.log"
        log_file.write_text(
            f"{today.isoformat()}T10:00:00.000|test_script|INFO|Test message\n"
            f"{today.isoformat()}T10:01:00.000|test_script|ERROR|Error message\n"
        )

        logs = log_manager.read_logs(today)
        assert len(logs) == 2
        assert logs[0].script_name == "test_script"
        assert logs[0].level == "INFO"
        assert logs[0].message == "Test message"

    def test_read_logs_filter_by_script(self, log_manager: LogManager, temp_log_dir: Path) -> None:
        """Test reading logs filtered by script name."""
        today = date.today()
        log_file = temp_log_dir / f"{today.isoformat()}.log"
        log_file.write_text(
            f"{today.isoformat()}T10:00:00.000|script1|INFO|Message 1\n"
            f"{today.isoformat()}T10:01:00.000|script2|INFO|Message 2\n"
            f"{today.isoformat()}T10:02:00.000|script1|INFO|Message 3\n"
        )

        logs = log_manager.read_logs(today, script_name="script1")
        assert len(logs) == 2
        assert all(log.script_name == "script1" for log in logs)

    def test_read_logs_no_file(self, log_manager: LogManager) -> None:
        """Test reading logs when no file exists."""
        logs = log_manager.read_logs(date(2000, 1, 1))
        assert logs == []

    def test_get_available_dates(self, log_manager: LogManager, temp_log_dir: Path) -> None:
        """Test getting list of dates with logs."""
        # Create some log files
        (temp_log_dir / "2025-01-10.log").write_text("log1")
        (temp_log_dir / "2025-01-11.log").write_text("log2")
        (temp_log_dir / "2025-01-12.log").write_text("log3")
        (temp_log_dir / "not-a-log.txt").write_text("other")

        dates = log_manager.get_available_dates()
        assert len(dates) == 3
        assert date(2025, 1, 10) in dates
        assert date(2025, 1, 11) in dates
        assert date(2025, 1, 12) in dates

    def test_get_available_dates_empty(self, log_manager: LogManager) -> None:
        """Test getting available dates when no logs exist."""
        dates = log_manager.get_available_dates()
        assert dates == []

    @pytest.mark.asyncio
    async def test_log_format(self, log_manager: LogManager, temp_log_dir: Path) -> None:
        """Test log entry format is correct."""
        await log_manager.write(1, "my_script", "WARNING", "Test warning")

        today = date.today().isoformat()
        log_file = temp_log_dir / f"{today}.log"
        content = log_file.read_text().strip()

        # Format: TIMESTAMP|SCRIPT_NAME|LEVEL|MESSAGE
        parts = content.split("|")
        assert len(parts) == 4
        assert "T" in parts[0]  # ISO timestamp
        assert parts[1] == "my_script"
        assert parts[2] == "WARNING"
        assert parts[3] == "Test warning"
