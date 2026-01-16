"""Tests for script executor service."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from script_launcher.services.executor import Execution, ScriptExecutor


@pytest.fixture
def executor() -> ScriptExecutor:
    """Provide a fresh executor instance for each test."""
    return ScriptExecutor()


@pytest.fixture
def simple_script() -> Path:
    """Create a simple test script that exits quickly."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write('print("Hello from test script")\n')
        return Path(f.name)


@pytest.fixture
def slow_script() -> Path:
    """Create a script that takes time to complete."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("import time\nprint('Starting')\ntime.sleep(10)\nprint('Done')\n")
        return Path(f.name)


@pytest.fixture
def failing_script() -> Path:
    """Create a script that fails with an error."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write('import sys\nprint("Error!", file=sys.stderr)\nsys.exit(1)\n')
        return Path(f.name)


class TestScriptExecutor:
    """Tests for ScriptExecutor class."""

    @pytest.mark.asyncio
    async def test_run_simple_script(self, executor: ScriptExecutor, simple_script: Path) -> None:
        """Test running a simple script that completes successfully."""
        execution = await executor.run(
            script_id=1,
            script_name="test",
            script_path=str(simple_script),
            trigger="manual",
        )

        assert execution.script_id == 1
        assert execution.script_name == "test"
        assert execution.status == "success"
        assert execution.exit_code == 0
        assert execution.finished_at is not None

    @pytest.mark.asyncio
    async def test_run_failing_script(self, executor: ScriptExecutor, failing_script: Path) -> None:
        """Test running a script that fails."""
        execution = await executor.run(
            script_id=1,
            script_name="failing",
            script_path=str(failing_script),
            trigger="manual",
        )

        assert execution.status == "failed"
        assert execution.exit_code == 1

    @pytest.mark.asyncio
    async def test_is_running(self, executor: ScriptExecutor, slow_script: Path) -> None:
        """Test checking if a script is running."""
        assert executor.is_running(1) is False

        # Start script in background
        task = asyncio.create_task(
            executor.run(
                script_id=1,
                script_name="slow",
                script_path=str(slow_script),
                trigger="manual",
            )
        )

        # Give it time to start
        await asyncio.sleep(0.2)
        assert executor.is_running(1) is True

        # Stop it
        executions = executor.get_active_executions()
        if executions:
            await executor.stop(executions[0].id)

        await task
        assert executor.is_running(1) is False

    @pytest.mark.asyncio
    async def test_stop_execution(self, executor: ScriptExecutor, slow_script: Path) -> None:
        """Test stopping a running execution."""
        # Start script in background
        task = asyncio.create_task(
            executor.run(
                script_id=1,
                script_name="slow",
                script_path=str(slow_script),
                trigger="manual",
            )
        )

        # Give it time to start
        await asyncio.sleep(0.2)

        # Get the execution and stop it
        executions = executor.get_active_executions()
        assert len(executions) == 1

        result = await executor.stop(executions[0].id)
        assert result is True

        execution = await task
        assert execution.status == "failed"
        assert execution.exit_code == -15  # SIGTERM

    @pytest.mark.asyncio
    async def test_stop_nonexistent_execution(self, executor: ScriptExecutor) -> None:
        """Test stopping an execution that doesn't exist."""
        result = await executor.stop("nonexistent-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_active_executions(self, executor: ScriptExecutor, slow_script: Path) -> None:
        """Test getting list of active executions."""
        assert executor.get_active_executions() == []

        # Start script
        task = asyncio.create_task(
            executor.run(
                script_id=1,
                script_name="slow",
                script_path=str(slow_script),
                trigger="manual",
            )
        )

        await asyncio.sleep(0.2)
        executions = executor.get_active_executions()
        assert len(executions) == 1
        assert executions[0].script_id == 1
        assert executions[0].status == "running"

        # Clean up
        await executor.stop(executions[0].id)
        await task

    @pytest.mark.asyncio
    async def test_get_execution(self, executor: ScriptExecutor, simple_script: Path) -> None:
        """Test getting a specific execution by ID."""
        execution = await executor.run(
            script_id=1,
            script_name="test",
            script_path=str(simple_script),
            trigger="manual",
        )

        retrieved = executor.get_execution(execution.id)
        assert retrieved is not None
        assert retrieved.id == execution.id

    @pytest.mark.asyncio
    async def test_get_execution_nonexistent(self, executor: ScriptExecutor) -> None:
        """Test getting a non-existent execution."""
        result = executor.get_execution("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_parallel_execution_blocked(self, executor: ScriptExecutor, slow_script: Path) -> None:
        """Test that parallel execution of same script is blocked."""
        # Start first execution
        task1 = asyncio.create_task(
            executor.run(
                script_id=1,
                script_name="slow",
                script_path=str(slow_script),
                trigger="manual",
            )
        )

        await asyncio.sleep(0.2)

        # Try to start second execution - should raise
        with pytest.raises(RuntimeError, match="already running"):
            await executor.run(
                script_id=1,
                script_name="slow",
                script_path=str(slow_script),
                trigger="manual",
            )

        # Clean up
        executions = executor.get_active_executions()
        if executions:
            await executor.stop(executions[0].id)
        await task1


class TestExecution:
    """Tests for Execution dataclass."""

    def test_execution_creation(self) -> None:
        """Test creating an Execution instance."""
        from datetime import UTC, datetime

        execution = Execution(
            id="test-id",
            script_id=1,
            script_name="test",
            started_at=datetime.now(UTC),
            trigger="manual",
        )

        assert execution.id == "test-id"
        assert execution.script_id == 1
        assert execution.status == "running"
        assert execution.exit_code is None
        assert execution.finished_at is None
