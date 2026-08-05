"""WebSocket routes for real-time streaming."""

import json
import asyncio
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query

from app.websocket import ws_manager
from app.auth import get_current_user

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/{job_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    job_id: str,
    user: dict = Depends(get_current_user),
):
    """WebSocket endpoint for streaming analysis updates.

    Supports:
    - Reconnect: clients can reconnect and receive the latest state
    - Heartbeat: server sends periodic heartbeat messages
    - Progress: streaming progress updates per agent
    - Errors: error messages when agents fail
    - Completion: final completion message when analysis finishes
    """
    await ws_manager.connect(job_id, websocket)
    try:
        while True:
            # Wait for any message from the client (heartbeat/ping)
            try:
                data = await websocket.receive_text()
                msg = json.loads(data)

                if msg.get("type") == "ping":
                    await ws_manager.send_to_job(job_id, {"type": "pong"})

            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        await ws_manager.send_to_job(
            job_id,
            {"agent": "system", "status": "error", "error": str(exc)},
        )
    finally:
        await ws_manager.disconnect(job_id, websocket)