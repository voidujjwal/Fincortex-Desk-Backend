import asyncio
import json
import logging
from typing import Optional
from fastapi import WebSocket

logger = logging.getLogger("tradingagents.ws")


class ConnectionManager:
    """Manages WebSocket connections grouped by job_id.

    Supports reconnect: clients can reconnect to a running job
    and receive the latest state. Each job_id has a room of
    connected clients that receive broadcast updates.
    """

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
        self._heartbeat_tasks: dict[str, asyncio.Task] = {}

    async def connect(self, job_id: str, websocket: WebSocket) -> None:
        """Register a WebSocket client for a job room."""
        await websocket.accept()
        if job_id not in self._connections:
            self._connections[job_id] = []
        self._connections[job_id].append(websocket)
        logger.info("WebSocket connected for job %s (total: %d)", job_id, len(self._connections[job_id]))

    async def disconnect(self, job_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket client from a job room."""
        if job_id in self._connections:
            self._connections[job_id] = [
                ws for ws in self._connections[job_id] if ws is not websocket
            ]
            if not self._connections[job_id]:
                del self._connections[job_id]
                if job_id in self._heartbeat_tasks:
                    self._heartbeat_tasks[job_id].cancel()
                    del self._heartbeat_tasks[job_id]
        logger.info("WebSocket disconnected for job %s", job_id)

    async def send_to_job(
        self, job_id: str, message: dict, exclude: Optional[WebSocket] = None
    ) -> None:
        """Broadcast a message to all clients in a job room."""
        disconnected = []
        for ws in self._connections.get(job_id, []):
            if ws is exclude:
                continue
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            await self.disconnect(job_id, ws)

    async def send_progress(
        self, job_id: str, agent: str, progress: float
    ) -> None:
        """Send a progress update to a job room."""
        await self.send_to_job(job_id, {
            "agent": agent,
            "status": "running",
            "progress": progress,
        })

    async def send_agent_status(
        self, job_id: str, agent: str, status: str, content: str = ""
    ) -> None:
        """Send an agent status update to a job room."""
        await self.send_to_job(job_id, {
            "agent": agent,
            "status": status,
            "content": content,
        })

    async def send_error(
        self, job_id: str, agent: str, error: str
    ) -> None:
        """Send an error message to a job room."""
        await self.send_to_job(job_id, {
            "agent": agent,
            "status": "error",
            "error": error,
        })

    async def send_completion(
        self, job_id: str, agent: str, result: dict
    ) -> None:
        """Send a completion message to a job room."""
        await self.send_to_job(job_id, {
            "agent": agent,
            "status": "completed",
            "result": result,
        })

    async def send_heartbeat(self, job_id: str) -> None:
        """Send a heartbeat ping to a job room."""
        await self.send_to_job(job_id, {"type": "heartbeat", "timestamp": asyncio.get_event_loop().time()})

    async def start_heartbeat(self, job_id: str, interval: int = 30) -> None:
        """Start a periodic heartbeat task for a job room."""
        async def _heartbeat():
            while job_id in self._connections:
                try:
                    await self.send_heartbeat(job_id)
                except Exception:
                    pass
                await asyncio.sleep(interval)

        if job_id not in self._heartbeat_tasks:
            self._heartbeat_tasks[job_id] = asyncio.create_task(_heartbeat())

    def get_connected_jobs(self) -> list[str]:
        """Return list of job_ids with active connections."""
        return list(self._connections.keys())


ws_manager = ConnectionManager()