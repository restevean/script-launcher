"""Script execution service."""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from script_launcher.services.log_manager import log_manager

if TYPE_CHECKING:
    from asyncio.subprocess import Process


@dataclass
class Execution:
    """Represents a script execution."""

    id: str
    script_id: int
    script_name: str
    started_at: datetime
    trigger: str  # 'manual' or 'scheduled'
    process: "Process | None" = field(default=None, repr=False)
    finished_at: datetime | None = None
    status: str = "running"  # 'running', 'success', 'failed'
    exit_code: int | None = None


class ScriptExecutor:
    """Service for executing Python scripts."""

    def __init__(self) -> None:
        """Initialize the executor."""
        self._active_executions: dict[str, Execution] = {}
        self._script_locks: dict[int, asyncio.Lock] = {}

    def _get_lock(self, script_id: int) -> asyncio.Lock:
        """Get or create a lock for a script."""
        if script_id not in self._script_locks:
            self._script_locks[script_id] = asyncio.Lock()
        return self._script_locks[script_id]

    def is_running(self, script_id: int) -> bool:
        """Check if a script is currently running."""
        return any(e.script_id == script_id and e.status == "running" for e in self._active_executions.values())

    def get_active_executions(self) -> list[Execution]:
        """Get all active executions."""
        return [e for e in self._active_executions.values() if e.status == "running"]

    def get_execution(self, execution_id: str) -> Execution | None:
        """Get an execution by ID."""
        return self._active_executions.get(execution_id)

    async def _stream_output(
        self,
        stream: asyncio.StreamReader,
        script_id: int,
        script_name: str,
        level: str,
    ) -> None:
        """Stream output from a subprocess line by line."""
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip()
            if text:
                await log_manager.write(script_id, script_name, level, text)

    async def run(
        self,
        script_id: int,
        script_name: str,
        script_path: str,
        trigger: str = "manual",
    ) -> Execution:
        """Execute a script."""
        lock = self._get_lock(script_id)

        if lock.locked():
            raise RuntimeError(f"Script {script_name} is already running")

        async with lock:
            execution = Execution(
                id=str(uuid4()),
                script_id=script_id,
                script_name=script_name,
                started_at=datetime.now(UTC),
                trigger=trigger,
            )
            self._active_executions[execution.id] = execution

            await log_manager.write(
                script_id,
                script_name,
                "INFO",
                f"Execution started (trigger={trigger})",
            )

            try:
                process = await asyncio.create_subprocess_exec(
                    "python",
                    script_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                execution.process = process

                # Stream stdout and stderr concurrently
                await asyncio.gather(
                    self._stream_output(process.stdout, script_id, script_name, "STDOUT"),
                    self._stream_output(process.stderr, script_id, script_name, "STDERR"),
                )

                # Wait for process to finish
                await process.wait()

                execution.finished_at = datetime.now(UTC)
                execution.exit_code = process.returncode
                execution.status = "success" if process.returncode == 0 else "failed"

                duration = (execution.finished_at - execution.started_at).total_seconds()
                await log_manager.write(
                    script_id,
                    script_name,
                    "INFO",
                    f"Execution finished (exit_code={execution.exit_code}, duration={duration:.2f}s)",
                )

            except Exception as e:
                execution.finished_at = datetime.now(UTC)
                execution.status = "failed"
                execution.exit_code = -1
                await log_manager.write(
                    script_id,
                    script_name,
                    "ERROR",
                    f"Execution failed: {e}",
                )
                raise

            return execution

    async def stop(self, execution_id: str) -> bool:
        """Stop a running execution."""
        execution = self._active_executions.get(execution_id)
        if not execution or execution.status != "running":
            return False

        if execution.process:
            execution.process.terminate()
            try:
                await asyncio.wait_for(execution.process.wait(), timeout=5.0)
            except TimeoutError:
                execution.process.kill()

            execution.finished_at = datetime.now(UTC)
            execution.status = "failed"
            execution.exit_code = -15  # SIGTERM

            await log_manager.write(
                execution.script_id,
                execution.script_name,
                "INFO",
                "Execution stopped by user",
            )

        return True


# Singleton instance
script_executor = ScriptExecutor()
