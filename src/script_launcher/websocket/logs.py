"""WebSocket endpoint for real-time log streaming."""

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from script_launcher.services.log_manager import log_manager

router = APIRouter()


@router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming all logs."""
    await websocket.accept()

    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    log_manager.register_client(queue)

    try:
        while True:
            message = await queue.get()
            await websocket.send_text(json.dumps(message))
    except WebSocketDisconnect:
        pass
    finally:
        log_manager.unregister_client(queue)


@router.websocket("/ws/logs/{script_id}")
async def websocket_logs_filtered(websocket: WebSocket, script_id: int) -> None:
    """WebSocket endpoint for streaming logs filtered by script ID."""
    await websocket.accept()

    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    log_manager.register_client(queue)

    try:
        while True:
            message = await queue.get()
            # Filter by script_id
            if message.get("script_id") == script_id:
                await websocket.send_text(json.dumps(message))
    except WebSocketDisconnect:
        pass
    finally:
        log_manager.unregister_client(queue)
