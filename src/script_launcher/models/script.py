"""Script model with integrated schedule configuration."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from script_launcher.database import Base


class Script(Base):
    """Model representing a Python script with optional scheduling."""

    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Schedule configuration (integrated)
    repeat_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    interval_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interval_unit: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # seconds, minutes, hours, days

    # Weekdays filter (JSON array: [0,1,2,3,4] for Mon-Fri, null for all days)
    weekdays: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Scheduling timestamps
    last_run: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<Script(id={self.id}, name='{self.name}', active={self.is_active})>"
