"""Pydantic schemas for Script."""

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ScriptBase(BaseModel):
    """Base schema with common script fields."""

    name: str = Field(..., min_length=1, max_length=255)
    path: str = Field(..., min_length=1, max_length=1024)
    description: str | None = None

    # Schedule configuration
    repeat_enabled: bool = False
    interval_value: int | None = Field(None, ge=1)
    interval_unit: str | None = Field(None, pattern="^(seconds|minutes|hours|days)$")
    weekdays: list[int] | None = Field(None, description="Days of week: 0=Mon, 6=Sun")

    # Scheduled start (one-time execution)
    scheduled_start_enabled: bool = False
    scheduled_start_datetime: datetime | None = None


class ScriptCreate(ScriptBase):
    """Schema for creating a new script."""

    pass


class ScriptUpdate(BaseModel):
    """Schema for updating an existing script."""

    name: str | None = Field(None, min_length=1, max_length=255)
    path: str | None = Field(None, min_length=1, max_length=1024)
    description: str | None = None
    is_active: bool | None = None
    repeat_enabled: bool | None = None
    interval_value: int | None = Field(None, ge=1)
    interval_unit: str | None = Field(None, pattern="^(seconds|minutes|hours|days)$")
    weekdays: list[int] | None = None
    scheduled_start_enabled: bool | None = None
    scheduled_start_datetime: datetime | None = None


class ScriptRead(ScriptBase):
    """Schema for reading a script."""

    id: int
    is_active: bool
    last_run: datetime | None
    next_run: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("weekdays", mode="before")
    @classmethod
    def parse_weekdays(cls, v: Any) -> list[int] | None:
        """Convert JSON string to list if needed."""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None
        return v
