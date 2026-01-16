"""Scripts CRUD API endpoints."""

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from script_launcher.database import get_db
from script_launcher.models import Script
from script_launcher.schemas import ScriptCreate, ScriptRead, ScriptUpdate
from script_launcher.services.scheduler import get_scheduler_service


def is_datetime_in_past(dt: datetime) -> bool:
    """Check if a datetime is in the past.

    Handles both naive and timezone-aware datetimes:
    - Naive datetimes are treated as LOCAL time (what the user entered)
    - Timezone-aware datetimes are compared directly with UTC
    """
    if dt.tzinfo is None:
        # Naive datetime - compare with local time
        return dt < datetime.now()
    else:
        # Timezone-aware datetime - compare with UTC
        return dt < datetime.now(UTC)


def should_script_remain_active(script: Script) -> bool:
    """Determine if a script should remain active based on its configuration.

    A script should remain active only if it has valid scheduling:
    - Has repeat_enabled = True, OR
    - Has scheduled_start_enabled = True with a future datetime
    """
    # If repeat is enabled, script can remain active
    if script.repeat_enabled:
        return True

    # If scheduled start is enabled with a future datetime, script can remain active
    if script.scheduled_start_enabled and script.scheduled_start_datetime:
        if not is_datetime_in_past(script.scheduled_start_datetime):
            return True

    # No valid scheduling - script should be deactivated
    return False


router = APIRouter(prefix="/api/scripts", tags=["scripts"])


@router.get("", response_model=list[ScriptRead])
async def list_scripts(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[Script]:
    """List all scripts, optionally filtered by active status."""
    query = select(Script)
    if active_only:
        query = query.where(Script.is_active == True)  # noqa: E712
    query = query.order_by(Script.name)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{script_id}", response_model=ScriptRead)
async def get_script(
    script_id: int,
    db: AsyncSession = Depends(get_db),
) -> Script:
    """Get a script by ID."""
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
    return script


@router.post("", response_model=ScriptRead, status_code=status.HTTP_201_CREATED)
async def create_script(
    script_data: ScriptCreate,
    db: AsyncSession = Depends(get_db),
) -> Script:
    """Create a new script."""
    # Convert weekdays list to JSON string for storage
    weekdays_json = json.dumps(script_data.weekdays) if script_data.weekdays else None

    script = Script(
        name=script_data.name,
        path=script_data.path,
        description=script_data.description,
        repeat_enabled=script_data.repeat_enabled,
        interval_value=script_data.interval_value,
        interval_unit=script_data.interval_unit,
        weekdays=weekdays_json,
        scheduled_start_enabled=script_data.scheduled_start_enabled,
        scheduled_start_datetime=script_data.scheduled_start_datetime,
    )
    db.add(script)
    await db.flush()
    await db.refresh(script)

    # Update scheduler if script has active repetition
    get_scheduler_service().update_job(script)

    return script


@router.put("/{script_id}", response_model=ScriptRead)
async def update_script(
    script_id: int,
    script_data: ScriptUpdate,
    db: AsyncSession = Depends(get_db),
) -> Script:
    """Update an existing script."""
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    update_data = script_data.model_dump(exclude_unset=True)

    # Handle weekdays conversion
    if "weekdays" in update_data:
        update_data["weekdays"] = json.dumps(update_data["weekdays"]) if update_data["weekdays"] else None

    for field, value in update_data.items():
        setattr(script, field, value)

    # Check if active script should be deactivated due to invalid scheduling
    # Keep scheduled_start_enabled/datetime intact (user's config)
    scheduler = get_scheduler_service()
    if script.is_active and not should_script_remain_active(script):
        script.is_active = False
        # Remove all scheduler jobs
        scheduler.remove_job(script_id)
        scheduler.remove_scheduled_start_job(script_id)
    else:
        # Update scheduler based on new configuration
        scheduler.update_job(script)

    await db.flush()
    await db.refresh(script)

    return script


@router.delete("/{script_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_script(
    script_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a script."""
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    # Remove from scheduler before deleting
    get_scheduler_service().remove_job(script_id)

    await db.delete(script)
    await db.flush()


@router.post("/{script_id}/enable", response_model=ScriptRead)
async def enable_script(
    script_id: int,
    db: AsyncSession = Depends(get_db),
) -> Script:
    """Enable a script and its scheduled repetition."""
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
    script.is_active = True
    await db.flush()
    await db.refresh(script)

    # Update scheduler (will add job if repeat_enabled)
    get_scheduler_service().update_job(script)

    return script


@router.post("/{script_id}/disable", response_model=ScriptRead)
async def disable_script(
    script_id: int,
    db: AsyncSession = Depends(get_db),
) -> Script:
    """Disable a script and stop its scheduled repetition."""
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
    script.is_active = False
    await db.flush()
    await db.refresh(script)

    # Remove from scheduler (both repeat and scheduled start jobs)
    get_scheduler_service().remove_job(script_id)
    get_scheduler_service().remove_scheduled_start_job(script_id)

    return script
