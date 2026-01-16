"""Logs API endpoints."""

from datetime import date

from fastapi import APIRouter, Query

from script_launcher.services.log_manager import log_manager

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
async def get_logs(
    script_name: str | None = Query(None, description="Filter by script name"),
    log_date: date | None = Query(None, description="Date to query (defaults to today)"),
) -> list[dict]:
    """Get logs for a specific date, optionally filtered by script."""
    entries = log_manager.read_logs(log_date=log_date, script_name=script_name)
    return [
        {
            "timestamp": entry.timestamp.isoformat(),
            "script_id": entry.script_id,
            "script_name": entry.script_name,
            "level": entry.level,
            "message": entry.message,
        }
        for entry in entries
    ]


@router.get("/dates")
async def get_available_dates() -> list[date]:
    """List dates that have log files available."""
    return log_manager.get_available_dates()
