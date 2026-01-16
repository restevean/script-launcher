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
from script_launcher.websocket import websocket_router


async def load_scheduled_scripts() -> None:
    """Load all scripts with active schedules into the scheduler."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Script).where(
                Script.is_active == True,  # noqa: E712
                Script.repeat_enabled == True,  # noqa: E712
            )
        )
        scripts = result.scalars().all()
        for script in scripts:
            get_scheduler_service().add_job(script)
            print(
                f"Loaded scheduled script: {script.name} "
                f"(every {script.interval_value} {script.interval_unit})"
            )


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
