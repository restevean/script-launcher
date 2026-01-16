"""Executions API endpoints."""

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from script_launcher.database import async_session_maker, get_db
from script_launcher.models import Script
from script_launcher.services.executor import script_executor
from script_launcher.services.log_manager import log_manager

router = APIRouter(prefix="/api", tags=["executions"])


def _is_datetime_in_past(dt: datetime) -> bool:
    """Check if a datetime is in the past (naive datetimes treated as local time)."""
    if dt.tzinfo is None:
        return dt < datetime.now()
    from datetime import UTC

    return dt < datetime.now(UTC)


def _should_deactivate_after_execution(script: Script) -> bool:
    """Determine if a script should be deactivated after execution.

    A script should be deactivated after execution if:
    - It doesn't have repeat_enabled (no periodic execution)
    - AND it doesn't have a future scheduled_start (no pending one-time execution)
    """
    if script.repeat_enabled:
        return False

    if script.scheduled_start_enabled and script.scheduled_start_datetime:
        if not _is_datetime_in_past(script.scheduled_start_datetime):
            return False  # Has a future scheduled start

    return True


async def _run_script_task(script_id: int, script_name: str, script_path: str) -> None:
    """Background task to run a script."""
    try:
        await script_executor.run(script_id, script_name, script_path, trigger="manual")
    except Exception:
        pass  # Errors are logged by the executor

    # After execution, check if script should be deactivated
    try:
        async with async_session_maker() as session:
            script = await session.get(Script, script_id)
            if script and script.is_active and _should_deactivate_after_execution(script):
                script.is_active = False
                await session.commit()
                await log_manager.write(
                    script_id,
                    script_name,
                    "INFO",
                    "Script deactivated after execution (no repetition configured)",
                )
    except Exception:
        pass  # Best effort - don't fail if deactivation fails


@router.post("/scripts/{script_id}/run")
async def run_script(
    script_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Execute a script manually."""
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    if script_executor.is_running(script_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Script is already running",
        )

    # Run in background to not block the response
    background_tasks.add_task(_run_script_task, script.id, script.name, script.path)

    return {"message": "Execution started", "script_id": script_id}


@router.get("/scripts/{script_id}/status")
async def get_script_status(
    script_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the running status of a script."""
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    is_running = script_executor.is_running(script_id)
    execution = None
    if is_running:
        executions = script_executor.get_active_executions()
        execution = next((e for e in executions if e.script_id == script_id), None)

    return {
        "script_id": script_id,
        "is_running": is_running,
        "execution_id": execution.id if execution else None,
        "started_at": execution.started_at.isoformat() if execution else None,
    }


@router.post("/scripts/{script_id}/stop")
async def stop_script(
    script_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Stop a running script execution."""
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    # Find active execution for this script
    executions = script_executor.get_active_executions()
    target = next((e for e in executions if e.script_id == script_id), None)

    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No running execution found for this script",
        )

    stopped = await script_executor.stop(target.id)
    if not stopped:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop execution",
        )

    return {"message": "Execution stopped", "script_id": script_id}


@router.get("/executions")
async def list_executions() -> list[dict]:
    """List all active executions."""
    executions = script_executor.get_active_executions()
    return [
        {
            "id": e.id,
            "script_id": e.script_id,
            "script_name": e.script_name,
            "started_at": e.started_at.isoformat(),
            "trigger": e.trigger,
            "status": e.status,
        }
        for e in executions
    ]


@router.get("/executions/{execution_id}")
async def get_execution(execution_id: str) -> dict:
    """Get execution status by ID."""
    execution = script_executor.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")

    return {
        "id": execution.id,
        "script_id": execution.script_id,
        "script_name": execution.script_name,
        "started_at": execution.started_at.isoformat(),
        "finished_at": execution.finished_at.isoformat() if execution.finished_at else None,
        "trigger": execution.trigger,
        "status": execution.status,
        "exit_code": execution.exit_code,
    }
