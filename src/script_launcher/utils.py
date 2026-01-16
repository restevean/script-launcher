"""Utility functions shared across the application."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from script_launcher.models import Script


def is_datetime_in_past(dt: datetime) -> bool:
    """Check if a datetime is in the past.

    Handles both naive and timezone-aware datetimes:
    - Naive datetimes are treated as LOCAL time (what the user entered)
    - Timezone-aware datetimes are compared directly with UTC
    """
    if dt.tzinfo is None:
        return dt < datetime.now()
    return dt < datetime.now(UTC)


def should_script_remain_active(script: "Script") -> bool:
    """Determine if a script should remain active based on its configuration.

    A script should remain active only if it has valid scheduling:
    - Has repeat_enabled = True, OR
    - Has scheduled_start_enabled = True with a future datetime
    """
    if script.repeat_enabled:
        return True

    if script.scheduled_start_enabled and script.scheduled_start_datetime:
        if not is_datetime_in_past(script.scheduled_start_datetime):
            return True

    return False


def should_deactivate_after_execution(script: "Script") -> bool:
    """Determine if a script should be deactivated after execution.

    Inverse of should_script_remain_active - a script should be deactivated if:
    - It doesn't have repeat_enabled (no periodic execution)
    - AND it doesn't have a future scheduled_start (no pending one-time execution)
    """
    return not should_script_remain_active(script)
