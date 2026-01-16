"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from script_launcher.api import executions_router, logs_router, scripts_router
from script_launcher.config import settings
from script_launcher.database import async_session_maker, init_db
from script_launcher.models import Script
from script_launcher.services.scheduler import get_scheduler_service
from script_launcher.utils import is_datetime_in_past
from script_launcher.websocket import websocket_router


async def load_scheduled_scripts() -> None:
    """Load all scripts with active schedules into the scheduler.

    Rules:
    - Scripts with repeat_enabled: Load into scheduler for periodic execution
    - Scripts with scheduled_start_enabled (no repeat):
      - If datetime is in the future: Load into scheduler
      - If datetime is in the past: Deactivate the script
    - Scripts that are already inactive: Leave them inactive
    """
    scheduler = get_scheduler_service()

    async with async_session_maker() as session:
        # Get all active scripts
        result = await session.execute(
            select(Script).where(Script.is_active == True)  # noqa: E712
        )
        scripts = result.scalars().all()

        for script in scripts:
            # Case 1: Script has repetition enabled - load repeat job
            if script.repeat_enabled:
                scheduler.add_job(script)
                print(f"Loaded repeat job: {script.name} (every {script.interval_value} {script.interval_unit})")

            # Case 2: Script has scheduled start enabled
            if script.scheduled_start_enabled and script.scheduled_start_datetime:
                if not is_datetime_in_past(script.scheduled_start_datetime):
                    # Future datetime - load scheduled start job
                    scheduler.add_scheduled_start_job(script)
                    print(f"Loaded scheduled start: {script.name} (at {script.scheduled_start_datetime})")
                else:
                    # Past datetime - deactivate if no repetition
                    # Keep scheduled_start_enabled/datetime intact (user's config)
                    if not script.repeat_enabled:
                        script.is_active = False
                        print(
                            f"Deactivated expired script: {script.name} "
                            f"(scheduled for {script.scheduled_start_datetime})"
                        )

            # Case 3: Script is active but has no scheduling at all
            # (no repeat, no scheduled start) - deactivate it
            if not script.repeat_enabled and not script.scheduled_start_enabled:
                script.is_active = False
                print(f"Deactivated script without scheduling: {script.name}")

        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    await init_db()
    get_scheduler_service().start()
    await load_scheduled_scripts()

    yield

    # Shutdown
    get_scheduler_service().shutdown()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(scripts_router)
app.include_router(executions_router)
app.include_router(logs_router)
app.include_router(websocket_router)

# Mount static files
static_dir = Path(__file__).parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
