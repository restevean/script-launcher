"""Logs API endpoints."""

from datetime import date

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
async def get_logs(
    script_id: int | None = Query(None, description="Filter by script ID"),
    log_date: date | None = Query(None, description="Date to query (defaults to today)"),
) -> list[dict]:
    """Get logs for a specific date, optionally filtered by script."""
    # TODO: Implement LogManager integration
    return []


@router.get("/dates")
async def get_available_dates() -> list[date]:
    """List dates that have log files available."""
    # TODO: Implement LogManager integration
    return []
