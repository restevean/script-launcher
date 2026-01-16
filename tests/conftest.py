"""Pytest configuration and fixtures."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from script_launcher.database import Base, get_db
from script_launcher.main import app


@pytest.fixture(autouse=True)
def mock_scheduler_service():
    """Mock the scheduler service globally to prevent thread creation."""
    mock_service = MagicMock()
    with (
        patch(
            "script_launcher.api.scripts.get_scheduler_service",
            return_value=mock_service,
        ),
        patch(
            "script_launcher.main.get_scheduler_service",
            return_value=mock_service,
        ),
    ):
        yield mock_service


# Test database (in-memory)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)

test_async_session_maker = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_async_session_maker() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide a test HTTP client."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Patch async_session_maker to return a function that gives back db_session
    # This ensures background tasks use the same session as the test
    @asynccontextmanager
    async def mock_session_maker():
        # Expire all objects to force refresh from DB
        db_session.expire_all()
        yield db_session

    with patch(
        "script_launcher.api.executions.async_session_maker",
        mock_session_maker,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

    app.dependency_overrides.clear()


def pytest_sessionfinish(session, exitstatus):
    """Cleanup after all tests have run."""
    import asyncio

    # Shutdown any scheduler that was created
    import script_launcher.services.scheduler as scheduler_module

    if scheduler_module._scheduler_service is not None:
        try:
            scheduler_module._scheduler_service._scheduler.shutdown(wait=False)
        except Exception:
            pass

    async def dispose_engine():
        await test_engine.dispose()

    # Create a new event loop for cleanup (the test event loop may be closed)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(dispose_engine())
    finally:
        loop.close()


@pytest.fixture
async def patched_async_session_maker():
    """Patch async_session_maker in main module to use test database.

    This fixture creates fresh tables for each test and cleans up after.
    """
    # Create tables before test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    with patch(
        "script_launcher.main.async_session_maker",
        test_async_session_maker,
    ):
        # Also patch the database module for consistency
        with patch(
            "script_launcher.database.async_session_maker",
            test_async_session_maker,
        ):
            yield test_async_session_maker

    # Clean up after test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
