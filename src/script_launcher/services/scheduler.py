"""Scheduler service for periodic script execution."""

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from script_launcher.services.executor import script_executor
from script_launcher.services.log_manager import log_manager

if TYPE_CHECKING:
    from script_launcher.models import Script


class SchedulerService:
    """Service for managing scheduled script executions."""

    def __init__(self) -> None:
        """Initialize the scheduler."""
        self._scheduler = BackgroundScheduler(daemon=True)
        self._jobs: dict[int, str] = {}  # script_id -> job_id (repeat jobs)
        self._scheduled_start_jobs: dict[int, str] = {}  # script_id -> job_id

    def start(self) -> None:
        """Start the scheduler."""
        if not self._scheduler.running:
            self._scheduler.start()

    def shutdown(self) -> None:
        """Shutdown the scheduler and force-close the internal thread pool."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        # Force shutdown the internal thread pool to prevent process hanging
        # APScheduler stores the pool as _pool in the executor
        try:
            executor = self._scheduler._executors.get("default")
            if executor and hasattr(executor, "_pool"):
                executor._pool.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass  # Best effort cleanup

    def add_job(self, script: "Script") -> None:
        """Add a scheduled job for a script."""
        if not script.repeat_enabled or not script.interval_value or not script.interval_unit:
            return

        # Remove existing job if any
        self.remove_job(script.id)

        # Build interval kwargs
        interval_kwargs = {script.interval_unit: script.interval_value}

        trigger = IntervalTrigger(**interval_kwargs)

        # Parse weekdays if set
        weekdays = None
        if script.weekdays:
            import json

            try:
                weekdays = json.loads(script.weekdays)
            except (json.JSONDecodeError, TypeError):
                weekdays = None

        job = self._scheduler.add_job(
            self._execute_script,
            trigger=trigger,
            args=[script.id, script.name, script.path, weekdays],
            id=f"script_{script.id}",
            name=f"Script: {script.name}",
        )
        self._jobs[script.id] = job.id

    def remove_job(self, script_id: int) -> None:
        """Remove a scheduled repeat job."""
        if script_id in self._jobs:
            job_id = self._jobs.pop(script_id)
            try:
                self._scheduler.remove_job(job_id)
            except Exception:
                pass  # Job might already be removed

    def add_scheduled_start_job(self, script: "Script") -> None:
        """Add a one-time scheduled start job for a script."""
        if not script.scheduled_start_enabled or not script.scheduled_start_datetime:
            return

        # Remove existing scheduled start job if any
        self.remove_scheduled_start_job(script.id)

        # Use the scheduled datetime (if in past, APScheduler will run immediately)
        trigger = DateTrigger(run_date=script.scheduled_start_datetime)

        job = self._scheduler.add_job(
            self._execute_scheduled_start,
            trigger=trigger,
            args=[script.id, script.name, script.path, script.repeat_enabled],
            id=f"script_{script.id}_scheduled_start",
            name=f"Script: {script.name} (scheduled start)",
        )
        self._scheduled_start_jobs[script.id] = job.id

    def remove_scheduled_start_job(self, script_id: int) -> None:
        """Remove a scheduled start job."""
        if script_id in self._scheduled_start_jobs:
            job_id = self._scheduled_start_jobs.pop(script_id)
            try:
                self._scheduler.remove_job(job_id)
            except Exception:
                pass  # Job might already be removed

    def _has_pending_scheduled_start(self, script: "Script") -> bool:
        """Check if script has a pending scheduled start in the future."""
        if not script.scheduled_start_enabled or not script.scheduled_start_datetime:
            return False
        # Check if scheduled start is in the future
        from datetime import UTC

        if script.scheduled_start_datetime.tzinfo is None:
            # Naive datetime - compare with local time
            from datetime import datetime as dt

            return script.scheduled_start_datetime > dt.now()
        else:
            # Timezone-aware datetime - compare with UTC
            from datetime import datetime as dt

            return script.scheduled_start_datetime > dt.now(UTC)

    def update_job(self, script: "Script") -> None:
        """Update scheduled jobs based on script configuration."""
        has_pending_start = self._has_pending_scheduled_start(script)

        # Handle repeat job
        # Don't add repeat job if there's a pending scheduled start (it will be added after)
        if script.repeat_enabled and script.is_active and not has_pending_start:
            self.add_job(script)
        else:
            self.remove_job(script.id)

        # Handle scheduled start job (independent of repeat)
        if script.scheduled_start_enabled and script.is_active:
            self.add_scheduled_start_job(script)
        else:
            self.remove_scheduled_start_job(script.id)

    def get_next_run(self, script_id: int) -> datetime | None:
        """Get the next scheduled run time for a script."""
        if script_id not in self._jobs:
            return None
        try:
            job = self._scheduler.get_job(self._jobs[script_id])
            return job.next_run_time if job else None
        except Exception:
            return None

    def _execute_script(
        self,
        script_id: int,
        script_name: str,
        script_path: str,
        weekdays: list[int] | None,
    ) -> None:
        """Execute a script (called by scheduler from background thread)."""
        # Run the async execution in a new event loop
        asyncio.run(self._execute_script_async(script_id, script_name, script_path, weekdays))

    async def _execute_script_async(
        self,
        script_id: int,
        script_name: str,
        script_path: str,
        weekdays: list[int] | None,
    ) -> None:
        """Async implementation of script execution."""
        # Check weekday filter
        if weekdays:
            current_weekday = datetime.now().weekday()  # 0=Monday, 6=Sunday
            if current_weekday not in weekdays:
                await log_manager.write(
                    script_id,
                    script_name,
                    "INFO",
                    f"Skipped: not scheduled for today (weekday={current_weekday})",
                )
                return

        # Check if already running
        if script_executor.is_running(script_id):
            await log_manager.write(
                script_id,
                script_name,
                "INFO",
                "Skipped: script is already running",
            )
            return

        # Execute
        try:
            await script_executor.run(script_id, script_name, script_path, trigger="scheduled")
        except Exception as e:
            await log_manager.write(
                script_id,
                script_name,
                "ERROR",
                f"Scheduled execution failed: {e}",
            )

    def _execute_scheduled_start(
        self,
        script_id: int,
        script_name: str,
        script_path: str,
        repeat_enabled: bool,
    ) -> None:
        """Execute a scheduled start job (one-time execution)."""
        asyncio.run(
            self._execute_scheduled_start_async(script_id, script_name, script_path, repeat_enabled)
        )

    async def _execute_scheduled_start_async(
        self,
        script_id: int,
        script_name: str,
        script_path: str,
        repeat_enabled: bool,
    ) -> None:
        """Async implementation of scheduled start execution."""
        # Import here to avoid circular imports
        from script_launcher.database import async_session_maker
        from script_launcher.models import Script

        # Clean up job from internal dict (it has already fired)
        if script_id in self._scheduled_start_jobs:
            del self._scheduled_start_jobs[script_id]

        # Check if already running
        if script_executor.is_running(script_id):
            await log_manager.write(
                script_id,
                script_name,
                "INFO",
                "Scheduled start skipped: script is already running",
            )
            return

        # Execute
        try:
            await script_executor.run(
                script_id, script_name, script_path, trigger="scheduled_start"
            )
        except Exception as e:
            await log_manager.write(
                script_id,
                script_name,
                "ERROR",
                f"Scheduled start execution failed: {e}",
            )

        # Handle post-execution based on repeat configuration
        try:
            async with async_session_maker() as session:
                script = await session.get(Script, script_id)
                if script:
                    if repeat_enabled:
                        # Add repeat job now that scheduled start has fired
                        self.add_job(script)
                        await log_manager.write(
                            script_id,
                            script_name,
                            "INFO",
                            "Scheduled start completed, repeat schedule now active",
                        )
                    else:
                        # No repetition - deactivate the script after execution
                        # Keep scheduled_start_enabled/datetime intact (user's config)
                        script.is_active = False
                        await session.commit()
                        await log_manager.write(
                            script_id,
                            script_name,
                            "INFO",
                            "Script deactivated after one-time scheduled execution",
                        )
        except Exception as e:
            await log_manager.write(
                script_id,
                script_name,
                "ERROR",
                f"Failed to handle post-execution: {e}",
            )


# Lazy singleton instance
_scheduler_service: SchedulerService | None = None


def get_scheduler_service() -> SchedulerService:
    """Get the scheduler service singleton (lazy initialization)."""
    global _scheduler_service
    if _scheduler_service is None:
        _scheduler_service = SchedulerService()
    return _scheduler_service
