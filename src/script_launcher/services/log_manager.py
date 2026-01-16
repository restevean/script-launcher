"""Log management service."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from script_launcher.config import settings


@dataclass
class LogEntry:
    """Represents a single log entry."""

    timestamp: datetime
    script_id: int
    script_name: str
    level: str  # 'INFO', 'STDOUT', 'STDERR'
    message: str

    def to_line(self) -> str:
        """Convert to log file line format."""
        ts = self.timestamp.isoformat(timespec="milliseconds")
        return f"{ts}|{self.script_name}|{self.level}|{self.message}"

    @classmethod
    def from_line(cls, line: str, script_id: int = 0) -> "LogEntry":
        """Parse a log line into a LogEntry."""
        parts = line.strip().split("|", 3)
        if len(parts) != 4:
            raise ValueError(f"Invalid log line format: {line}")
        return cls(
            timestamp=datetime.fromisoformat(parts[0]),
            script_id=script_id,
            script_name=parts[1],
            level=parts[2],
            message=parts[3],
        )


class LogManager:
    """Service for managing script execution logs."""

    def __init__(self, log_dir: Path | None = None) -> None:
        """Initialize the log manager.

        Args:
            log_dir: Optional directory for logs. If not provided, uses settings.
        """
        self._logs_dir = log_dir if log_dir is not None else settings.logs_dir
        self._websocket_clients: set[asyncio.Queue] = set()

    def _get_log_file(self, log_date: date | None = None) -> Path:
        """Get the log file path for a specific date."""
        if log_date is None:
            log_date = date.today()
        return self._logs_dir / f"{log_date.isoformat()}.log"

    async def write(
        self,
        script_id: int,
        script_name: str,
        level: str,
        message: str,
    ) -> None:
        """Write a log entry."""
        entry = LogEntry(
            timestamp=datetime.now(UTC),
            script_id=script_id,
            script_name=script_name,
            level=level,
            message=message,
        )

        # Write to file
        log_file = self._get_log_file()
        with log_file.open("a", encoding="utf-8") as f:
            f.write(entry.to_line() + "\n")

        # Broadcast to WebSocket clients
        await self.broadcast(entry)

    async def broadcast(self, entry: LogEntry) -> None:
        """Broadcast a log entry to all connected WebSocket clients."""
        message = {
            "type": "log",
            "timestamp": entry.timestamp.isoformat(),
            "script_id": entry.script_id,
            "script_name": entry.script_name,
            "level": entry.level,
            "message": entry.message,
        }
        for queue in self._websocket_clients:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                pass  # Skip if queue is full

    def register_client(self, queue: asyncio.Queue) -> None:
        """Register a WebSocket client queue."""
        self._websocket_clients.add(queue)

    def unregister_client(self, queue: asyncio.Queue) -> None:
        """Unregister a WebSocket client queue."""
        self._websocket_clients.discard(queue)

    def read_logs(
        self,
        log_date: date | None = None,
        script_name: str | None = None,
    ) -> list[LogEntry]:
        """Read logs from a file, optionally filtered by script."""
        log_file = self._get_log_file(log_date)
        if not log_file.exists():
            return []

        entries = []
        with log_file.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = LogEntry.from_line(line)
                    if script_name is None or entry.script_name == script_name:
                        entries.append(entry)
                except ValueError:
                    continue  # Skip malformed lines

        return entries

    def get_available_dates(self) -> list[date]:
        """Get list of dates that have log files."""
        dates = []
        for log_file in self._logs_dir.glob("*.log"):
            try:
                log_date = date.fromisoformat(log_file.stem)
                dates.append(log_date)
            except ValueError:
                continue
        return sorted(dates, reverse=True)


# Singleton instance
log_manager = LogManager()
