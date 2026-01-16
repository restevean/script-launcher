"""Tests for executions API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_executions_empty(client: AsyncClient) -> None:
    """Test listing executions when none are running."""
    response = await client.get("/api/executions")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_run_script_not_found(client: AsyncClient) -> None:
    """Test running a non-existent script returns 404."""
    response = await client.post("/api/scripts/999/run")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_stop_script_not_found(client: AsyncClient) -> None:
    """Test stopping a non-existent script returns 404."""
    response = await client.post("/api/scripts/999/stop")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_stop_script_not_running(client: AsyncClient) -> None:
    """Test stopping a script that is not running returns 404."""
    # Create a script
    script_data = {"name": "Test", "path": "/path.py"}
    create_response = await client.post("/api/scripts", json=script_data)
    script_id = create_response.json()["id"]

    # Try to stop it (it's not running)
    response = await client.post(f"/api/scripts/{script_id}/stop")
    assert response.status_code == 404
    assert "No running execution" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_script_status(client: AsyncClient) -> None:
    """Test getting script running status."""
    # Create a script
    script_data = {"name": "Test", "path": "/path.py"}
    create_response = await client.post("/api/scripts", json=script_data)
    script_id = create_response.json()["id"]

    # Check status (should not be running)
    response = await client.get(f"/api/scripts/{script_id}/status")
    assert response.status_code == 200
    data = response.json()
    assert data["script_id"] == script_id
    assert data["is_running"] is False
    assert data["execution_id"] is None


@pytest.mark.asyncio
async def test_get_script_status_not_found(client: AsyncClient) -> None:
    """Test getting status of non-existent script returns 404."""
    response = await client.get("/api/scripts/999/status")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_execution_not_found(client: AsyncClient) -> None:
    """Test getting a non-existent execution returns 404."""
    response = await client.get("/api/executions/non-existent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_script_without_repeat_deactivates_after_execution(
    client: AsyncClient,
    tmp_path,
) -> None:
    """Test that a script without repetition is deactivated after execution.

    Scenario:
    - Script has repeat_enabled = False
    - Script has scheduled_start_enabled = False
    - Script is active and executed
    - After execution completes, script should be deactivated

    This ensures scripts without scheduling don't remain active forever
    after being executed.
    """
    import asyncio

    # Create a simple test script that exits quickly
    test_script = tmp_path / "quick_script.py"
    test_script.write_text('print("Done")\n')

    # Create script without repetition
    script_data = {
        "name": "No Repeat Script",
        "path": str(test_script),
        "repeat_enabled": False,
        "scheduled_start_enabled": False,
    }
    create_response = await client.post("/api/scripts", json=script_data)
    assert create_response.status_code == 201
    script_id = create_response.json()["id"]

    # Enable the script
    enable_response = await client.post(f"/api/scripts/{script_id}/enable")
    assert enable_response.status_code == 200
    assert enable_response.json()["is_active"] is True

    # Execute the script
    run_response = await client.post(f"/api/scripts/{script_id}/run")
    assert run_response.status_code == 200

    # Wait for execution to complete and script to be deactivated
    # Use a loop with timeout to handle background task timing
    for _ in range(20):  # Max 2 seconds
        await asyncio.sleep(0.1)
        get_response = await client.get(f"/api/scripts/{script_id}")
        if get_response.json()["is_active"] is False:
            break

    # Verify script is now deactivated
    get_response = await client.get(f"/api/scripts/{script_id}")
    assert get_response.status_code == 200
    script_data = get_response.json()
    assert script_data["is_active"] is False, "Script without repetition should be deactivated after execution"
