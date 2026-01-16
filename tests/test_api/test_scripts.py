"""Tests for scripts API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_scripts_empty(client: AsyncClient) -> None:
    """Test listing scripts when none exist."""
    response = await client.get("/api/scripts")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_script(client: AsyncClient) -> None:
    """Test creating a new script."""
    script_data = {
        "name": "Test Script",
        "path": "/path/to/script.py",
        "description": "A test script",
        "repeat_enabled": False,
    }
    response = await client.post("/api/scripts", json=script_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Script"
    assert data["path"] == "/path/to/script.py"
    assert data["description"] == "A test script"
    assert data["repeat_enabled"] is False
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_create_script_with_schedule(client: AsyncClient) -> None:
    """Test creating a script with schedule configuration."""
    script_data = {
        "name": "Scheduled Script",
        "path": "/path/to/script.py",
        "repeat_enabled": True,
        "interval_value": 30,
        "interval_unit": "minutes",
        "weekdays": [0, 1, 2, 3, 4],  # Monday to Friday
    }
    response = await client.post("/api/scripts", json=script_data)
    assert response.status_code == 201
    data = response.json()
    assert data["repeat_enabled"] is True
    assert data["interval_value"] == 30
    assert data["interval_unit"] == "minutes"


@pytest.mark.asyncio
async def test_get_script(client: AsyncClient) -> None:
    """Test getting a single script by ID."""
    # Create script first
    script_data = {"name": "Get Test", "path": "/path/to/script.py"}
    create_response = await client.post("/api/scripts", json=script_data)
    script_id = create_response.json()["id"]

    # Get the script
    response = await client.get(f"/api/scripts/{script_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == script_id
    assert data["name"] == "Get Test"


@pytest.mark.asyncio
async def test_get_script_not_found(client: AsyncClient) -> None:
    """Test getting a non-existent script returns 404."""
    response = await client.get("/api/scripts/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_script(client: AsyncClient) -> None:
    """Test updating an existing script."""
    # Create script first
    script_data = {"name": "Original Name", "path": "/original/path.py"}
    create_response = await client.post("/api/scripts", json=script_data)
    script_id = create_response.json()["id"]

    # Update the script
    update_data = {"name": "Updated Name", "path": "/updated/path.py"}
    response = await client.put(f"/api/scripts/{script_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["path"] == "/updated/path.py"


@pytest.mark.asyncio
async def test_update_script_schedule(client: AsyncClient) -> None:
    """Test updating script schedule configuration."""
    # Create script without schedule
    script_data = {"name": "Test", "path": "/path.py", "repeat_enabled": False}
    create_response = await client.post("/api/scripts", json=script_data)
    script_id = create_response.json()["id"]

    # Enable schedule
    update_data = {
        "repeat_enabled": True,
        "interval_value": 10,
        "interval_unit": "seconds",
    }
    response = await client.put(f"/api/scripts/{script_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["repeat_enabled"] is True
    assert data["interval_value"] == 10
    assert data["interval_unit"] == "seconds"


@pytest.mark.asyncio
async def test_update_script_not_found(client: AsyncClient) -> None:
    """Test updating a non-existent script returns 404."""
    response = await client.put("/api/scripts/999", json={"name": "Test"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_script(client: AsyncClient) -> None:
    """Test deleting a script."""
    # Create script first
    script_data = {"name": "To Delete", "path": "/path.py"}
    create_response = await client.post("/api/scripts", json=script_data)
    script_id = create_response.json()["id"]

    # Delete the script
    response = await client.delete(f"/api/scripts/{script_id}")
    assert response.status_code == 204

    # Verify it's gone
    get_response = await client.get(f"/api/scripts/{script_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_script_not_found(client: AsyncClient) -> None:
    """Test deleting a non-existent script returns 404."""
    response = await client.delete("/api/scripts/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_enable_script(client: AsyncClient) -> None:
    """Test enabling a script."""
    # Create and disable script
    script_data = {"name": "Test", "path": "/path.py"}
    create_response = await client.post("/api/scripts", json=script_data)
    script_id = create_response.json()["id"]
    await client.post(f"/api/scripts/{script_id}/disable")

    # Enable it
    response = await client.post(f"/api/scripts/{script_id}/enable")
    assert response.status_code == 200
    assert response.json()["is_active"] is True


@pytest.mark.asyncio
async def test_disable_script(client: AsyncClient) -> None:
    """Test disabling a script."""
    # Create script (active by default)
    script_data = {"name": "Test", "path": "/path.py"}
    create_response = await client.post("/api/scripts", json=script_data)
    script_id = create_response.json()["id"]

    # Disable it
    response = await client.post(f"/api/scripts/{script_id}/disable")
    assert response.status_code == 200
    assert response.json()["is_active"] is False


@pytest.mark.asyncio
async def test_list_scripts_filter_active(client: AsyncClient) -> None:
    """Test listing only active scripts."""
    # Create two scripts
    await client.post("/api/scripts", json={"name": "Active", "path": "/a.py"})
    response2 = await client.post("/api/scripts", json={"name": "Inactive", "path": "/b.py"})
    script_id = response2.json()["id"]
    await client.post(f"/api/scripts/{script_id}/disable")

    # List active only
    response = await client.get("/api/scripts?active_only=true")
    assert response.status_code == 200
    scripts = response.json()
    assert len(scripts) == 1
    assert scripts[0]["name"] == "Active"
