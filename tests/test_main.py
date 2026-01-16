"""Tests for main module startup logic."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from script_launcher.main import load_scheduled_scripts
from script_launcher.models import Script


@pytest.mark.asyncio
async def test_load_scheduled_scripts_deactivates_past_scheduled_start(
    patched_async_session_maker: async_sessionmaker,
) -> None:
    """Test that scripts with past scheduled_start and no repeat are deactivated on startup.

    Scenario:
    - Script is active
    - scheduled_start_enabled = True
    - scheduled_start_datetime is in the PAST
    - repeat_enabled = False

    Expected: Script should be deactivated on startup.
    """
    # Arrange: Create a script with past scheduled_start and no repeat
    # Use naive datetime (local time) because that's what the frontend sends
    past_datetime = datetime.now() - timedelta(hours=1)  # Naive, local time

    async with patched_async_session_maker() as session:
        script = Script(
            name="Past Scheduled Script",
            path="/path/to/script.py",
            is_active=True,
            repeat_enabled=False,
            scheduled_start_enabled=True,
            scheduled_start_datetime=past_datetime,
        )
        session.add(script)
        await session.commit()
        script_id = script.id

    # Act: Load scheduled scripts (simulates Uvicorn startup)
    await load_scheduled_scripts()

    # Assert: Script should be deactivated
    async with patched_async_session_maker() as session:
        result = await session.execute(select(Script).where(Script.id == script_id))
        updated_script = result.scalar_one()

        assert updated_script.is_active is False, "Script with past scheduled_start should be deactivated"
        # User's config should be preserved
        assert updated_script.scheduled_start_enabled is True, "scheduled_start_enabled should remain True"


@pytest.mark.asyncio
async def test_load_scheduled_scripts_keeps_future_scheduled_start_active(
    patched_async_session_maker: async_sessionmaker,
) -> None:
    """Test that scripts with future scheduled_start remain active on startup.

    Scenario:
    - Script is active
    - scheduled_start_enabled = True
    - scheduled_start_datetime is in the FUTURE
    - repeat_enabled = False

    Expected: Script should remain active on startup.
    """
    # Arrange: Create a script with future scheduled_start
    # Use naive datetime (local time) because that's what the frontend sends
    # and SQLite doesn't preserve timezone info
    future_datetime = datetime.now() + timedelta(hours=1)  # Naive, local time

    async with patched_async_session_maker() as session:
        script = Script(
            name="Future Scheduled Script",
            path="/path/to/script.py",
            is_active=True,
            repeat_enabled=False,
            scheduled_start_enabled=True,
            scheduled_start_datetime=future_datetime,
        )
        session.add(script)
        await session.commit()
        script_id = script.id

    # Act: Load scheduled scripts (simulates Uvicorn startup)
    await load_scheduled_scripts()

    # Assert: Script should remain active
    async with patched_async_session_maker() as session:
        result = await session.execute(select(Script).where(Script.id == script_id))
        updated_script = result.scalar_one()

        assert updated_script.is_active is True, "Script with future scheduled_start should remain active"
        assert updated_script.scheduled_start_enabled is True, "scheduled_start_enabled should remain True"


@pytest.mark.asyncio
async def test_load_scheduled_scripts_deactivates_no_scheduling(
    patched_async_session_maker: async_sessionmaker,
) -> None:
    """Test that active scripts without any scheduling are deactivated on startup.

    Scenario:
    - Script is active
    - scheduled_start_enabled = False
    - repeat_enabled = False

    Expected: Script should be deactivated on startup.
    """
    # Arrange: Create a script with no scheduling
    async with patched_async_session_maker() as session:
        script = Script(
            name="No Scheduling Script",
            path="/path/to/script.py",
            is_active=True,
            repeat_enabled=False,
            scheduled_start_enabled=False,
        )
        session.add(script)
        await session.commit()
        script_id = script.id

    # Act: Load scheduled scripts (simulates Uvicorn startup)
    await load_scheduled_scripts()

    # Assert: Script should be deactivated
    async with patched_async_session_maker() as session:
        result = await session.execute(select(Script).where(Script.id == script_id))
        updated_script = result.scalar_one()

        assert updated_script.is_active is False, "Script without scheduling should be deactivated"


@pytest.mark.asyncio
async def test_load_scheduled_scripts_keeps_repeat_enabled_active(
    patched_async_session_maker: async_sessionmaker,
) -> None:
    """Test that scripts with repeat_enabled remain active on startup.

    Scenario:
    - Script is active
    - repeat_enabled = True

    Expected: Script should remain active on startup.
    """
    # Arrange: Create a script with repeat enabled
    async with patched_async_session_maker() as session:
        script = Script(
            name="Repeat Enabled Script",
            path="/path/to/script.py",
            is_active=True,
            repeat_enabled=True,
            interval_value=30,
            interval_unit="seconds",
            scheduled_start_enabled=False,
        )
        session.add(script)
        await session.commit()
        script_id = script.id

    # Act: Load scheduled scripts (simulates Uvicorn startup)
    await load_scheduled_scripts()

    # Assert: Script should remain active
    async with patched_async_session_maker() as session:
        result = await session.execute(select(Script).where(Script.id == script_id))
        updated_script = result.scalar_one()

        assert updated_script.is_active is True, "Script with repeat_enabled should remain active"


@pytest.mark.asyncio
async def test_load_scheduled_scripts_deactivates_naive_past_datetime(
    patched_async_session_maker: async_sessionmaker,
) -> None:
    """Test that scripts with naive (no timezone) past datetime are deactivated.

    This test reproduces the real-world scenario where:
    - User enters a datetime in their local timezone (e.g., 08:14 CET)
    - It's stored as naive datetime (08:14:00 without timezone)
    - The datetime is in the past in local time

    The system should interpret naive datetimes as LOCAL time, not UTC,
    since that's what the user intended when entering the value.

    Expected: Script should be deactivated because the datetime has passed
    in the user's local timezone.
    """
    # Arrange: Create a script with a naive datetime that is 1 minute in the past
    # Using local time (not UTC) because that's what the frontend sends
    past_local = datetime.now() - timedelta(minutes=1)  # Naive, local time

    async with patched_async_session_maker() as session:
        script = Script(
            name="Naive Past Datetime Script",
            path="/path/to/script.py",
            is_active=True,
            repeat_enabled=False,
            scheduled_start_enabled=True,
            scheduled_start_datetime=past_local,  # Naive datetime (no timezone)
        )
        session.add(script)
        await session.commit()
        script_id = script.id

    # Act: Load scheduled scripts (simulates Uvicorn startup)
    await load_scheduled_scripts()

    # Assert: Script should be deactivated
    async with patched_async_session_maker() as session:
        result = await session.execute(select(Script).where(Script.id == script_id))
        updated_script = result.scalar_one()

        assert updated_script.is_active is False, "Script with naive past datetime should be deactivated"
        # User's config should be preserved
        assert updated_script.scheduled_start_enabled is True, "scheduled_start_enabled should remain True"
